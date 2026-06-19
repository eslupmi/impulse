const STORAGE_KEY = "ui_chains_timezone_mode";

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
