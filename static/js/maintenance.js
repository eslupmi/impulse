import {getBaseUrl, parseWeekStart} from "./utils.js";
import {createEditableFilterBadge, validateAndFormatFilter} from "./filters.js";
import {getIsAuthenticated, onAuthChange} from "./auth.js";
import {
    setTimezoneMode,
    getEffectiveTimezone,
    syncTimezoneSelects,
} from "./ui_timezone.js";

let intervalCalendar = null;
let rows = [];
let rowSeq = 0;
let pickerMode = null;
let pickerTargetId = null;
let configTimezone = "UTC";
let configWeekStart = "Mon";
let messengerType = "";
let userTimezone = null;
let activeIndicatorTimer = null;

const ACTIVE_INDICATOR_POLL_MS = 60000;

const CAL_BTN_SVG =
    '<svg width="16" height="16" viewBox="0 0 13 15" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M9.16667 0.5V3.16667M3.83333 0.5V3.16667M0.5 5.83333H12.5M1.83333 1.83333H11.1667C11.903 1.83333 12.5 2.43029 12.5 3.16667V12.5C12.5 13.2364 11.903 13.8333 11.1667 13.8333H1.83333C1.09695 13.8333 0.5 13.2364 0.5 12.5V3.16667C0.5 2.43029 1.09695 1.83333 1.83333 1.83333Z" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round"/></svg>';

const SAVE_BTN_SVG =
    '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M19 21H5C4.46957 21 3.96086 20.7893 3.58579 20.4142C3.21071 20.0391 3 19.5304 3 19V5C3 4.46957 3.21071 3.96086 3.58579 3.58579C3.96086 3.21071 4.46957 3 5 3H16L21 8V19C21 19.5304 20.7893 20.0391 20.4142 20.4142C20.0391 20.7893 19.5304 21 19 21Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/><path d="M17 21V13H7V21" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/><path d="M7 3V8H15" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>';

const CANCEL_BTN_SVG =
    '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M18 6L6 18M6 6l12 12" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>';

const EDIT_BTN_SVG =
    '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M11.333 2C11.5084 1.82445 11.7163 1.68505 11.9448 1.59033C12.1733 1.4956 12.4179 1.44775 12.6651 1.44968C12.9123 1.45161 13.1561 1.50328 13.3829 1.60153C13.6097 1.69977 13.8148 1.8425 13.9867 2.02134C14.1586 2.20018 14.2936 2.41154 14.3836 2.64297C14.4735 2.8744 14.5163 3.12138 14.5094 3.36968C14.5025 3.61798 14.4461 3.86228 14.3437 4.08801L14.333 4.11334L5.056 13.39L2 14.167L2.777 11.111L11.333 2Z" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round"/></svg>';

const DELETE_BTN_SVG =
    '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M3 6H21M8 6V4C8 3.46957 8.21071 2.96086 8.58579 2.58579C8.96086 2.21071 9.46957 2 10 2H14C14.5304 2 15.0391 2.21071 15.4142 2.58579C15.7893 2.96086 16 3.46957 16 4V6M19 6V20C19 20.5304 18.7893 21.0391 18.4142 21.4142C18.0391 21.7893 17.5304 22 17 22H7C6.46957 22 5.96086 21.7893 5.58579 21.4142C5.21071 21.0391 5 20.5304 5 20V6H19Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>';

function getTz() {
    return getEffectiveTimezone(configTimezone, userTimezone);
}

function isMaintenanceWindowActive(startsAt, endsAt, now = new Date()) {
    const start = startsAt instanceof Date ? startsAt : new Date(startsAt);
    const end = endsAt instanceof Date ? endsAt : new Date(endsAt);
    return start.getTime() <= now.getTime() && now.getTime() < end.getTime();
}

function countActiveMaintenanceWindows(windows, now = new Date()) {
    return windows.filter((window) => {
        const start = new Date(window.starts_at);
        const end = new Date(window.ends_at);
        return isMaintenanceWindowActive(start, end, now);
    }).length;
}

function setActiveIndicatorCount(count) {
    const badge = document.getElementById("maintenance-active-count");
    const toggle = document.getElementById("maintenance-toggle");
    if (count > 0) {
        badge.textContent = String(count);
        badge.classList.remove("hidden");
        toggle.title = count === 1
            ? "Maintenance (1 active window)"
            : `Maintenance (${count} active windows)`;
    } else {
        badge.textContent = "";
        badge.classList.add("hidden");
        toggle.title = "Maintenance";
    }
}

