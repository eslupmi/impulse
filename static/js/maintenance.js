import {getSocket} from "./websocket.js";
import {getBaseUrl, parseWeekStart} from "./utils.js";
import {attachNavListener, getSharedCalendarOptions, updateMonthCalendarWeekHighlight} from "./calendar_shared.js";
import {createEditableFilterBadge, validateAndFormatFilter} from "./filters.js";
import {getIsAuthenticated, onAuthChange} from "./auth.js";
import {
    captureCalendarViewAnchor,
    getEffectiveTimezone,
    onTimezoneChange,
    reformatDateTimeInput,
    syncTimezoneSelects,
    updateTimezoneConfig,
} from "./ui_timezone.js";

let calendar = null;
let monthCalendar = null;
let initialized = false;
let cachedWindows = [];
let windowsPromiseResolve = null;
let savePromiseResolve = null;
let currentWindowId = null;
let pendingSelectStart = null;
let pendingSelectEnd = null;
let modalMatchers = [];
let configTimezone = "UTC";
let configWeekStart = "Mon";
let messengerType = "";
let userTimezone = null;
let activeIndicatorTimer = null;

const ACTIVE_INDICATOR_POLL_MS = 60000;

const MAINTENANCE_TOGGLE_HTML =
    '<svg class="maintenance-icon" width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">' +
    '<path d="M8.30088 3.36909C8.17873 3.49371 8.11031 3.66126 8.11031 3.83576C8.11031 4.01026 8.17873 4.17781 8.30088 4.30243L9.36755 5.36909C9.49217 5.49125 9.65971 5.55967 9.83421 5.55967C10.0087 5.55967 10.1763 5.49125 10.3009 5.36909L12.8142 2.85576C13.1494 3.59655 13.2509 4.42192 13.1052 5.22186C12.9594 6.0218 12.5734 6.75832 11.9984 7.33328C11.4234 7.90824 10.6869 8.29432 9.88698 8.44007C9.08704 8.58582 8.26167 8.48432 7.52088 8.1491L2.91421 12.7558C2.649 13.021 2.28929 13.17 1.91421 13.17C1.53914 13.17 1.17943 13.021 0.914214 12.7558C0.648997 12.4905 0.5 12.1308 0.5 11.7558C0.5 11.3807 0.648997 11.021 0.914214 10.7558L5.52088 6.1491C5.18566 5.4083 5.08416 4.58294 5.22991 3.783C5.37566 2.98306 5.76174 2.24653 6.33669 1.67158C6.91165 1.09662 7.64818 0.710541 8.44812 0.564789C9.24806 0.419038 10.0734 0.520538 10.8142 0.855761L8.30755 3.36243L8.30088 3.36909Z" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round"/>' +
    '</svg>' +
    '<span id="maintenance-active-count" class="maintenance-active-count hidden" aria-hidden="true"></span>';

let footerToggleClickHandler = null;

function getTz() {
    return getEffectiveTimezone(configTimezone, userTimezone);
}

function truncateMatcher(matcher, maxLen = 24) {
    if (!matcher) return "";
    if (matcher.length <= maxLen) return matcher;
    return matcher.slice(0, maxLen - 3) + "...";
}

function eventTitleForWindow(window) {
    const matchers = window.matchers || [];
    return truncateMatcher(matchers[0] || window.comment || "Maintenance");
}

function isMaintenanceWindowActive(startIso, endIso, now = new Date()) {
    const start = new Date(startIso);
    const end = new Date(endIso);
    return start.getTime() <= now.getTime() && now.getTime() < end.getTime();
}

function countActiveMaintenanceWindows(windows, now = new Date()) {
    return windows.filter((w) => isMaintenanceWindowActive(w.start, w.end, now)).length;
}

