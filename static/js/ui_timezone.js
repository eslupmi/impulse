const STORAGE_KEY = "ui_chains_timezone_mode";

const timezoneConfig = {
    configTimezone: "UTC",
    messengerType: "",
    userTimezone: null,
};

function resolveUserTimezone(userTimezone) {
    return userTimezone || null;
}

function getBrowserTimezone() {
    try {
        return Intl.DateTimeFormat().resolvedOptions().timeZone || null;
    } catch {
        return null;
    }
}

export function getTimezoneMode(configTimezone = "UTC", userTimezone = null) {
    const saved = localStorage.getItem(STORAGE_KEY);
    const userTz = resolveUserTimezone(userTimezone);
    const browserTz = getBrowserTimezone();
    if (saved === "user") {
        if (userTz && userTz !== "UTC") {
            return "user";
        }
    } else if (saved === "browser") {
        if (browserTz && browserTz !== "UTC") {
            return "browser";
        }
    } else if (saved === "config" || saved === "utc") {
        return saved;
    }
    if (userTz && userTz !== "UTC") {
        return "user";
    }
    if (browserTz && browserTz !== "UTC") {
        return "browser";
    }
    if (configTimezone && configTimezone !== "UTC") {
        return "config";
    }
    return "utc";
}

export function setTimezoneMode(mode) {
    localStorage.setItem(STORAGE_KEY, mode);
}

export function getEffectiveTimezone(configTimezone = "UTC", userTimezone = null) {
    const mode = getTimezoneMode(configTimezone, userTimezone);
    if (mode === "user") {
        return resolveUserTimezone(userTimezone);
    }
    if (mode === "browser") {
        return getBrowserTimezone() || "UTC";
    }
    if (mode === "config") {
        return configTimezone || "UTC";
    }
    return "UTC";
}

function getTimezoneOptions(configTimezone = "UTC", messengerType = "", userTimezone = null) {
    const options = [];
    const userTz = resolveUserTimezone(userTimezone);
    const browserTz = getBrowserTimezone();
    const currentMode = getTimezoneMode(configTimezone, userTimezone);
    if (userTz && userTz !== "UTC") {
        options.push({value: "user", label: userTz, selected: currentMode === "user"});
    }
    if (browserTz && browserTz !== "UTC") {
        options.push({value: "browser", label: browserTz, selected: currentMode === "browser"});
    }
    if (configTimezone && configTimezone !== "UTC") {
        options.push({value: "config", label: configTimezone, selected: currentMode === "config"});
    }
    options.push({value: "utc", label: "UTC", selected: currentMode === "utc"});
    return options;
}

export function fillTimezoneSelect(selector, configTimezone = "UTC", messengerType = "", userTimezone = null) {
    if (!selector) return;
    const options = getTimezoneOptions(configTimezone, messengerType, userTimezone);
    selector.innerHTML = "";
    for (const opt of options) {
        const option = document.createElement("option");
        option.value = opt.value;
        option.textContent = opt.label;
        if (opt.selected) option.selected = true;
        selector.appendChild(option);
    }
}

export function syncTimezoneSelects(configTimezone = "UTC", messengerType = "", userTimezone = null) {
    fillTimezoneSelect(document.getElementById("timezone-select"), configTimezone, messengerType, userTimezone);
    fillTimezoneSelect(document.getElementById("maintenance-timezone-select"), configTimezone, messengerType, userTimezone);
}

const timezoneChangeListeners = new Set();

export function onTimezoneChange(callback) {
    timezoneChangeListeners.add(callback);
    return () => timezoneChangeListeners.delete(callback);
}

function notifyTimezoneChange(context) {
    for (const callback of timezoneChangeListeners) {
        Promise.resolve(callback(context)).catch((error) => {
            console.error("Timezone change handler failed", error);
        });
    }
}

export function updateTimezoneConfig({configTimezone, messengerType, userTimezone}) {
    if (configTimezone !== undefined) {
        timezoneConfig.configTimezone = configTimezone;
    }
    if (messengerType !== undefined) {
        timezoneConfig.messengerType = messengerType;
    }
    if (userTimezone !== undefined) {
        timezoneConfig.userTimezone = userTimezone;
    }
}

export function getTimezoneConfig() {
    return timezoneConfig;
}

export function applyTimezoneModeChange(mode) {
    const {configTimezone, messengerType, userTimezone} = timezoneConfig;
    const previousTimezone = getEffectiveTimezone(configTimezone, userTimezone);
    setTimezoneMode(mode);
    syncTimezoneSelects(configTimezone, messengerType, userTimezone);
    notifyTimezoneChange({previousTimezone, configTimezone, userTimezone});
}

export function captureCalendarViewAnchor(calendarApi) {
    if (!calendarApi?.view) {
        return null;
    }
    const timeZone = calendarApi.getOption("timeZone") || "local";
    const activeStart = calendarApi.view.activeStart;
    if (typeof luxon === "undefined") {
        const year = activeStart.getFullYear();
        const month = String(activeStart.getMonth() + 1).padStart(2, "0");
        const day = String(activeStart.getDate()).padStart(2, "0");
        return `${year}-${month}-${day}`;
    }
    const zone = timeZone === "local" ? undefined : timeZone;
    return luxon.DateTime.fromJSDate(activeStart, zone ? {zone} : undefined).toFormat("yyyy-MM-dd");
}

export function initTimezoneSelectHandlers() {
    for (const id of ["timezone-select", "maintenance-timezone-select"]) {
        const select = document.getElementById(id);
        if (!select || select.dataset.timezoneHandlerAttached) {
            continue;
        }
        select.dataset.timezoneHandlerAttached = "1";
        select.addEventListener("change", (event) => {
            applyTimezoneModeChange(event.target.value);
        });
    }
}

export function reformatDateTimeValue(value, previousTimezone, configTimezone, userTimezone) {
    const match = value.trim().match(/(\d{4})-(\d{2})-(\d{2}),\s*(\d{2}):(\d{2})/);
    if (!match) {
        return value;
    }
    const [, year, month, day, hour, minute] = match;
    if (typeof luxon === "undefined") {
        return value;
    }
    const utc = luxon.DateTime.fromObject(
        {year: +year, month: +month, day: +day, hour: +hour, minute: +minute, second: 0},
        {zone: previousTimezone},
    ).toUTC();
    const dt = utc.setZone(getEffectiveTimezone(configTimezone, userTimezone));
    const pad = (n) => n.toString().padStart(2, "0");
    return `${dt.year}-${pad(dt.month)}-${pad(dt.day)}, ${pad(dt.hour)}:${pad(dt.minute)}`;
}

export function reformatDateTimeInput(input, previousTimezone, configTimezone, userTimezone) {
    if (!input?.value.trim()) {
        return;
    }
    input.value = reformatDateTimeValue(input.value, previousTimezone, configTimezone, userTimezone);
}