function refreshActiveIndicatorFromRows() {
    if (!getIsAuthenticated()) {
        setActiveIndicatorCount(0);
        return;
    }
    const savedRows = rows.filter((row) => row.serverId);
    setActiveIndicatorCount(countActiveMaintenanceWindows(savedRows.map((row) => ({
        starts_at: row.start,
        ends_at: new Date(row.start.getTime() + row.durationMs),
    }))));
}

async function refreshActiveIndicator() {
    if (!getIsAuthenticated()) {
        setActiveIndicatorCount(0);
        return;
    }
    try {
        const data = await apiList();
        setActiveIndicatorCount(countActiveMaintenanceWindows(data));
    } catch (e) {
        console.warn("Failed to refresh maintenance active indicator", e);
    }
}

function startActiveIndicatorPolling() {
    if (activeIndicatorTimer !== null) return;
    activeIndicatorTimer = setInterval(() => {
        refreshActiveIndicator();
    }, ACTIVE_INDICATOR_POLL_MS);
}

function stopActiveIndicatorPolling() {
    if (activeIndicatorTimer === null) return;
    clearInterval(activeIndicatorTimer);
    activeIndicatorTimer = null;
}

const MAINTENANCE_TOGGLE_HTML =
    '<svg class="maintenance-icon" width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">' +
    '<path d="M8.30088 3.36909C8.17873 3.49371 8.11031 3.66126 8.11031 3.83576C8.11031 4.01026 8.17873 4.17781 8.30088 4.30243L9.36755 5.36909C9.49217 5.49125 9.65971 5.55967 9.83421 5.55967C10.0087 5.55967 10.1763 5.49125 10.3009 5.36909L12.8142 2.85576C13.1494 3.59655 13.2509 4.42192 13.1052 5.22186C12.9594 6.0218 12.5734 6.75832 11.9984 7.33328C11.4234 7.90824 10.6869 8.29432 9.88698 8.44007C9.08704 8.58582 8.26167 8.48432 7.52088 8.1491L2.91421 12.7558C2.649 13.021 2.28929 13.17 1.91421 13.17C1.53914 13.17 1.17943 13.021 0.914214 12.7558C0.648997 12.4905 0.5 12.1308 0.5 11.7558C0.5 11.3807 0.648997 11.021 0.914214 10.7558L5.52088 6.1491C5.18566 5.4083 5.08416 4.58294 5.22991 3.783C5.37566 2.98306 5.76174 2.24653 6.33669 1.67158C6.91165 1.09662 7.64818 0.710541 8.44812 0.564789C9.24806 0.419038 10.0734 0.520538 10.8142 0.855761L8.30755 3.36243L8.30088 3.36909Z" stroke="#FFFFFF" stroke-linecap="round" stroke-linejoin="round"/>' +
    '</svg>' +
    '<span id="maintenance-active-count" class="maintenance-active-count hidden" aria-hidden="true"></span>';

let footerToggleClickHandler = null;

function getPrivilegedFooterControlsContainer() {
    return document.getElementById("privileged-footer-controls");
}

function mountFooterToggle() {
    if (document.getElementById("maintenance-toggle")) {
        return;
    }
    const container = getPrivilegedFooterControlsContainer();
    if (!container) {
        return;
    }
    const toggle = document.createElement("button");
    toggle.id = "maintenance-toggle";
    toggle.className = "control-btn maintenance-control-btn";
    toggle.title = "Maintenance";
    toggle.type = "button";
    toggle.innerHTML = MAINTENANCE_TOGGLE_HTML;
    footerToggleClickHandler = () => {
        if (!getIsAuthenticated()) {
            return;
        }
        openMaintenanceModal();
    };
    toggle.addEventListener("click", footerToggleClickHandler);
    container.appendChild(toggle);
}

function unmountFooterToggle() {
    stopActiveIndicatorPolling();
    closeMaintenanceModal();
    setActiveIndicatorCount(0);
    const toggle = document.getElementById("maintenance-toggle");
    if (!toggle) {
        return;
    }
    if (footerToggleClickHandler) {
        toggle.removeEventListener("click", footerToggleClickHandler);
        footerToggleClickHandler = null;
    }
    toggle.remove();
}

