import {table} from "./table.js";
import {TIMELINE_PINS_KEY, TIMELINE_RANGE_KEY, TIMELINE_VIEW_KEY} from "./constants.js";
import {getEffectiveTimezone, getTimezoneConfig, onTimezoneChange} from "./ui_timezone.js";

const PRESETS = ["1h", "12h", "1d", "7d", "15d", "30d", "90d"];
const DEFAULT_RANGE = "1d";
const UNIT_MS = {s: 1000, m: 60000, h: 3600000, d: 86400000};
const FUTURE_RATIO = 0.25;
const ZOOM_FACTOR = 1.5;
const MIN_RANGE_MS = UNIT_MS.m;
const MAX_RANGE_MS = 90 * UNIT_MS.d;
const ROW_HEIGHT = 41;
const ROW_GAP = 4;
const TICKS_PER_VIEW = 12;
const MAX_TICKS = 240;
const TICK_STEPS = [
    60000, 120000, 300000, 600000, 900000, 1800000,
    3600000, 7200000, 10800000, 21600000, 43200000,
    86400000, 172800000, 432000000, 604800000, 1296000000, 2592000000,
];
const STATUS_VARS = {
    firing: "--status-badge-firing",
    unknown: "--status-badge-unknown",
    resolved: "--status-badge-resolved",
    closed: "--status-badge-closed",
    deleted: "--status-badge-closed",
    frozen: "--status-badge-frozen",
};

let active = false;
let rangeText = localStorage.getItem(TIMELINE_RANGE_KEY) || DEFAULT_RANGE;
let rangeMs = parseRange(rangeText) || parseRange(DEFAULT_RANGE);
const rowElements = new Map();
const tickElements = [];
let pinnedIds = loadPins();
let elements;

function loadPins() {
    try {
        return JSON.parse(localStorage.getItem(TIMELINE_PINS_KEY) || "[]");
    } catch {
        return [];
    }
}

function savePins() {
    localStorage.setItem(TIMELINE_PINS_KEY, JSON.stringify(pinnedIds));
}

function isPinned(uniqId) {
    return pinnedIds.includes(uniqId);
}

function togglePin(uniqId) {
    if (isPinned(uniqId)) {
        pinnedIds = pinnedIds.filter(id => id !== uniqId);
    } else {
        pinnedIds = [uniqId, ...pinnedIds.filter(id => id !== uniqId)];
    }
    savePins();
}

function sortRows(rows) {
    const pinned = [];
    const unpinned = [];
    for (const row of rows) {
        (isPinned(row.uniq_id) ? pinned : unpinned).push(row);
    }
    pinned.sort((a, b) => pinnedIds.indexOf(a.uniq_id) - pinnedIds.indexOf(b.uniq_id));
    unpinned.sort((a, b) => b._timeline.created - a._timeline.created);
    return [...pinned, ...unpinned];
}

function parseRange(text) {
    let total = 0;
    for (const [, value, unit] of String(text).toLowerCase().matchAll(/(\d+)\s*([smhd])/g)) {
        total += Number(value) * UNIT_MS[unit];
    }
    return total;
}

function statusColor(status) {
    return `var(${STATUS_VARS[status] || STATUS_VARS.closed})`;
}

function markerOf(timeline, frozen) {
    if (frozen) {
        return timeline.frozen_until ? {time: timeline.frozen_until * 1000, status: "frozen"} : null;
    }
    if (!timeline.next_status || !timeline.status_update_datetime) {
        return null;
    }
    return {time: timeline.status_update_datetime * 1000, status: timeline.next_status};
}

function tickStep(spanMs) {
    const target = rangeMs / TICKS_PER_VIEW;
    let step = TICK_STEPS.reduce((best, candidate) =>
        Math.abs(Math.log(candidate / target)) < Math.abs(Math.log(best / target)) ? candidate : best);
    while (spanMs / step > MAX_TICKS) {
        const coarser = TICK_STEPS.find(candidate => candidate > step);
        if (!coarser) {
            break;
        }
        step = coarser;
    }
    return step;
}

function tickFormat(time, step, zone) {
    if (step >= UNIT_MS.d) {
        return "LLL dd";
    }
    return luxon.DateTime.fromMillis(time, {zone}).hour === 0 ? "LLL dd" : "HH:mm";
}