function setActiveIndicatorCount(count) {
    const badge = document.getElementById("maintenance-active-count");
    const toggle = document.getElementById("maintenance-toggle");
    if (!toggle) return;
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

function refreshActiveIndicatorFromCache() {
    if (!getIsAuthenticated()) {
        setActiveIndicatorCount(0);
        return;
    }
    setActiveIndicatorCount(countActiveMaintenanceWindows(cachedWindows));
}

async function refreshActiveIndicator() {
    if (!getIsAuthenticated()) {
        setActiveIndicatorCount(0);
        return;
    }
    try {
        await loadWindows();
        refreshActiveIndicatorFromCache();
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

function mountFooterToggle() {
    if (document.getElementById("maintenance-toggle")) return;
    const container = document.getElementById("privileged-footer-controls");
    if (!container) return;
    const toggle = document.createElement("button");
    toggle.id = "maintenance-toggle";
    toggle.className = "control-btn maintenance-control-btn";
    toggle.title = "Maintenance";
    toggle.type = "button";
    toggle.innerHTML = MAINTENANCE_TOGGLE_HTML;
    footerToggleClickHandler = () => {
        if (getIsAuthenticated()) openMaintenanceModal();
    };
    toggle.addEventListener("click", footerToggleClickHandler);
    container.appendChild(toggle);
    refreshActiveIndicator();
}

function unmountFooterToggle() {
    stopActiveIndicatorPolling();
    closeMaintenanceModal();
    setActiveIndicatorCount(0);
    const toggle = document.getElementById("maintenance-toggle");
    if (!toggle) return;
    if (footerToggleClickHandler) {
        toggle.removeEventListener("click", footerToggleClickHandler);
        footerToggleClickHandler = null;
    }
    toggle.remove();
}

function showNotification(message) {
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

async function loadChainsConfig() {
    const res = await fetch(`${getBaseUrl()}/chains_config`, {credentials: "same-origin"});
    if (!res.ok) throw new Error(`Failed to load chains config, status: ${res.status}`);
    const data = await res.json();
    configTimezone = data.timezone;
    configWeekStart = data.week_start;
    messengerType = data.messenger_type;
    userTimezone = data.user_timezone;
    updateTimezoneConfig({configTimezone, messengerType, userTimezone});
}

globalThis.handleMaintenanceData = function(data) {
    cachedWindows = Array.isArray(data) ? data : [];
    if (windowsPromiseResolve) {
        windowsPromiseResolve(cachedWindows);
        windowsPromiseResolve = null;
    }
    refreshActiveIndicatorFromCache();
};

globalThis.handleMaintenanceSaved = function(success) {
    if (savePromiseResolve) {
        savePromiseResolve(!!success);
        savePromiseResolve = null;
    }
    if (!success) {
        showNotification("Failed to save maintenance windows");
    }
};

globalThis.handleMaintenanceError = function(detail) {
    if (windowsPromiseResolve) {
        windowsPromiseResolve(cachedWindows);
        windowsPromiseResolve = null;
    }
    showNotification(detail || "Maintenance error");
};

async function loadWindows() {
    const socket = getSocket();
    if (!socket || socket.readyState !== WebSocket.OPEN) {
        return cachedWindows;
    }
    return new Promise((resolve) => {
        windowsPromiseResolve = resolve;
        socket.send(JSON.stringify({event: "request_maintenance"}));
        setTimeout(() => {
            if (windowsPromiseResolve === resolve) {
                windowsPromiseResolve = null;
                resolve(cachedWindows);
            }
        }, 5000);
    });
}

async function saveWindows(windows) {
    cachedWindows = windows;
    const socket = getSocket();
    if (!socket || socket.readyState !== WebSocket.OPEN) {
        console.error("WebSocket not connected, cannot save maintenance windows");
        return false;
    }
    return new Promise((resolve) => {
        savePromiseResolve = resolve;
        socket.send(JSON.stringify({event: "save_maintenance", data: windows}));
        setTimeout(() => {
            if (savePromiseResolve === resolve) {
                savePromiseResolve = null;
                resolve(false);
            }
        }, 5000);
    });
}

function formatDateTime(date) {
    const timezone = getTz();
    const pad = (n) => n.toString().padStart(2, "0");
    if (typeof luxon === "undefined") {
        const d = new Date(date);
        return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}, ${pad(d.getHours())}:${pad(d.getMinutes())}`;
    }
    const dt = luxon.DateTime.fromISO(new Date(date).toISOString(), {zone: "utc"}).setZone(timezone);
    return `${dt.year}-${pad(dt.month)}-${pad(dt.day)}, ${pad(dt.hour)}:${pad(dt.minute)}`;
}

function parseDateTime(dateStr) {
    const match = dateStr.match(/(\d{4})-(\d{2})-(\d{2}),\s*(\d{2}):(\d{2})/);
    if (!match) return null;
    const [, year, month, day, hour, minute] = match;
    const timezone = getTz();
    if (typeof luxon === "undefined") {
        return new Date(+year, +month - 1, +day, +hour, +minute).toISOString();
    }
    return luxon.DateTime.fromObject(
        {year: +year, month: +month, day: +day, hour: +hour, minute: +minute, second: 0},
        {zone: timezone},
    ).toUTC().toISO();
}

function windowsToEvents(windows) {
    const eventBg = getComputedStyle(document.documentElement).getPropertyValue("--maintenance-event-bg").trim()
        || getComputedStyle(document.documentElement).getPropertyValue("--chain-event-bg").trim();
    const eventBorder = getComputedStyle(document.documentElement).getPropertyValue("--maintenance-event-border").trim()
        || getComputedStyle(document.documentElement).getPropertyValue("--chain-event-border").trim();

    return windows.map((window) => ({
        id: window.id,
        title: eventTitleForWindow(window),
        start: window.start,
        end: window.end,
        extendedProps: {
            matchers: window.matchers || [],
            comment: window.comment || "",
            created_by: window.created_by || null,
        },
        display: "block",
        backgroundColor: eventBg,
        borderColor: eventBorder,
        classNames: ["maintenance-calendar-event"],
    }));
}

function refreshCalendarEvents(windows) {
    const events = windowsToEvents(windows);
    if (calendar) {
        calendar.removeAllEvents();
        calendar.addEventSource(events);
    }
    if (monthCalendar) {
        monthCalendar.removeAllEvents();
        monthCalendar.addEventSource(events);
    }
}

function updateWeekNumberDisplay() {
    if (!calendar) return;
    const weekNumber = calendar.view.dateEnv.computeWeekNumber(calendar.view.currentStart);
    const el = document.getElementById("maintenance-week-number-display");
    if (el) el.textContent = `Week ${weekNumber}`;
}

function updateCurrentWeekHighlight() {
    updateMonthCalendarWeekHighlight(calendar, monthCalendar);
}

function bindCalendarNavButtons() {
    attachNavListener(document.getElementById("maintenance-calendar-prev"), () => {
        calendar.prev();
        setTimeout(updateWeekNumberDisplay, 50);
    });
    attachNavListener(document.getElementById("maintenance-calendar-next"), () => {
        calendar.next();
        setTimeout(updateWeekNumberDisplay, 50);
    });
    attachNavListener(document.getElementById("maintenance-calendar-today"), () => {
        calendar.today();
        setTimeout(updateWeekNumberDisplay, 50);
    });
}

function buildMainCalendarOptions(events, firstDay, timezone) {
    return {
        initialView: "timeGridWeek",
        headerToolbar: false,
        nowIndicator: true,
        slotMinHeight: 60,
        scrollTimeReset: false,
        allDaySlot: false,
        ...getSharedCalendarOptions(firstDay, timezone),
        dayHeaderFormat: {weekday: "short", day: "numeric", omitCommas: false},
        slotLabelFormat: {hour: "2-digit", minute: "2-digit", hour12: false},
        slotDuration: "00:30:00",
        slotLabelInterval: "01:00:00",
        editable: true,
        selectable: true,
        selectMirror: true,
        dayMaxEvents: true,
        eventContent(arg) {
            const title = arg.event.title || "";
            return {
                html: `<div class="fc-event-title maintenance-event-title">${title}</div>`,
            };
        },
        eventDidMount(arg) {
            arg.el.classList.add("maintenance-calendar-event");
        },
        eventTimeFormat: {hour: "2-digit", minute: "2-digit", hour12: false},
        displayEventTime: false,
        events,

        select(info) {
            pendingSelectStart = info.start;
            pendingSelectEnd = info.end;
            openWindowModal();
            document.getElementById("maintenance-window-start").value = formatDateTime(info.start);
            if (info.end) {
                document.getElementById("maintenance-window-end").value = formatDateTime(info.end);
            }
            calendar.unselect();
        },

        eventClick(info) {
            const props = info.event.extendedProps || {};
            openWindowModal({
                id: info.event.id,
                start: info.event.start.toISOString(),
                end: info.event.end?.toISOString() ?? null,
                matchers: props.matchers || [],
                comment: props.comment || "",
                created_by: props.created_by || null,
            });
        },

        eventDrop: handleEventTimeChange,
        eventResize: handleEventTimeChange,

        datesSet() {
            updateWeekNumberDisplay();
            if (monthCalendar) {
                monthCalendar.gotoDate(calendar.view.activeStart);
                monthCalendar.render();
                setTimeout(updateCurrentWeekHighlight, 100);
            }
        },
    };
}

function buildMonthCalendarOptions(events, firstDay, timezone) {
    return {
        initialView: "dayGridMonth",
        headerToolbar: {left: "title", center: "", right: "prev,next"},
        ...getSharedCalendarOptions(firstDay, timezone),
        height: "auto",
        fixedWeekCount: false,
        showNonCurrentDates: false,
        events,
        dateClick(info) {
            calendar.gotoDate(info.dateStr);
        },
        dayCellContent(info) {
            return {html: `<div class="day-number">${info.dayNumberText}</div>`};
        },
        datesSet() {
            setTimeout(updateCurrentWeekHighlight, 50);
        },
    };
}

async function handleEventTimeChange(info) {
    const windows = await loadWindows();
    const index = windows.findIndex((w) => w.id === info.event.id);
    if (index === -1) {
        info.revert();
        return;
    }
    windows[index] = {
        ...windows[index],
        start: info.event.start.toISOString(),
        end: info.event.end?.toISOString() ?? windows[index].end,
    };
    const saved = await saveWindows(windows);
    if (!saved) {
        info.revert();
        return;
    }
    refreshCalendarEvents(windows);
    refreshActiveIndicatorFromCache();
}

function renderMatcherBadges() {
    const container = document.getElementById("maintenance-matchers-badges");
    const input = document.getElementById("maintenance-matcher-input");
    const wrap = document.getElementById("maintenance-matchers-wrap");
    if (!container) return;
    container.replaceChildren();
    for (const matcher of modalMatchers) {
        const badge = createEditableFilterBadge({
            value: matcher,
            onBadgeClick: (e) => e.stopPropagation(),
            onChange: (newVal, oldVal) => {
                if (modalMatchers.includes(newVal)) return false;
                const idx = modalMatchers.indexOf(oldVal);
                if (idx < 0) return false;
                modalMatchers[idx] = newVal;
                renderMatcherBadges();
                return true;
            },
            onRemove: (val) => {
                modalMatchers = modalMatchers.filter((m) => m !== val);
                renderMatcherBadges();
            },
        });
        container.appendChild(badge);
    }
    if (input) {
        input.placeholder = modalMatchers.length === 0 ? 'service="elasticsearch"' : "";
    }
    if (wrap) {
        wrap.classList.toggle("maintenance-field-error", modalMatchers.length === 0);
    }
}

function commitMatcherInput() {
    const input = document.getElementById("maintenance-matcher-input");
    const wrap = document.getElementById("maintenance-matchers-wrap");
    if (!input) return;
    const query = input.value.trim();
    if (!query) return;
    const formatted = validateAndFormatFilter(query);
    if (!formatted) {
        input.classList.add("maintenance-field-error");
        return;
    }
    if (!modalMatchers.includes(formatted)) {
        modalMatchers.push(formatted);
        renderMatcherBadges();
    }
    input.value = "";
    input.classList.remove("maintenance-field-error");
    if (wrap) wrap.classList.toggle("maintenance-field-error", modalMatchers.length === 0);
}

function openWindowModal(windowData = null) {
    const modal = document.getElementById("maintenance-window-modal");
    const title = document.getElementById("maintenance-window-modal-title");
    const startInput = document.getElementById("maintenance-window-start");
    const endInput = document.getElementById("maintenance-window-end");
    const commentInput = document.getElementById("maintenance-window-comment");
    const deleteBtn = document.getElementById("maintenance-window-delete-btn");

    if (windowData) {
        currentWindowId = windowData.id;
        title.textContent = "Edit maintenance";
        startInput.value = formatDateTime(windowData.start);
        endInput.value = windowData.end ? formatDateTime(windowData.end) : "";
        commentInput.value = windowData.comment || "";
        modalMatchers = [...(windowData.matchers || [])];
        deleteBtn.classList.remove("hidden");
    } else {
        currentWindowId = null;
        title.textContent = "New maintenance";
        if (!pendingSelectStart) {
            startInput.value = "";
            endInput.value = "";
        }
        commentInput.value = "";
        modalMatchers = [];
        deleteBtn.classList.add("hidden");
    }
    renderMatcherBadges();
    modal.classList.add("visible");
}

function closeWindowModal() {
    document.getElementById("maintenance-window-modal")?.classList.remove("visible");
    currentWindowId = null;
    pendingSelectStart = null;
    pendingSelectEnd = null;
    modalMatchers = [];
}

function validateWindowModalInput() {
    const startStr = document.getElementById("maintenance-window-start").value.trim();
    const endStr = document.getElementById("maintenance-window-end").value.trim();
    const comment = document.getElementById("maintenance-window-comment").value.trim();
    const commentBox = document.getElementById("maintenance-window-comment");
    const matchersWrap = document.getElementById("maintenance-matchers-wrap");

    if (!startStr || !endStr) {
        showNotification("Start and end are required");
        return null;
    }
    const start = parseDateTime(startStr);
    const end = parseDateTime(endStr);
    if (!start || !end) {
        showNotification("Invalid date format");
        return null;
    }
    if (new Date(end) <= new Date(start)) {
        showNotification("End must be after start");
        return null;
    }
    if (modalMatchers.length === 0) {
        matchersWrap?.classList.add("maintenance-field-error");
        showNotification("At least one matcher is required");
        return null;
    }
    if (!comment) {
        commentBox?.classList.add("maintenance-field-error");
        showNotification("Comment is required");
        return null;
    }
    commentBox?.classList.remove("maintenance-field-error");
    matchersWrap?.classList.remove("maintenance-field-error");
    return {start, end, comment, matchers: [...modalMatchers]};
}

async function saveWindowModal() {
    const input = validateWindowModalInput();
    if (!input) return;

    const windows = await loadWindows();
    if (currentWindowId) {
        const index = windows.findIndex((w) => w.id === currentWindowId);
        if (index === -1) return;
        windows[index] = {
            ...windows[index],
            start: input.start,
            end: input.end,
            matchers: input.matchers,
            comment: input.comment,
        };
    } else {
        windows.push({
            id: crypto.randomUUID(),
            start: input.start,
            end: input.end,
            matchers: input.matchers,
            comment: input.comment,
            created_by: null,
        });
    }

    const saved = await saveWindows(windows);
    if (!saved) return;
    closeWindowModal();
    refreshCalendarEvents(windows);
    refreshActiveIndicatorFromCache();
}

async function deleteWindowModal() {
    if (!currentWindowId) return;
    const windows = (await loadWindows()).filter((w) => w.id !== currentWindowId);
    const saved = await saveWindows(windows);
    if (!saved) return;
    closeWindowModal();
    refreshCalendarEvents(windows);
    refreshActiveIndicatorFromCache();
}

function refreshMaintenanceModalDateTimes({previousTimezone, configTimezone: tz, userTimezone: userTz}) {
    const modal = document.getElementById("maintenance-window-modal");
    if (!modal?.classList.contains("visible")) {
        return;
    }
    reformatDateTimeInput(document.getElementById("maintenance-window-start"), previousTimezone, tz, userTz);
    reformatDateTimeInput(document.getElementById("maintenance-window-end"), previousTimezone, tz, userTz);
}

async function updateCalendarTimezone() {
    const modal = document.getElementById("maintenance-modal");
    if (!modal?.classList.contains("visible") || !initialized) {
        return;
    }

    const calendarEl = document.getElementById("maintenance-calendar");
    const monthCalendarEl = document.getElementById("maintenance-month-calendar");
    if (!calendarEl || !monthCalendarEl) {
        return;
    }

    const timegridScroller = document.querySelector("#maintenance-calendar .fc-timegrid-body .fc-scroller");
    const scrollTop = timegridScroller ? timegridScroller.scrollTop : 0;
    const anchorDate = captureCalendarViewAnchor(calendar);
    const firstDay = parseWeekStart(configWeekStart);
    const timezone = getTz();
    const windows = cachedWindows.length ? cachedWindows : await loadWindows();
    const events = windowsToEvents(windows);

    if (calendar) {
        calendar.destroy();
    }
    if (monthCalendar) {
        monthCalendar.destroy();
    }

    const calendarOptions = buildMainCalendarOptions(events, firstDay, timezone);
    const monthOptions = buildMonthCalendarOptions(events, firstDay, timezone);
    if (anchorDate) {
        calendarOptions.initialDate = anchorDate;
        monthOptions.initialDate = anchorDate;
    }

    calendar = new FullCalendar.Calendar(calendarEl, calendarOptions);
    monthCalendar = new FullCalendar.Calendar(monthCalendarEl, monthOptions);
    calendar.render();
    monthCalendar.render();

    if (anchorDate) {
        calendar.gotoDate(anchorDate);
        monthCalendar.gotoDate(anchorDate);
    }

    bindCalendarNavButtons();
    updateWeekNumberDisplay();
    updateCurrentWeekHighlight();

    setTimeout(() => {
        calendar.updateSize();
        monthCalendar.updateSize();
        if (timegridScroller) {
            timegridScroller.scrollTop = scrollTop;
        }
    }, 50);
}

async function initializeCalendars() {
    if (typeof FullCalendar === "undefined") {
        console.error("FullCalendar is not available");
        return;
    }

    const calendarEl = document.getElementById("maintenance-calendar");
    const monthCalendarEl = document.getElementById("maintenance-month-calendar");
    if (!calendarEl || !monthCalendarEl) return;

    const firstDay = parseWeekStart(configWeekStart);
    const timezone = getTz();
    const windows = await loadWindows();
    const events = windowsToEvents(windows);

    if (initialized && calendar && monthCalendar) {
        calendar.setOption("timeZone", timezone);
        monthCalendar.setOption("timeZone", timezone);
        refreshCalendarEvents(windows);
        calendar.render();
        monthCalendar.render();
        bindCalendarNavButtons();
        setTimeout(() => {
            calendar.updateSize();
            monthCalendar.updateSize();
            updateWeekNumberDisplay();
            updateCurrentWeekHighlight();
        }, 100);
        return;
    }

    if (calendar) calendar.destroy();
    if (monthCalendar) monthCalendar.destroy();

    calendar = new FullCalendar.Calendar(calendarEl, buildMainCalendarOptions(events, firstDay, timezone));
    monthCalendar = new FullCalendar.Calendar(monthCalendarEl, buildMonthCalendarOptions(events, firstDay, timezone));
    calendar.render();
    monthCalendar.render();
    bindCalendarNavButtons();
    initialized = true;

    setTimeout(() => {
        updateWeekNumberDisplay();
        updateCurrentWeekHighlight();
        calendar.updateSize();
        monthCalendar.updateSize();
    }, 200);
}

function closeMaintenanceModal() {
    closeWindowModal();
    document.getElementById("maintenance-modal")?.classList.remove("visible");
}

async function openMaintenanceModal() {
    if (!getIsAuthenticated()) return;
    const modal = document.getElementById("maintenance-modal");
    if (!modal) return;

    await loadChainsConfig();
    syncTimezoneSelects(configTimezone, messengerType, userTimezone);
    modal.classList.add("visible");

    setTimeout(async () => {
        await initializeCalendars();
    }, 200);
}

function setupWindowModalListeners() {
    const modal = document.getElementById("maintenance-window-modal");
    const closeBtn = modal?.querySelector(".modal-close");
    const saveBtn = document.getElementById("maintenance-window-save-btn");
    const deleteBtn = document.getElementById("maintenance-window-delete-btn");
    const matcherInput = document.getElementById("maintenance-matcher-input");
    const matchersBox = document.getElementById("maintenance-matchers-box");
    const commentInput = document.getElementById("maintenance-window-comment");

    closeBtn?.addEventListener("click", closeWindowModal);
    saveBtn?.addEventListener("click", saveWindowModal);
    deleteBtn?.addEventListener("click", deleteWindowModal);
    matcherInput?.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
            e.preventDefault();
            commitMatcherInput();
        }
    });
    matcherInput?.addEventListener("blur", commitMatcherInput);
    matcherInput?.addEventListener("input", () => matcherInput.classList.remove("maintenance-field-error"));
    matchersBox?.addEventListener("click", () => matcherInput?.focus());
    commentInput?.addEventListener("input", () => commentInput.classList.remove("maintenance-field-error"));

    modal?.addEventListener("click", (e) => {
        if (e.target === modal) closeWindowModal();
    });
}

export const MaintenanceManager = {
    initialized: false,

    init() {
        if (this.initialized) return;

        const modal = document.getElementById("maintenance-modal");
        const closeBtn = modal?.querySelector(".chains-modal-close");
        if (!modal || !closeBtn) return;

        setupWindowModalListeners();

        onTimezoneChange(async (context) => {
            refreshMaintenanceModalDateTimes(context);
            await updateCalendarTimezone();
        });

        closeBtn.addEventListener("click", closeMaintenanceModal);
        modal.addEventListener("click", (e) => {
            if (e.target === modal) closeMaintenanceModal();
        });

        document.addEventListener("keydown", (e) => {
            const windowModal = document.getElementById("maintenance-window-modal");
            if (windowModal?.classList.contains("visible") && e.key === "Escape") {
                closeWindowModal();
                return;
            }
            if (e.key === "Escape" && modal.classList.contains("visible")) {
                closeMaintenanceModal();
            }
        });

        onAuthChange((authenticated) => {
            if (authenticated) {
                mountFooterToggle();
                startActiveIndicatorPolling();
            } else {
                unmountFooterToggle();
            }
        });

        if (getIsAuthenticated()) {
            mountFooterToggle();
            startActiveIndicatorPolling();
        }

        this.initialized = true;
    },
};