function dtInTz(d) {
    return luxon.DateTime.fromJSDate(d, {zone: "utc"}).setZone(getTz());
}

function daysFromToday(d) {
    const dt = dtInTz(d);
    const now = dtInTz(new Date());
    return Math.round(dt.startOf("day").diff(now.startOf("day"), "days").days);
}

function formatShortDate(d) {
    return dtInTz(d).toFormat("MMM d");
}

function getDayLabel(d) {
    const days = daysFromToday(d);
    if (days === 0) return "Today";
    if (days === 1) return "Tomorrow";
    return dtInTz(d).toFormat("ccc");
}

function isWithinWeek(d) {
    const days = daysFromToday(d);
    return days >= 0 && days <= 7;
}

function formatRowTimeRange(start, durationMs) {
    const end = new Date(start.getTime() + durationMs);
    const s = dtInTz(start);
    const e = dtInTz(end);
    return `${s.toFormat("HH:mm")} - ${e.toFormat("HH:mm")}`;
}

function formatDurationMs(ms) {
    const totalMin = Math.round(ms / 60000);
    const h = Math.floor(totalMin / 60);
    const m = totalMin % 60;
    if (m === 0 && h > 0) return `${h}h`;
    if (h === 0) return `${m}m`;
    return `${h}h ${m}m`;
}

function buildDurationSpan(durationMs) {
    const span = document.createElement("span");
    span.className = "maintenance-row-duration";
    span.textContent = `(${formatDurationMs(durationMs)})`;
    return span;
}

function buildSecondaryLine(dateText, durationMs) {
    const line = document.createElement("div");
    line.className = "maintenance-row-time";
    if (dateText) {
        const date = document.createElement("span");
        date.className = "maintenance-row-time-date";
        date.textContent = dateText;
        line.appendChild(date);
    } else {
        line.classList.add("maintenance-row-time-end");
    }
    line.appendChild(buildDurationSpan(durationMs));
    return line;
}

function buildIntervalContent(row) {
    const wrap = document.createElement("div");
    wrap.className = "maintenance-row-interval-content";
    const timeRange = formatRowTimeRange(row.start, row.durationMs);
    const primary = document.createElement("div");
    primary.className = "maintenance-row-date";
    if (isWithinWeek(row.start)) {
        primary.textContent = `${getDayLabel(row.start)}, ${timeRange}`;
        wrap.append(primary, buildSecondaryLine(formatShortDate(row.start), row.durationMs));
    } else {
        primary.textContent = `${formatShortDate(row.start)}, ${timeRange}`;
        wrap.append(primary, buildSecondaryLine("", row.durationMs));
    }
    return wrap;
}

function validateMaintenanceRow(row) {
    return row.start && row.durationMs > 0 && row.matchers.length > 0 && row.comment.trim() !== "";
}

function validateMaintenanceRowInputs(el, row) {
    const matchersWrap = el.querySelector(".maintenance-matchers-wrap");
    const commentBox = el.querySelector(".maintenance-comment-panel .maintenance-panel-box");
    const ok = validateMaintenanceRow(row);
    if (matchersWrap) {
        matchersWrap.classList.toggle("maintenance-field-error", row.matchers.length === 0);
    }
    if (commentBox) {
        commentBox.classList.toggle("maintenance-field-error", row.comment.trim() === "");
    }
    if (!ok) return null;
    return {pdt: row.start, pdur: row.durationMs, matchers: [...row.matchers]};
}

function commitParsedRowInputs(row, parsed) {
    row.start = parsed.pdt;
    row.durationMs = parsed.pdur;
    row.matchers = parsed.matchers;
}

async function loadChainsConfig() {
    const res = await fetch(`${getBaseUrl()}/chains_config`, {credentials: "same-origin"});
    if (!res.ok) {
        throw new Error(`Failed to load chains config, status: ${res.status}`);
    }
    const data = await res.json();
    configTimezone = data.timezone;
    configWeekStart = data.week_start;
    messengerType = data.messenger_type;
    userTimezone = data.user_timezone;
}