function createRowElement() {
    const row = document.createElement("div");
    row.className = "timeline-row";
    row.innerHTML = `
        <button type="button" class="timeline-pin" aria-label="Pin incident" aria-pressed="false">
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
                <path d="M7 1.5V8.5M7 8.5L4.5 12H9.5L7 8.5M3.5 4.5C3.5 2.843 5.067 1.5 7 1.5C8.933 1.5 10.5 2.843 10.5 4.5C10.5 5.5 7 6.5 7 6.5C7 6.5 3.5 5.5 3.5 4.5Z" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
        </button>
        <div class="timeline-bar">
            <div class="timeline-seg base"></div>
            <div class="timeline-seg status"></div>
            <div class="timeline-seg retention hidden"></div>
            <div class="timeline-label"></div>
        </div>
        <div class="timeline-marker"></div>`;
    return {
        root: row,
        pin: row.querySelector(".timeline-pin"),
        bar: row.querySelector(".timeline-bar"),
        base: row.querySelector(".timeline-seg.base"),
        status: row.querySelector(".timeline-seg.status"),
        retention: row.querySelector(".timeline-seg.retention"),
        label: row.querySelector(".timeline-label"),
        marker: row.querySelector(".timeline-marker"),
    };
}

function syncRows(rows) {
    const seen = new Set();
    for (const row of rows) {
        seen.add(row.uniq_id);
        if (!rowElements.has(row.uniq_id)) {
            const element = createRowElement();
            element.bar.dataset.uniqId = row.uniq_id;
            element.pin.dataset.uniqId = row.uniq_id;
            elements.rows.appendChild(element.root);
            rowElements.set(row.uniq_id, element);
        }
    }
    for (const [uniqId, element] of rowElements) {
        if (!seen.has(uniqId)) {
            element.root.remove();
            rowElements.delete(uniqId);
        }
    }
}

function layoutRow(row, index, scale) {
    const element = rowElements.get(row.uniq_id);
    const timeline = row._timeline;
    const frozen = Boolean(row._is_frozen);
    const isClosed = timeline.status === "closed" && !frozen;
    const start = scale.x(timeline.created * 1000);
    const barLeft = Math.max(start, 0);
    let barRightTime = scale.now;
    if (isClosed && timeline.status_update_datetime) {
        barRightTime = timeline.status_update_datetime * 1000;
    } else if (timeline.closed) {
        barRightTime = timeline.closed * 1000;
    }
    const barRight = scale.x(barRightTime);
    const width = Math.max(barRight - barLeft, 2);

    element.root.style.top = `${index * (ROW_HEIGHT + ROW_GAP)}px`;
    element.root.classList.toggle("pinned", isPinned(row.uniq_id));
    element.pin.classList.toggle("pinned", isPinned(row.uniq_id));
    element.pin.setAttribute("aria-pressed", isPinned(row.uniq_id) ? "true" : "false");
    element.pin.title = isPinned(row.uniq_id) ? "Unpin incident" : "Pin incident";
    element.bar.style.left = `${barLeft}px`;
    element.bar.style.width = `${width}px`;
    element.bar.classList.toggle("clipped", start < 0);
    element.label.textContent = timeline.alertname;

    if (isClosed && timeline.status_update_datetime) {
        const closedStart = Math.min(Math.max(scale.x(timeline.updated * 1000), barLeft), barRight);
        const nowX = Math.min(Math.max(scale.x(scale.now), closedStart), barRight);
        const baseWidth = closedStart - barLeft;
        const statusWidth = nowX - closedStart;
        const retentionWidth = barRight - nowX;

        element.bar.style.setProperty("--seg-color", statusColor("closed"));
        element.base.style.width = `${baseWidth}px`;
        element.base.classList.toggle("hidden", baseWidth <= 0);
        element.base.classList.toggle("no-split", statusWidth <= 0 && retentionWidth <= 0);

        element.status.style.left = `${baseWidth}px`;
        element.status.style.width = `${statusWidth}px`;
        element.status.classList.toggle("hidden", statusWidth <= 0);
        element.status.classList.toggle("no-split", retentionWidth <= 0);
        element.status.classList.toggle("mid", retentionWidth > 0);

        element.retention.style.left = `${baseWidth + statusWidth}px`;
        element.retention.style.width = `${retentionWidth}px`;
        element.retention.classList.toggle("hidden", retentionWidth <= 0);
    } else {
        const split = frozen ? barLeft : Math.min(Math.max(scale.x(timeline.updated * 1000), barLeft), barLeft + width);
        const baseWidth = split - barLeft;
        const statusWidth = width - baseWidth;

        element.bar.style.setProperty("--seg-color", statusColor(frozen ? "frozen" : timeline.status));
        element.base.style.width = `${baseWidth}px`;
        element.base.classList.toggle("hidden", baseWidth <= 0);
        element.base.classList.toggle("no-split", statusWidth <= 0);

        element.status.style.left = `${baseWidth}px`;
        element.status.style.width = `${statusWidth}px`;
        element.status.classList.toggle("hidden", statusWidth <= 0);
        element.status.classList.toggle("no-split", baseWidth <= 0);
        element.status.classList.remove("mid");

        element.retention.classList.add("hidden");
    }

    const marker = markerOf(timeline, frozen);
    const markerVisible = marker && marker.time <= scale.t0 + scale.spanMs;
    element.marker.classList.toggle("hidden", !markerVisible);
    if (markerVisible) {
        element.marker.style.left = `${scale.x(marker.time)}px`;
        element.marker.style.background = statusColor(marker.status);
    }
}

