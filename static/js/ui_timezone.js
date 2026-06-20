const STORAGE_KEY = "ui_chains_timezone_mode";

const SOURCE_LABELS = {
    user: "messenger",
    browser: "browser",
    config: "config",
    utc: null,
};

const timezoneConfig = {
    configTimezone: "UTC",
    messengerType: "",
    userTimezone: null,
};

let documentClickAttached = false;

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
        options.push({
            value: "user",
            label: userTz,
            sourceLabel: SOURCE_LABELS.user,
            selected: currentMode === "user",
        });
    }
    if (browserTz && browserTz !== "UTC") {
        options.push({
            value: "browser",
            label: browserTz,
            sourceLabel: SOURCE_LABELS.browser,
            selected: currentMode === "browser",
        });
    }
    if (configTimezone && configTimezone !== "UTC") {
        options.push({
            value: "config",
            label: configTimezone,
            sourceLabel: SOURCE_LABELS.config,
            selected: currentMode === "config",
        });
    }
    options.push({
        value: "utc",
        label: "UTC",
        sourceLabel: SOURCE_LABELS.utc,
        selected: currentMode === "utc",
    });
    return options;
}

function fillTriggerContent(container, option) {
    container.replaceChildren();
    const name = document.createElement("span");
    name.className = "timezone-select-name";
    name.textContent = option.label;
    container.appendChild(name);
}

function fillDropdownOption(container, option) {
    container.replaceChildren();
    const body = document.createElement("div");
    body.className = "timezone-select-option-body";
    if (!option.sourceLabel) {
        body.classList.add("timezone-select-option-body--single");
    }
    if (option.sourceLabel) {
        const source = document.createElement("span");
        source.className = "timezone-select-source";
        source.textContent = option.sourceLabel;
        body.appendChild(source);
    }
    const name = document.createElement("span");
    name.className = "timezone-select-name";
    name.textContent = option.label;
    body.appendChild(name);
    container.appendChild(body);
}

function closeAllTimezoneMenus() {
    for (const menu of document.querySelectorAll(".timezone-select-menu")) {
        menu.hidden = true;
    }
    for (const trigger of document.querySelectorAll(".timezone-select-trigger")) {
        trigger.setAttribute("aria-expanded", "false");
    }
}

function syncTimezoneMenuWidth(widget) {
    const menu = widget.querySelector(".timezone-select-menu");
    const trigger = widget.querySelector(".timezone-select-trigger");
    if (!menu || !trigger || menu.children.length === 0) {
        return;
    }

    menu.style.minWidth = "";

    const wasHidden = menu.hidden;
    const previousVisibility = menu.style.visibility;
    menu.hidden = false;
    menu.style.visibility = "hidden";
    menu.style.pointerEvents = "none";

    let maxOptionWidth = 0;
    for (const option of menu.children) {
        maxOptionWidth = Math.max(maxOptionWidth, option.offsetWidth);
    }

    menu.hidden = wasHidden;
    menu.style.visibility = previousVisibility;
    menu.style.pointerEvents = "";

    menu.style.minWidth = `${Math.max(maxOptionWidth, trigger.offsetWidth)}px`;
}

function attachTimezoneDocumentClose() {
    if (documentClickAttached) {
        return;
    }
    documentClickAttached = true;
    document.addEventListener("click", closeAllTimezoneMenus);
}

function ensureTimezoneSelectWidget(selectEl) {
    const existing = selectEl.closest(".timezone-select-widget");
    if (existing) {
        return existing;
    }

    const widget = document.createElement("div");
    widget.className = "timezone-select-widget";
    selectEl.parentNode.insertBefore(widget, selectEl);
    widget.appendChild(selectEl);

    selectEl.classList.add("timezone-select-native");
    selectEl.tabIndex = -1;
    selectEl.setAttribute("aria-hidden", "true");

    const trigger = document.createElement("button");
    trigger.type = "button";
    trigger.className = "timezone-select-trigger";
    trigger.setAttribute("aria-haspopup", "listbox");
    trigger.setAttribute("aria-expanded", "false");

    const triggerContent = document.createElement("span");
    triggerContent.className = "timezone-select-trigger-content";
    trigger.appendChild(triggerContent);

    const chevron = document.createElement("span");
    chevron.className = "timezone-select-chevron";
    chevron.setAttribute("aria-hidden", "true");
    trigger.appendChild(chevron);

    const menu = document.createElement("ul");
    menu.className = "timezone-select-menu";
    menu.setAttribute("role", "listbox");
    menu.hidden = true;

    widget.appendChild(trigger);
    widget.appendChild(menu);

    trigger.addEventListener("click", (event) => {
        event.stopPropagation();
        const willOpen = menu.hidden;
        closeAllTimezoneMenus();
        if (willOpen) {
            syncTimezoneMenuWidth(widget);
        }
        menu.hidden = !willOpen;
        trigger.setAttribute("aria-expanded", willOpen ? "true" : "false");
    });

    return widget;
}

function fillTimezoneSelect(selector, configTimezone = "UTC", messengerType = "", userTimezone = null) {
    if (!selector) {
        return;
    }
    const options = getTimezoneOptions(configTimezone, messengerType, userTimezone);
    const widget = ensureTimezoneSelectWidget(selector);
    const trigger = widget.querySelector(".timezone-select-trigger");
    const triggerContent = widget.querySelector(".timezone-select-trigger-content");
    const menu = widget.querySelector(".timezone-select-menu");
    const selected = options.find((option) => option.selected) || options[0];

    selector.innerHTML = "";
    for (const option of options) {
        const nativeOption = document.createElement("option");
        nativeOption.value = option.value;
        nativeOption.textContent = option.label;
        if (option.selected) {
            nativeOption.selected = true;
        }
        selector.appendChild(nativeOption);
    }

    fillTriggerContent(triggerContent, selected);
    trigger.setAttribute("aria-label", `Timezone: ${selected.label}`);

    menu.replaceChildren();
    for (const option of options) {
        const item = document.createElement("li");
        item.className = "timezone-select-option";
        if (option.selected) {
            item.classList.add("selected");
            item.setAttribute("aria-selected", "true");
        } else {
            item.setAttribute("aria-selected", "false");
        }
        item.setAttribute("role", "option");
        item.dataset.value = option.value;
        fillDropdownOption(item, option);
        item.addEventListener("click", (event) => {
            event.stopPropagation();
            closeAllTimezoneMenus();
            applyTimezoneModeChange(option.value);
        });
        menu.appendChild(item);
    }
    syncTimezoneMenuWidth(widget);
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
    attachTimezoneDocumentClose();
    syncTimezoneSelects(
        timezoneConfig.configTimezone,
        timezoneConfig.messengerType,
        timezoneConfig.userTimezone,
    );
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