function rowFromServer(data) {
    const start = new Date(data.starts_at);
    const end = new Date(data.ends_at);
    const matchers = [...data.matchers];
    return {
        localId: `m-${++rowSeq}`,
        serverId: data.id,
        start,
        durationMs: end.getTime() - start.getTime(),
        matchers,
        comment: data.comment || "",
        dirty: false,
        editing: false,
    };
}

function getActiveRow() {
    return rows.find((r) => !r.serverId || r.editing) || null;
}

function isRowEditing(row) {
    return getActiveRow() === row;
}

function rowToServerPayload(row) {
    return {
        start: row.start.toISOString(),
        durationMs: row.durationMs,
        matchers: row.matchers,
        comment: row.comment,
    };
}

async function apiList() {
    const baseUrl = getBaseUrl();
    const res = await fetch(`${baseUrl}/maintenance`, {credentials: "same-origin"});
    if (res.status === 401) return [];
    if (!res.ok) throw new Error(`GET /maintenance failed: ${res.status}`);
    return await res.json();
}

async function apiCreate(payload) {
    const baseUrl = getBaseUrl();
    const res = await fetch(`${baseUrl}/maintenance`, {
        method: "POST",
        credentials: "same-origin",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(payload),
    });
    if (res.status === 401) return null;
    if (!res.ok) throw new Error(`POST /maintenance failed: ${res.status}`);
    return await res.json();
}

async function apiUpdate(id, payload) {
    const baseUrl = getBaseUrl();
    const res = await fetch(`${baseUrl}/maintenance/${encodeURIComponent(id)}`, {
        method: "PUT",
        credentials: "same-origin",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(payload),
    });
    if (res.status === 401) return null;
    if (!res.ok) throw new Error(`PUT /maintenance/${id} failed: ${res.status}`);
    return await res.json();
}

async function apiDelete(id) {
    const baseUrl = getBaseUrl();
    const res = await fetch(`${baseUrl}/maintenance/${encodeURIComponent(id)}`, {
        method: "DELETE",
        credentials: "same-origin",
    });
    if (res.status === 401) return false;
    if (!res.ok && res.status !== 404) throw new Error(`DELETE /maintenance/${id} failed: ${res.status}`);
    return true;
}

async function saveRow(row) {
    const el = document.querySelector(`.maintenance-row[data-row-id="${row.localId}"]`);
    const parsed = el ? validateMaintenanceRowInputs(el, row) : null;
    if (!parsed) return;
    commitParsedRowInputs(row, parsed);
    try {
        const payload = rowToServerPayload(row);
        const saved = row.serverId
            ? await apiUpdate(row.serverId, payload)
            : await apiCreate(payload);
        if (!saved) return;
        row.serverId = saved.id;
        row.dirty = false;
        row.editing = false;
        delete row._snapshot;
        renderRows();
        refreshActiveIndicatorFromRows();
    } catch (e) {
        console.warn("Failed to save maintenance row", e);
    }
}

function restoreDeletedRow(snapshot) {
    rows.push({
        localId: snapshot.localId,
        serverId: snapshot.serverId,
        start: snapshot.start,
        durationMs: snapshot.durationMs,
        matchers: snapshot.matchers,
        comment: snapshot.comment,
        dirty: false,
        editing: false,
    });
    renderRows();
    refreshActiveIndicatorFromRows();
}

async function deleteRow(row) {
    const snapshot = {
        ...snapshotRow(row),
        localId: row.localId,
        serverId: row.serverId,
    };
    const serverId = row.serverId;

    rows = rows.filter((r) => r !== row);
    renderRows();
    refreshActiveIndicatorFromRows();

    if (!serverId) {
        return;
    }

    try {
        const deleted = await apiDelete(serverId);
        if (!deleted) {
            restoreDeletedRow(snapshot);
            showDeleteFailedWarning();
        }
    } catch (e) {
        console.warn("Failed to delete maintenance row", e);
        restoreDeletedRow(snapshot);
        showDeleteFailedWarning();
    }
}

function snapshotRow(row) {
    return {
        start: new Date(row.start),
        durationMs: row.durationMs,
        matchers: [...row.matchers],
        comment: row.comment,
    };
}

function discardRow(row) {
    if (!row.serverId) {
        rows = rows.filter((r) => r !== row);
        renderRows();
        return;
    }
    const s = row._snapshot;
    if (s) {
        row.start = new Date(s.start);
        row.durationMs = s.durationMs;
        row.matchers = [...s.matchers];
        row.comment = s.comment;
    }
    row.dirty = false;
    row.editing = false;
    delete row._snapshot;
    renderRows();
}