function layoutAxis(scale) {
    const zone = getEffectiveTimezone(getTimezoneConfig().configTimezone, getTimezoneConfig().userTimezone);
    const step = tickStep(scale.spanMs);
    const offset = luxon.DateTime.fromMillis(scale.t0, {zone}).offset * UNIT_MS.m;
    const first = Math.ceil((scale.t0 + offset) / step) * step - offset;
    let index = 0;

    for (let time = first; time <= scale.t0 + scale.spanMs; time += step, index += 1) {
        if (!tickElements[index]) {
            const tick = document.createElement("div");
            tick.className = "timeline-tick";
            tick.innerHTML = '<span class="timeline-tick-label"></span>';
            elements.axis.appendChild(tick);
            tickElements.push(tick);
        }
        const tick = tickElements[index];
        tick.classList.remove("hidden");
        tick.style.left = `${scale.x(time)}px`;
        tick.firstElementChild.textContent = luxon.DateTime.fromMillis(time, {zone}).toFormat(tickFormat(time, step, zone));
    }
    for (let rest = index; rest < tickElements.length; rest += 1) {
        tickElements[rest].classList.add("hidden");
    }
}

function timelineSpanMs() {
    return rangeMs * (1 + FUTURE_RATIO);
}

function buildScale(now, innerWidth) {
    const spanMs = timelineSpanMs();
    const t0 = now - rangeMs;
    const pxPerMs = innerWidth / spanMs;
    return {
        now,
        t0,
        spanMs,
        width: innerWidth,
        x: time => (time - t0) * pxPerMs,
    };
}

function applyVerticalScroll(rows) {
    const scroll = elements.scroll;
    elements.rows.style.height = `${rows.length * (ROW_HEIGHT + ROW_GAP)}px`;
    const contentHeight = elements.rows.offsetTop + elements.rows.offsetHeight;
    const vertical = contentHeight > scroll.clientHeight;
    scroll.style.overflowY = vertical ? "auto" : "hidden";
    return vertical ? scroll.clientWidth : scroll.offsetWidth;
}

function render() {
    if (!active) {
        return;
    }
    const rows = sortRows(table.getData("active").filter(row => row._timeline));
    const stalePins = pinnedIds.length;
    pinnedIds = pinnedIds.filter(id => rows.some(row => row.uniq_id === id));
    if (pinnedIds.length !== stalePins) {
        savePins();
    }

    elements.placeholder.classList.toggle("hidden", rows.length > 0);
    syncRows(rows);

    const now = Date.now();
    const scale = buildScale(now, applyVerticalScroll(rows));
    elements.canvas.style.width = "100%";
    elements.now.style.left = `${scale.x(scale.now)}px`;
    layoutAxis(scale);
    rows.forEach((row, index) => layoutRow(row, index, scale));
}

function showTooltip(bar, event) {
    const row = table.getRow(bar.dataset.uniqId);
    const labels = row ? row.getData()._timeline.group_labels : null;
    if (!labels || Object.keys(labels).length === 0) {
        return;
    }
    elements.tooltip.replaceChildren(...Object.entries(labels).map(([key, value]) => {
        const pill = document.createElement("span");
        pill.className = "label";
        pill.textContent = `${key}: ${value}`;
        return pill;
    }));
    elements.tooltip.classList.remove("hidden");
    moveTooltip(event);
}

function moveTooltip(event) {
    const rect = elements.tooltip.getBoundingClientRect();
    const left = Math.min(event.clientX + 12, window.innerWidth - rect.width - 8);
    const top = Math.max(event.clientY - rect.height - 12, 8);
    elements.tooltip.style.left = `${left}px`;
    elements.tooltip.style.top = `${top}px`;
}

function initPins() {
    elements.rows.addEventListener("click", event => {
        const pin = event.target.closest(".timeline-pin");
        if (!pin) {
            return;
        }
        event.stopPropagation();
        togglePin(pin.dataset.uniqId);
        render();
    });
}

