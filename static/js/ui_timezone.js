const STORAGE_KEY = "ui_chains_timezone_mode";

let openPickerMenu = null;

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
        options.push({value: "user", label: userTz, hint: messengerType, selected: currentMode === "user"});
    }
    if (browserTz && browserTz !== "UTC") {
        options.push({value: "browser", label: browserTz, hint: "browser", selected: currentMode === "browser"});
    }
    if (configTimezone && configTimezone !== "UTC") {
        options.push({value: "config", label: configTimezone, hint: "config", selected: currentMode === "config"});
    }
    options.push({value: "utc", label: "UTC", hint: "", selected: currentMode === "utc"});
    return options;
}

function buildOptionLabel(label, hint) {
    const wrap = document.createElement("span");
    wrap.className = "timezone-picker-option-text";
    const main = document.createElement("span");
    main.className = "timezone-picker-label";
    main.textContent = label;
    wrap.appendChild(main);
    if (hint) {
        const sub = document.createElement("span");
        sub.className = "timezone-picker-hint";
        sub.textContent = hint;
        wrap.appendChild(sub);
    }
    return wrap;
}

function closeOpenPickerMenu() {
    if (openPickerMenu) {
        openPickerMenu.classList.add("hidden");
        openPickerMenu = null;
    }
}

function updatePickerTrigger(picker, options) {
    const trigger = picker.querySelector(".timezone-picker-trigger");
    const selected = options.find((o) => o.selected) || options[options.length - 1];
    trigger.replaceChildren(buildOptionLabel(selected.label, selected.hint));
}

function rebuildPickerMenu(picker, selectEl, options) {
    const menu = picker.querySelector(".timezone-picker-menu");
    menu.replaceChildren();
    for (const opt of options) {
        const item = document.createElement("button");
        item.type = "button";
        item.className = "timezone-picker-menu-item";
        item.appendChild(buildOptionLabel(opt.label, opt.hint));
        item.addEventListener("click", (e) => {
            e.stopPropagation();
            selectEl.value = opt.value;
            selectEl.dispatchEvent(new Event("change", {bubbles: true}));
            closeOpenPickerMenu();
        });
        menu.appendChild(item);
    }
}

function mountTimezonePicker(selectEl) {
    if (selectEl.dataset.timezonePickerMounted) return;
    selectEl.dataset.timezonePickerMounted = "1";
    selectEl.classList.add("timezone-select-native");

    const picker = document.createElement("div");
    picker.className = "timezone-picker";

    const trigger = document.createElement("button");
    trigger.type = "button";
    trigger.className = "timezone-picker-trigger";
    trigger.title = "Timezone";

    const menu = document.createElement("div");
    menu.className = "timezone-picker-menu hidden";

    trigger.addEventListener("click", (e) => {
        e.stopPropagation();
        if (openPickerMenu === menu) {
            closeOpenPickerMenu();
            return;
        }
        closeOpenPickerMenu();
        menu.classList.remove("hidden");
        openPickerMenu = menu;
    });

    picker.appendChild(trigger);
    picker.appendChild(menu);
    selectEl.parentNode.insertBefore(picker, selectEl);
}

export function fillTimezoneSelect(selector, configTimezone = "UTC", messengerType = "", userTimezone = null) {
    if (!selector) return;
    if (!selector.dataset.timezonePickerMounted) {
        mountTimezonePicker(selector);
    }
    const options = getTimezoneOptions(configTimezone, messengerType, userTimezone);
    selector.innerHTML = "";
    for (const opt of options) {
        const option = document.createElement("option");
        option.value = opt.value;
        option.textContent = opt.label;
        if (opt.selected) option.selected = true;
        selector.appendChild(option);
    }
    const picker = selector.previousElementSibling;
    if (picker?.classList.contains("timezone-picker")) {
        updatePickerTrigger(picker, options);
        rebuildPickerMenu(picker, selector, options);
    }
}

export function syncTimezoneSelects(configTimezone = "UTC", messengerType = "", userTimezone = null) {
    fillTimezoneSelect(document.getElementById("timezone-select"), configTimezone, messengerType, userTimezone);
    fillTimezoneSelect(document.getElementById("maintenance-timezone-select"), configTimezone, messengerType, userTimezone);
}

document.addEventListener("click", () => closeOpenPickerMenu());
document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeOpenPickerMenu();
});