async function tryCancelEditing(row) {
    if (!row || !isRowEditing(row)) return;
    if (row.dirty) {
        showUnsavedChangesWarning();
        return;
    }
    discardRow(row);
}

function isClickOutsideActiveRow(target) {
    const active = getActiveRow();
    if (!active) return false;
    const overlay = document.getElementById("maintenance-interval-overlay");
    if (overlay && !overlay.classList.contains("hidden") && overlay.contains(target)) return false;
    const rowEl = document.querySelector(`.maintenance-row[data-row-id="${active.localId}"]`);
    return !rowEl?.contains(target);
}

function refreshRowSaveUi(row) {
    const el = document.querySelector(`.maintenance-row[data-row-id="${row.localId}"]`);
    if (!el) return;
    const save = el.querySelector(".maintenance-row-save");
    const cancel = el.querySelector(".maintenance-row-cancel");
    if (save) save.classList.toggle("hidden", !row.dirty);
    if (cancel) cancel.classList.toggle("hidden", !row.dirty);
}

function refreshAddButton() {
    const addBtn = document.getElementById("maintenance-add-row");
    if (!addBtn) return;
    addBtn.classList.toggle("hidden", !!getActiveRow() || pickerMode === "add");
}

function destroyIntervalCalendar() {
    if (intervalCalendar) {
        intervalCalendar.destroy();
        intervalCalendar = null;
    }
    const mount = document.getElementById("maintenance-interval-mount");
    if (mount) mount.innerHTML = "";
}

function scrollTimeFromDate(d) {
    return dtInTz(d).toFormat("HH:mm:ss");
}

function syncMatcherPlaceholder(row, input) {
    if (!input) return;
    input.placeholder = row.matchers.length === 0 ? 'service="elasticsearch"' : "";
}

function renderMatcherBadges(container, row, editable) {
    container.replaceChildren();
    const wrap = container.closest(".maintenance-matchers-wrap");
    for (const matcher of row.matchers) {
        if (!editable) {
            const badge = document.createElement("div");
            badge.className = "filter-badge";
            const text = document.createElement("span");
            text.className = "filter-badge-text";
            text.textContent = matcher;
            badge.appendChild(text);
            container.appendChild(badge);
            continue;
        }
        const badge = createEditableFilterBadge({
            value: matcher,
            onBadgeClick: (e) => e.stopPropagation(),
            onChange: (newVal, oldVal) => {
                if (row.matchers.includes(newVal)) return false;
                const idx = row.matchers.indexOf(oldVal);
                if (idx < 0) return false;
                row.matchers[idx] = newVal;
                row.dirty = true;
                refreshRowSaveUi(row);
                if (wrap) wrap.classList.toggle("maintenance-field-error", row.matchers.length === 0);
                return true;
            },
            onRemove: (val) => {
                row.matchers = row.matchers.filter((m) => m !== val);
                row.dirty = true;
                renderMatcherBadges(container, row, true);
                refreshRowSaveUi(row);
                if (wrap) wrap.classList.toggle("maintenance-field-error", row.matchers.length === 0);
            },
        });
        container.appendChild(badge);
    }
    syncMatcherPlaceholder(row, wrap?.querySelector(".maintenance-matcher-inline-input"));
}

function commitMatcherInput(row, input, badgeContainer, wrap) {
    const query = input.value.trim();
    if (!query) return false;
    const formatted = validateAndFormatFilter(query);
    if (!formatted) {
        input.classList.add("maintenance-field-error");
        return false;
    }
    if (!row.matchers.includes(formatted)) {
        row.matchers.push(formatted);
        row.dirty = true;
        renderMatcherBadges(badgeContainer, row, true);
        refreshRowSaveUi(row);
    }
    input.value = "";
    input.classList.remove("maintenance-field-error");
    if (wrap) wrap.classList.toggle("maintenance-field-error", row.matchers.length === 0);
    return true;
}

