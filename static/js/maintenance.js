import {getSocket} from "./websocket.js";
import {getBaseUrl, parseWeekStart} from "./utils.js";
import {
    attachNavListener,
    cleanupFullCalendarDragArtifacts,
    destroyFullCalendarInstance,
    getSharedCalendarOptions,
    registerCalendarSuspender,
    suspendOtherCalendars,
    updateMonthCalendarWeekHighlight,
} from "./calendar_shared.js";
import {createEditableFilterBadge} from "./filters.js";
import {validateAndFormatMatcher, validateMatcher} from "./matcher.js";
import {getIsAuthenticated, onAuthChange} from "./auth.js";
import {createUserSelector, getAssignableUserById, initUserSelector} from "./user_selector.js";
import {
    captureCalendarViewAnchor,
    formatDateTime,
    getEffectiveTimezone,
    onTimezoneChange,
    parseDateTime,
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
let ownerSelector = null;
let configTimezone = "UTC";
let configWeekStart = "Mon";
let messengerType = "";
let userTimezone = null;
let cachedActiveWindows = [];
let popupClosedThisSession = false;
let popupVisible = false;
let activeMaintenanceTimer = null;

const ACTIVE_MAINTENANCE_RERENDER_MS = 30000;

const MAINTENANCE_TOGGLE_HTML =
    '<svg class="maintenance-icon" width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">' +
    '<path d="M8.30088 3.36909C8.17873 3.49371 8.11031 3.66126 8.11031 3.83576C8.11031 4.01026 8.17873 4.17781 8.30088 4.30243L9.36755 5.36909C9.49217 5.49125 9.65971 5.55967 9.83421 5.55967C10.0087 5.55967 10.1763 5.49125 10.3009 5.36909L12.8142 2.85576C13.1494 3.59655 13.2509 4.42192 13.1052 5.22186C12.9594 6.0218 12.5734 6.75832 11.9984 7.33328C11.4234 7.90824 10.6869 8.29432 9.88698 8.44007C9.08704 8.58582 8.26167 8.48432 7.52088 8.1491L2.91421 12.7558C2.649 13.021 2.28929 13.17 1.91421 13.17C1.53914 13.17 1.17943 13.021 0.914214 12.7558C0.648997 12.4905 0.5 12.1308 0.5 11.7558C0.5 11.3807 0.648997 11.021 0.914214 10.7558L5.52088 6.1491C5.18566 5.4083 5.08416 4.58294 5.22991 3.783C5.37566 2.98306 5.76174 2.24653 6.33669 1.67158C6.91165 1.09662 7.64818 0.710541 8.44812 0.564789C9.24806 0.419038 10.0734 0.520538 10.8142 0.855761L8.30755 3.36243L8.30088 3.36909Z" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round"/>' +
    '</svg>';

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

function formatTimeLeft(endIso, now = new Date()) {
    const ms = new Date(endIso).getTime() - now.getTime();
    if (ms <= 0) return "ended";
    const minutes = Math.floor(ms / 60000);
    if (minutes < 1) return "<1m left";
    if (minutes < 60) return `${minutes}m left`;
    const hours = Math.floor(minutes / 60);
    const mins = minutes % 60;
    if (mins === 0) return `${hours}h left`;
    return `${hours}h ${mins}m left`;
}

function formatTimeRange(startIso, endIso) {
    const timeOpts = {hour: "2-digit", minute: "2-digit", hour12: false};
    const start = new Date(startIso).toLocaleTimeString(undefined, timeOpts);
    const end = new Date(endIso).toLocaleTimeString(undefined, timeOpts);
    return `${start}-${end}`;
}

function getCurrentlyActiveWindows(windows, now = new Date()) {
    return windows.filter((w) => isMaintenanceWindowActive(w.start, w.end, now));
}

function updateActiveCounter(count) {
    const counter = document.getElementById("maintenance-active-counter");
    if (!counter) return;
    if (count > 0) {
        counter.textContent = String(count);
        counter.classList.remove("hidden");
        counter.setAttribute("aria-label", count === 1
            ? "1 active maintenance window"
            : `${count} active maintenance windows`);
    } else {
        counter.textContent = "";
        counter.classList.add("hidden");
        counter.setAttribute("aria-label", "Active maintenance");
    }
}

function showActiveMaintenancePopup() {
    const popup = document.getElementById("maintenance-active-popup");
    if (!popup) return;
    popup.classList.remove("hidden");
    popupVisible = true;
}

function hideActiveMaintenancePopup() {
    const popup = document.getElementById("maintenance-active-popup");
    if (!popup) return;
    popup.classList.add("hidden");
    popupVisible = false;
}

function renderActiveMaintenancePopup(windows) {
    const list = document.getElementById("maintenance-active-popup-list");
    if (!list) return;
    list.replaceChildren();
    const now = new Date();
    const activeWindows = windows.filter((window) => isMaintenanceWindowActive(window.start, window.end, now));
    activeWindows.forEach((window, index) => {
        const row = document.createElement("div");
        row.className = "maintenance-active-popup-row";

        const times = document.createElement("div");
        times.className = "maintenance-active-popup-times";

        const timeLeft = document.createElement("div");
        timeLeft.className = "maintenance-active-popup-time-left";
        timeLeft.textContent = formatTimeLeft(window.end, now);

        const timeRange = document.createElement("div");
        timeRange.className = "maintenance-active-popup-time-range";
        timeRange.textContent = formatTimeRange(window.start, window.end);

        times.append(timeLeft, timeRange);

        const comment = document.createElement("div");
        comment.className = "maintenance-active-popup-comment";
        comment.textContent = window.comment || "";

        row.append(times, comment);

        const owner = document.createElement(window.owner_url ? "a" : "span");
        owner.className = "maintenance-active-popup-owner";
        owner.textContent = window.owner_full_name || "";
        owner.title = window.owner_full_name || "";
        if (window.owner_url) {
            owner.href = window.owner_url;
            owner.target = "_blank";
            owner.rel = "noopener noreferrer";
        }
        row.append(owner);

        list.appendChild(row);
        if (index < activeWindows.length - 1) {
            const divider = document.createElement("div");
            divider.className = "maintenance-active-popup-row-divider";
            divider.setAttribute("aria-hidden", "true");
            list.appendChild(divider);
        }
    });
}

function refreshActiveMaintenanceDisplay() {
    const now = new Date();
    cachedActiveWindows = getCurrentlyActiveWindows(cachedActiveWindows, now);
    const count = cachedActiveWindows.length;
    updateActiveCounter(count);
    if (count === 0) {
        hideActiveMaintenancePopup();
        return;
    }
    renderActiveMaintenancePopup(cachedActiveWindows);
}

globalThis.handleActiveMaintenance = function(list) {
    const incoming = Array.isArray(list) ? list : [];
    const prevCount = getCurrentlyActiveWindows(cachedActiveWindows).length;
    cachedActiveWindows = incoming;
    const active = getCurrentlyActiveWindows(cachedActiveWindows);
    const count = active.length;
    updateActiveCounter(count);

    if (count === 0) {
        hideActiveMaintenancePopup();
        return;
    }

    renderActiveMaintenancePopup(active);

    if (prevCount === 0 && count > 0 && !getIsAuthenticated() && !popupClosedThisSession) {
        showActiveMaintenancePopup();
    }
};

function setupActiveMaintenanceUI() {
    const counter = document.getElementById("maintenance-active-counter");
    const closeBtn = document.getElementById("maintenance-active-popup-close");

    counter?.addEventListener("click", () => {
        if (popupVisible) {
            hideActiveMaintenancePopup();
        } else {
            showActiveMaintenancePopup();
        }
    });

    closeBtn?.addEventListener("click", () => {
        popupClosedThisSession = true;
        hideActiveMaintenancePopup();
    });

    onAuthChange((authenticated) => {
        if (authenticated) {
            hideActiveMaintenancePopup();
            return;
        }
        if (cachedActiveWindows.length > 0 && !popupClosedThisSession) {
            showActiveMaintenancePopup();
        }
    });

    if (activeMaintenanceTimer === null) {
        activeMaintenanceTimer = setInterval(() => {
            refreshActiveMaintenanceDisplay();
        }, ACTIVE_MAINTENANCE_RERENDER_MS);
    }
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
}

function unmountFooterToggle() {
    destroyCalendars();
    closeMaintenanceModal();
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
};

globalThis.handleMaintenanceSaved = function(success, detail) {
    if (savePromiseResolve) {
        savePromiseResolve(!!success);
        savePromiseResolve = null;
    }
    if (!success) {
        showNotification(detail || "Failed to save maintenance windows");
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
    if (socket?.readyState !== WebSocket.OPEN) {
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
    if (socket?.readyState !== WebSocket.OPEN) {
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

let windowModalPersistInFlight = false;

async function getWindowsForEdit() {
    if (cachedWindows.length > 0) {
        return [...cachedWindows];
    }
    return [...await loadWindows()];
}

function setWindowModalPersistInFlight(inFlight) {
    windowModalPersistInFlight = inFlight;
    document.getElementById("maintenance-window-save-btn")?.toggleAttribute("disabled", inFlight);
    document.getElementById("maintenance-window-delete-btn")?.toggleAttribute("disabled", inFlight);
}

async function persistMaintenanceWindows(windows, previousWindows) {
    refreshCalendarEvents(windows);
    const saved = await saveWindows(windows);
    if (!saved) {
        cachedWindows = previousWindows;
        refreshCalendarEvents(previousWindows);
    }
    return saved;
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
            owner_id: window.owner_id || null,
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
            document.getElementById("maintenance-window-start").value = formatDateTime(info.start, getTz());
            if (info.end) {
                document.getElementById("maintenance-window-end").value = formatDateTime(info.end, getTz());
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
                owner_id: props.owner_id || null,
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
    const previousWindows = cachedWindows;
    const windows = await getWindowsForEdit();
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
    const saved = await persistMaintenanceWindows(windows, previousWindows);
    if (!saved) {
        info.revert();
    }
}

function setMatcherInputError(reason) {
    const input = document.getElementById("maintenance-matcher-input");
    const wrap = document.getElementById("maintenance-matchers-wrap");
    const error = document.getElementById("maintenance-matcher-error");
    input?.classList.add("maintenance-field-error");
    wrap?.classList.add("maintenance-field-error");
    if (error) {
        error.textContent = reason;
        error.classList.remove("hidden");
    }
}

function clearMatcherInputError() {
    const input = document.getElementById("maintenance-matcher-input");
    const wrap = document.getElementById("maintenance-matchers-wrap");
    const error = document.getElementById("maintenance-matcher-error");
    input?.classList.remove("maintenance-field-error");
    if (error) {
        error.textContent = "";
        error.classList.add("hidden");
    }
    if (wrap) {
        wrap.classList.toggle("maintenance-field-error", modalMatchers.length === 0);
    }
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
            validateAndFormat: validateAndFormatMatcher,
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
    if (wrap && modalMatchers.length > 0) {
        wrap.classList.remove("maintenance-field-error");
    }
}

function commitMatcherInput() {
    const input = document.getElementById("maintenance-matcher-input");
    const wrap = document.getElementById("maintenance-matchers-wrap");
    if (!input) return true;
    const query = input.value.trim();
    if (!query) {
        if (modalMatchers.length === 0) {
            setMatcherInputError("At least one matcher is required");
            return false;
        }
        clearMatcherInputError();
        if (wrap) wrap.classList.remove("maintenance-field-error");
        return true;
    }
    const result = validateMatcher(query);
    if (!result.ok) {
        setMatcherInputError(result.reason);
        return false;
    }
    if (!modalMatchers.includes(result.formatted)) {
        modalMatchers.push(result.formatted);
        renderMatcherBadges();
    }
    input.value = "";
    clearMatcherInputError();
    if (wrap) wrap.classList.toggle("maintenance-field-error", modalMatchers.length === 0);
    return true;
}

function ensureOwnerSelector() {
    if (ownerSelector) {
        return ownerSelector;
    }
    const wrap = document.getElementById("maintenance-window-owner-wrap");
    ownerSelector = createUserSelector({
        inputId: "maintenance-window-owner",
        allowClear: false,
    });
    wrap.replaceChildren(ownerSelector.element);
    return ownerSelector;
}

function setOwnerSelectorValue(ownerId, fullName, {defaultToAuthUser = false} = {}) {
    const selector = ensureOwnerSelector();
    if (ownerId) {
        const user = getAssignableUserById(ownerId);
        selector.setValue(ownerId, fullName || (user && user.full_name) || "");
        return;
    }
    if (defaultToAuthUser) {
        selector.setDefaultToAuthUser();
        return;
    }
    selector.setValue("", "");
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
        startInput.value = formatDateTime(windowData.start, getTz());
        endInput.value = windowData.end ? formatDateTime(windowData.end, getTz()) : "";
        commentInput.value = windowData.comment || "";
        modalMatchers = [...(windowData.matchers || [])];
        deleteBtn.classList.remove("hidden");
        setOwnerSelectorValue(windowData.owner_id, null);
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
        setOwnerSelectorValue("", "", {defaultToAuthUser: true});
    }
    renderMatcherBadges();
    clearMatcherInputError();
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
    const start = parseDateTime(startStr, getTz());
    const end = parseDateTime(endStr, getTz());
    if (!start || !end) {
        showNotification("Invalid date format");
        return null;
    }
    if (new Date(end) <= new Date(start)) {
        showNotification("End must be after start");
        return null;
    }
    if (!commitMatcherInput()) {
        return null;
    }
    if (modalMatchers.length === 0) {
        setMatcherInputError("At least one matcher is required");
        return null;
    }
    const matchers = [];
    for (const matcher of modalMatchers) {
        const result = validateMatcher(matcher);
        if (!result.ok) {
            setMatcherInputError(result.reason);
            return null;
        }
        matchers.push(result.formatted);
    }
    if (!comment) {
        commentBox?.classList.add("maintenance-field-error");
        showNotification("Comment is required");
        return null;
    }
    const ownerValue = ensureOwnerSelector().getValue();
    if (!ownerValue.userId) {
        showNotification("Owner is required");
        return null;
    }
    commentBox?.classList.remove("maintenance-field-error");
    clearMatcherInputError();
    if (matchersWrap) matchersWrap.classList.remove("maintenance-field-error");
    return {start, end, comment, matchers, owner_id: ownerValue.userId};
}

async function saveWindowModal() {
    if (windowModalPersistInFlight) return;
    const input = validateWindowModalInput();
    if (!input) return;

    const previousWindows = cachedWindows;
    const windows = await getWindowsForEdit();
    if (currentWindowId) {
        const index = windows.findIndex((w) => w.id === currentWindowId);
        if (index === -1) return;
        windows[index] = {
            ...windows[index],
            start: input.start,
            end: input.end,
            matchers: input.matchers,
            comment: input.comment,
            owner_id: input.owner_id,
        };
    } else {
        windows.push({
            id: crypto.randomUUID(),
            start: input.start,
            end: input.end,
            matchers: input.matchers,
            comment: input.comment,
            owner_id: input.owner_id,
        });
    }

    setWindowModalPersistInFlight(true);
    closeWindowModal();
    await persistMaintenanceWindows(windows, previousWindows);
    setWindowModalPersistInFlight(false);
}

async function deleteWindowModal() {
    if (!currentWindowId || windowModalPersistInFlight) return;

    const previousWindows = cachedWindows;
    const windows = (await getWindowsForEdit()).filter((w) => w.id !== currentWindowId);

    setWindowModalPersistInFlight(true);
    closeWindowModal();
    await persistMaintenanceWindows(windows, previousWindows);
    setWindowModalPersistInFlight(false);
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

function destroyCalendars() {
    destroyFullCalendarInstance(calendar);
    calendar = null;
    destroyFullCalendarInstance(monthCalendar);
    monthCalendar = null;
    initialized = false;
    cleanupFullCalendarDragArtifacts();
}

function closeMaintenanceModal() {
    closeWindowModal();
    document.getElementById("maintenance-modal")?.classList.remove("visible");
}

async function openMaintenanceModal() {
    if (!getIsAuthenticated()) return;
    suspendOtherCalendars("maintenance");
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
    const closeBtn = modal?.querySelector(".chains-modal-close");
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
    matcherInput?.addEventListener("input", clearMatcherInputError);
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

        setupActiveMaintenanceUI();
        initUserSelector(getBaseUrl()).then(() => ensureOwnerSelector());

        onAuthChange((authenticated) => {
            if (authenticated) {
                mountFooterToggle();
            } else {
                unmountFooterToggle();
            }
        });

        if (getIsAuthenticated()) {
            mountFooterToggle();
        }

        const modal = document.getElementById("maintenance-modal");
        const closeBtn = modal?.querySelector(".chains-modal-close");
        if (!modal || !closeBtn) {
            this.initialized = true;
            return;
        }

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

        registerCalendarSuspender("maintenance", destroyCalendars);

        this.initialized = true;
    },
};