function initTooltip() {
    elements.rows.addEventListener("mouseover", event => {
        const bar = event.target.closest(".timeline-bar");
        if (bar) {
            showTooltip(bar, event);
        }
    });
    elements.rows.addEventListener("mousemove", event => {
        if (!elements.tooltip.classList.contains("hidden")) {
            moveTooltip(event);
        }
    });
    elements.rows.addEventListener("mouseout", event => {
        if (event.target.closest(".timeline-bar") && !event.relatedTarget?.closest(".timeline-bar")) {
            elements.tooltip.classList.add("hidden");
        }
    });
}

function formatRange(ms) {
    let rest = Math.round(ms);
    const parts = [];
    for (const [unit, label] of [[UNIT_MS.d, "d"], [UNIT_MS.h, "h"], [UNIT_MS.m, "m"]]) {
        const value = Math.floor(rest / unit);
        if (value) {
            parts.push(`${value}${label}`);
            rest -= value * unit;
        }
    }
    return parts.join(" ") || "1m";
}

function applyRangeMs(ms) {
    rangeMs = Math.min(MAX_RANGE_MS, Math.max(MIN_RANGE_MS, Math.round(ms)));
    rangeText = formatRange(rangeMs);
    localStorage.setItem(TIMELINE_RANGE_KEY, rangeText);
    elements.rangeInput.value = rangeText;
    render();
}

function applyRange(text) {
    const parsed = parseRange(text);
    if (!parsed) {
        elements.rangeInput.value = rangeText;
        return;
    }
    rangeText = text.trim();
    rangeMs = parsed;
    localStorage.setItem(TIMELINE_RANGE_KEY, rangeText);
    elements.rangeInput.value = rangeText;
    render();
}

function initRangeSelector() {
    elements.rangeInput.value = rangeText;
    elements.rangeMenu.replaceChildren(...PRESETS.map(preset => {
        const option = document.createElement("button");
        option.type = "button";
        option.className = "timeline-range-option";
        option.textContent = preset;
        option.addEventListener("click", () => {
            elements.rangeMenu.classList.add("hidden");
            applyRange(preset);
        });
        return option;
    }));

    elements.rangeToggle.addEventListener("click", () => elements.rangeMenu.classList.toggle("hidden"));
    elements.rangeInput.addEventListener("keydown", event => {
        if (event.key === "Enter") {
            applyRange(elements.rangeInput.value);
        }
    });
    elements.rangeInput.addEventListener("blur", () => applyRange(elements.rangeInput.value));
    document.addEventListener("click", event => {
        if (!event.target.closest(".timeline-range")) {
            elements.rangeMenu.classList.add("hidden");
        }
    });
}

function initRangeZoom() {
    elements.scroll.addEventListener("wheel", event => {
        if (!active) {
            return;
        }
        event.preventDefault();
        applyRangeMs(rangeMs * (event.deltaY > 0 ? ZOOM_FACTOR : 1 / ZOOM_FACTOR));
    }, {passive: false});
}

function updateToggleButton() {
    elements.toggle.setAttribute("aria-pressed", active ? "true" : "false");
    elements.toggle.title = active ? "Show table" : "Show timeline";
}

function setTimelineActive(value) {
    active = value;
    localStorage.setItem(TIMELINE_VIEW_KEY, value ? "true" : "false");
    elements.view.classList.toggle("hidden", !active);
    elements.dataTable.classList.toggle("hidden", active);
    updateToggleButton();
    if (active) {
        render();
    } else {
        table.redraw(true);
    }
}

function initTimeline() {
    elements = {
        view: document.getElementById("timeline-view"),
        dataTable: document.getElementById("data-table"),
        toggle: document.getElementById("timeline-toggle"),
        scroll: document.getElementById("timeline-scroll"),
        canvas: document.getElementById("timeline-canvas"),
        axis: document.getElementById("timeline-axis"),
        now: document.getElementById("timeline-now"),
        rows: document.getElementById("timeline-rows"),
        placeholder: document.getElementById("timeline-placeholder"),
        tooltip: document.getElementById("timeline-tooltip"),
        rangeInput: document.getElementById("timeline-range-input"),
        rangeToggle: document.getElementById("timeline-range-toggle"),
        rangeMenu: document.getElementById("timeline-range-menu"),
    };

    initRangeSelector();
    initRangeZoom();
    initPins();
    initTooltip();
    elements.toggle.addEventListener("click", () => setTimelineActive(!active));
    table.on("dataFiltered", render);
    table.on("dataProcessed", render);
    window.addEventListener("resize", render);
    onTimezoneChange(render);
    setInterval(render, 1000);
    setTimelineActive(localStorage.getItem(TIMELINE_VIEW_KEY) === "true");
}

export {initTimeline};