function buildMatchersPanel(row, editable) {
    const panel = document.createElement("div");
    panel.className = "maintenance-panel maintenance-matchers-wrap";

    const label = document.createElement("span");
    label.className = "maintenance-panel-label";
    label.textContent = "Matchers";

    const box = document.createElement("div");
    box.className = "maintenance-panel-box maintenance-matchers-box";

    const badgeContainer = document.createElement("div");
    badgeContainer.className = "maintenance-matchers-badges";
    renderMatcherBadges(badgeContainer, row, editable);

    box.appendChild(badgeContainer);
    if (editable) {
        const inp = document.createElement("input");
        inp.type = "text";
        inp.className = "maintenance-matcher-inline-input";
        syncMatcherPlaceholder(row, inp);
        inp.setAttribute("aria-label", "Add matcher");
        inp.addEventListener("keydown", (e) => {
            if (e.key === "Enter") {
                e.preventDefault();
                commitMatcherInput(row, inp, badgeContainer, panel);
            }
        });
        inp.addEventListener("blur", () => commitMatcherInput(row, inp, badgeContainer, panel));
        inp.addEventListener("input", () => inp.classList.remove("maintenance-field-error"));
        box.addEventListener("click", () => inp.focus());
        box.appendChild(inp);
    }
    panel.appendChild(label);
    panel.appendChild(box);
    return panel;
}

function buildCommentPanel(row, editable) {
    const panel = document.createElement("div");
    panel.className = "maintenance-panel maintenance-comment-panel";

    const label = document.createElement("span");
    label.className = "maintenance-panel-label";
    label.textContent = "Comment";

    const box = document.createElement("div");
    box.className = "maintenance-panel-box";
    if (editable) {
        const ta = document.createElement("textarea");
        ta.className = "maintenance-comment-input";
        ta.value = row.comment;
        ta.addEventListener("input", () => {
            row.comment = ta.value;
            row.dirty = true;
            refreshRowSaveUi(row);
        });
        box.appendChild(ta);
    } else {
        const view = document.createElement("div");
        view.className = "maintenance-comment-view";
        view.textContent = row.comment;
        box.appendChild(view);
    }
    panel.appendChild(label);
    panel.appendChild(box);
    return panel;
}

function buildRowInterval(row, editing) {
    const interval = document.createElement("div");
    interval.className = "maintenance-row-interval";
    const intervalContent = buildIntervalContent(row);
    if (editing) {
        const bCal = document.createElement("button");
        bCal.type = "button";
        bCal.className = "maintenance-interval-edit-btn";
        bCal.title = "Edit interval";
        bCal.innerHTML = CAL_BTN_SVG;
        bCal.addEventListener("click", () => openIntervalPickerEdit(row.localId));
        interval.append(bCal, intervalContent);
    } else {
        interval.appendChild(intervalContent);
    }
    return interval;
}

function buildEditingRowActions(row) {
    const actions = document.createElement("div");
    actions.className = "maintenance-row-actions";

    const bCancel = document.createElement("button");
    bCancel.type = "button";
    bCancel.className = "maintenance-row-cancel";
    bCancel.title = "Cancel";
    bCancel.innerHTML = CANCEL_BTN_SVG;
    bCancel.classList.toggle("hidden", !row.dirty);
    bCancel.addEventListener("click", () => discardRow(row));

    const bSave = document.createElement("button");
    bSave.type = "button";
    bSave.className = "maintenance-row-save";
    bSave.title = "Save";
    bSave.innerHTML = SAVE_BTN_SVG;
    bSave.classList.toggle("hidden", !row.dirty);
    bSave.addEventListener("click", () => saveRow(row));
    actions.append(bCancel, bSave);

    if (row.serverId) {
        const bDelete = document.createElement("button");
        bDelete.type = "button";
        bDelete.className = "maintenance-row-delete";
        bDelete.title = "Delete";
        bDelete.innerHTML = DELETE_BTN_SVG;
        bDelete.addEventListener("click", (e) => {
            e.stopPropagation();
            deleteRow(row);
        });
        actions.appendChild(bDelete);
    }
    return actions;
}

function buildViewRowActions(row, active) {
    const actions = document.createElement("div");
    actions.className = "maintenance-row-actions";
    if (active || !row.serverId) {
        return actions;
    }

    const bEdit = document.createElement("button");
    bEdit.type = "button";
    bEdit.className = "maintenance-row-edit";
    bEdit.title = "Edit";
    bEdit.innerHTML = EDIT_BTN_SVG;
    bEdit.addEventListener("click", (e) => {
        e.stopPropagation();
        for (const r of rows) r.editing = false;
        row._snapshot = snapshotRow(row);
        row.editing = true;
        row.dirty = false;
        renderRows();
    });
    actions.appendChild(bEdit);
    return actions;
}

function buildMaintenanceRowElement(row, active) {
    const editing = isRowEditing(row);
    const el = document.createElement("div");
    el.className = "maintenance-row"
        + (editing ? " maintenance-row-new" : "")
        + (active && active !== row ? " maintenance-row-locked" : "");
    el.dataset.rowId = row.localId;

    const actions = editing ? buildEditingRowActions(row) : buildViewRowActions(row, active);
    el.append(
        buildRowInterval(row, editing),
        buildMatchersPanel(row, editing),
        buildCommentPanel(row, editing),
        actions,
    );
    return el;
}

function renderRows() {
    const list = document.getElementById("maintenance-rows");
    if (!list) return;
    list.replaceChildren();
    const sorted = [...rows].sort((a, b) => a.start.getTime() - b.start.getTime());
    const active = getActiveRow();
    for (const row of sorted) {
        const el = buildMaintenanceRowElement(row, active);
        list.appendChild(el);

        if (!row.serverId) {
            const inlineInp = el.querySelector(".maintenance-matcher-inline-input");
            if (inlineInp) inlineInp.focus();
        }
    }
    refreshAddButton();
}

function findRow(localId) {
    return rows.find((r) => r.localId === localId);
}

function closeIntervalPicker() {
    destroyIntervalCalendar();
    pickerMode = null;
    pickerTargetId = null;
    const overlay = document.getElementById("maintenance-interval-overlay");
    if (overlay) overlay.classList.add("hidden");
    refreshAddButton();
}

function applyIntervalSelection(start, durationMs) {
    if (pickerMode === "add") {
        rows.push({
            localId: `m-${++rowSeq}`,
            serverId: null,
            start: new Date(start),
            durationMs,
            matchers: [],
            comment: "",
            dirty: true,
        });
    } else if (pickerMode === "edit" && pickerTargetId) {
        const row = findRow(pickerTargetId);
        if (row) {
            row.start = new Date(start);
            row.durationMs = durationMs;
            row.dirty = true;
        }
    }
    closeIntervalPicker();
    renderRows();
}

function openIntervalPickerUi(initialStart, initialDurationMs) {
    const overlay = document.getElementById("maintenance-interval-overlay");
    const mount = document.getElementById("maintenance-interval-mount");
    overlay.classList.remove("hidden");
    destroyIntervalCalendar();
    intervalCalendar = new FullCalendar.Calendar(mount, {
        initialView: "timeGridWeek",
        initialDate: initialStart,
        headerToolbar: {left: "title", center: "", right: "today prev,next"},
        firstDay: parseWeekStart(configWeekStart),
        height: "100%",
        scrollTime: scrollTimeFromDate(initialStart),
        scrollTimeReset: false,
        slotMinHeight: 36,
        slotDuration: "00:15:00",
        snapDuration: "00:15:00",
        slotLabelInterval: "01:00:00",
        allDaySlot: false,
        nowIndicator: true,
        selectable: true,
        selectMirror: true,
        timeZone: getTz(),
        dayHeaderFormat: {weekday: "short", day: "numeric", omitCommas: false},
        slotLabelFormat: {
            hour: "2-digit",
            minute: "2-digit",
            hour12: false,
        },
        weekNumbers: true,
        events: [],
        select(info) {
            const ms = info.end.getTime() - info.start.getTime();
            if (ms <= 0) {
                intervalCalendar?.unselect();
                return;
            }
            applyIntervalSelection(info.start, ms);
            intervalCalendar?.unselect();
        },
    });
    intervalCalendar.render();
    setTimeout(() => intervalCalendar?.updateSize(), 80);
}

function openIntervalPickerAdd() {
    const start = new Date();
    start.setSeconds(0, 0);
    pickerMode = "add";
    pickerTargetId = null;
    refreshAddButton();
    openIntervalPickerUi(start, 24 * 60 * 60 * 1000);
}

function openIntervalPickerEdit(localId) {
    const row = findRow(localId);
    if (!row) return;
    pickerMode = "edit";
    pickerTargetId = localId;
    openIntervalPickerUi(row.start, row.durationMs);
}

async function loadRows() {
    try {
        const data = await apiList();
        rows = data.map(rowFromServer);
    } catch (e) {
        console.warn("Failed to load maintenance windows", e);
        rows = [];
    }
}

function hasUnsavedMaintenance() {
    return rows.some((r) => r.dirty);
}

function showTransientNotification(message) {
    const notification = document.createElement("div");
    notification.className = "overlap-notification";
    notification.textContent = message;
    document.body.appendChild(notification);
    setTimeout(() => notification.classList.add("show"), 10);
    setTimeout(() => {
        notification.classList.remove("show");
        notification.classList.add("hide");
        setTimeout(() => notification.remove(), 300);
    }, 4000);
}

function showUnsavedChangesWarning() {
    showTransientNotification("Unsaved changes");
}

function showDeleteFailedWarning() {
    showTransientNotification("Failed to delete maintenance window");
}

function closeMaintenanceModal() {
    closeIntervalPicker();
    const modal = document.getElementById("maintenance-modal");
    if (modal) modal.classList.remove("visible");
}

function tryCloseMaintenanceModal() {
    if (hasUnsavedMaintenance()) {
        showUnsavedChangesWarning();
        return;
    }
    closeMaintenanceModal();
}

async function openMaintenanceModal() {
    if (!getIsAuthenticated()) {
        return;
    }
    const modal = document.getElementById("maintenance-modal");
    if (!modal) return;
    await loadChainsConfig();
    syncTimezoneSelects(configTimezone, messengerType, userTimezone);
    modal.classList.add("visible");
    await loadRows();
    renderRows();
    refreshActiveIndicatorFromRows();
}

export const MaintenanceManager = {
    initialized: false,

    init() {
        if (this.initialized) return;
        const modal = document.getElementById("maintenance-modal");
        const closeBtn = modal?.querySelector(".maintenance-modal-close");
        const addBtn = document.getElementById("maintenance-add-row");
        const intervalClose = document.getElementById("maintenance-interval-close");
        const intervalOverlay = document.getElementById("maintenance-interval-overlay");
        const tzSelect = document.getElementById("maintenance-timezone-select");
        if (!modal || !closeBtn || !addBtn || !intervalClose || !intervalOverlay || !tzSelect) return;

        tzSelect.addEventListener("change", (e) => {
            setTimezoneMode(e.target.value);
            syncTimezoneSelects(configTimezone, messengerType, userTimezone);
            renderRows();
            if (intervalCalendar) {
                intervalCalendar.setOption("timeZone", getTz());
            }
        });

        closeBtn.addEventListener("click", () => tryCloseMaintenanceModal());
        modal.addEventListener("click", (e) => {
            if (e.target === modal) tryCloseMaintenanceModal();
        });
        const modalContent = modal.querySelector(".maintenance-modal-content");
        modalContent?.addEventListener("click", (e) => {
            if (!modal.classList.contains("visible")) return;
            if (e.target.closest(".chains-modal-header")) return;
            const active = getActiveRow();
            if (!active || !isClickOutsideActiveRow(e.target)) return;
            tryCancelEditing(active);
        });
        intervalClose.addEventListener("click", () => closeIntervalPicker());
        intervalOverlay.addEventListener("click", (e) => {
            if (e.target === intervalOverlay) closeIntervalPicker();
        });
        addBtn.addEventListener("click", () => openIntervalPickerAdd());
        document.addEventListener("keydown", (e) => {
            if (e.key !== "Escape") return;
            if (!modal.classList.contains("visible")) return;
            const overlay = document.getElementById("maintenance-interval-overlay");
            if (overlay && !overlay.classList.contains("hidden")) {
                closeIntervalPicker();
                return;
            }
            const active = getActiveRow();
            if (active) {
                tryCancelEditing(active);
                return;
            }
            tryCloseMaintenanceModal();
        });
        onAuthChange((authenticated) => {
            if (authenticated) {
                mountFooterToggle();
                refreshActiveIndicator();
                startActiveIndicatorPolling();
            } else {
                unmountFooterToggle();
            }
        });
        if (getIsAuthenticated()) {
            mountFooterToggle();
            refreshActiveIndicator();
            startActiveIndicatorPolling();
        }
        this.initialized = true;
    },
};
