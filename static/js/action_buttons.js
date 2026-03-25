import {getBaseUrl} from "./utils.js";
import {getIsAuthenticated, onAuthChange} from "./auth.js";

const PIN_ICON = `<svg width="12" height="12" viewBox="0 0 12 12" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M11.598 4.00156L7.74802 0.151562C7.64646 0.05 7.51365 0 7.38083 0C7.24802 0 7.11521 0.05 7.01365 0.151562L4.49646 2.67031C4.30583 2.64844 4.11365 2.63906 3.92146 2.63906C2.77771 2.63906 1.63396 3.01563 0.694896 3.76875C0.63803 3.81441 0.591421 3.87154 0.558105 3.93641C0.524789 4.00129 0.505513 4.07245 0.501533 4.14527C0.497553 4.21809 0.508958 4.29093 0.535005 4.35905C0.561053 4.42717 0.601158 4.48904 0.652709 4.54063L3.49177 7.37969L0.126146 10.7422C0.0849036 10.7832 0.05945 10.8374 0.0542713 10.8953L0.0011464 11.4766C-0.0129161 11.6234 0.104271 11.7484 0.249584 11.7484C0.257396 11.7484 0.265209 11.7484 0.273021 11.7469L0.854271 11.6938C0.912084 11.6891 0.966771 11.6625 1.0074 11.6219L4.37302 8.25625L7.21208 11.0953C7.31365 11.1969 7.44646 11.2469 7.57927 11.2469C7.73083 11.2469 7.88083 11.1813 7.98396 11.0531C8.86365 9.95469 9.22927 8.57969 9.08083 7.25L11.598 4.73281C11.7996 4.53281 11.7996 4.20469 11.598 4.00156ZM8.28396 6.45781L7.90115 6.84062L7.96052 7.37813C8.05363 8.20948 7.88774 9.0493 7.48552 9.78281L1.96833 4.2625C2.1699 4.15156 2.37927 4.05781 2.59802 3.98281C3.02302 3.83594 3.46833 3.7625 3.92146 3.7625C4.07146 3.7625 4.22302 3.77031 4.37302 3.7875L4.91052 3.84688L5.29333 3.46406L7.3824 1.375L10.3746 4.36719L8.28396 6.45781Z" fill="currentColor"/></svg>`;

const SNOWFLAKE_ICON = `<svg width="13" height="13" viewBox="0 0 13 13" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M2.71784 4.98616L5.49463 6.5985L2.99341 8.05081L0 7.24869V8.284L2.33897 8.91069L1.70881 11.2625L2.60537 11.7801L3.35031 8.99994L5.99038 7.467V10.226L3.76609 12.4503L4.66266 12.9679L6.55288 11.0777L8.40084 12.9257L9.29744 12.408L6.99038 10.101V7.467L9.58419 8.97309L10.3428 11.8045L11.2394 11.2868L10.6028 8.91069L12.9904 8.27094V7.23566L9.975 8.04362L7.48613 6.5985L10.2506 4.99331L12.9904 5.72744V4.69216L10.8137 4.10894L11.4146 1.86616L10.5181 1.3485L9.77775 4.1115L6.99038 5.72997V2.60616L9.07891 0.517625L8.18234 0L6.45822 1.72413L4.76113 0.0270624L3.86456 0.544687L5.99038 2.6705V5.72997L3.15678 4.08466L2.43016 1.37287L1.53356 1.8905L2.128 4.10894L0 4.67912V5.71441L2.71784 4.98616Z" fill="currentColor"/></svg>
`;

const RELEASE_ICON = `<svg width="12" height="12" viewBox="0 0 12 12" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M2 4L5 1M2 4L5 7M2 4H8C9.10457 4 10 4.89543 10 6V6C10 7.10457 9.10457 8 8 8H6" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/></svg>`;

const FREEZE_OPTIONS = [
    {label: "Tomorrow", value: "tomorrow"},
    {label: "Next Monday", value: "next_monday"},
    {label: "In Month", value: "month"},
    {label: "In 6 months", value: "6months"},
];

let featureFlags = {};
let activeFreezePopup = null;

function initActionButtons(uiConfig) {
    featureFlags = uiConfig.features || {};
}

function closeFreezePopup() {
    if (activeFreezePopup) {
        activeFreezePopup.remove();
        activeFreezePopup = null;
    }
}

document.addEventListener("click", () => closeFreezePopup());

function formatFrozenUntil(isoString) {
    if (!isoString) return "";
    const date = new Date(isoString);
    const now = new Date();
    const diffMs = date - now;
    const diffDays = diffMs / (1000 * 60 * 60 * 24);

    if (diffDays < 7) {
        const dayName = date.toLocaleDateString("en-US", {weekday: "short"});
        const time = date.toLocaleTimeString("en-US", {hour: "2-digit", minute: "2-digit", hour12: false});
        return `${dayName} ${time}`;
    }
    return date.toLocaleDateString("en-US", {month: "short", day: "numeric"});
}

function actionButtonsFormatter(cell) {
    const container = document.createElement("div");
    container.className = "action-buttons-container";

    const data = cell.getData();
    const info = (data._responsive_data || {}).incident_info || {};
    const isFrozen = data._is_frozen;
    const indicator = data.indicator;
    const assignedUserId = data._assigned_user_id;
    const taskLink = info.task_link;
    const frozenUntil = info.frozen_until;
    const frozenByInhibition = info.frozen_by_inhibition;
    const uniqId = data.uniq_id;

    const buttons = [];

    if (featureFlags.task_management) {
        const pinBtn = createButton(PIN_ICON, "action-btn action-btn-pin");
        if (taskLink) {
            pinBtn.classList.add("active");
            pinBtn.disabled = true;
            pinBtn.title = "Task created";
        } else {
            pinBtn.title = "Create task";
            pinBtn.addEventListener("click", async (e) => {
                e.stopPropagation();
                closeFreezePopup();
                pinBtn.disabled = true;
                try {
                    const response = await postAction("/task", {uniq_id: uniqId});
                    if (response.ok) {
                        pinBtn.classList.add("active");
                    } else {
                        pinBtn.disabled = false;
                        logActionError("task", response.status);
                    }
                } catch (err) {
                    pinBtn.disabled = false;
                    console.error("Task request failed:", err);
                }
            });
        }
        buttons.push(pinBtn);
    }

    const freezeBtn = createButton(SNOWFLAKE_ICON, "action-btn action-btn-freeze");
    if (isFrozen) {
        freezeBtn.classList.add("active");
        if (frozenByInhibition) {
            freezeBtn.classList.add("inhibited");
            freezeBtn.title = "Inhibited";
            freezeBtn.disabled = true;
        } else {
            freezeBtn.title = frozenUntil ? `Frozen until ${formatFrozenUntil(frozenUntil)}` : "Frozen";
            freezeBtn.addEventListener("click", async (e) => {
                e.stopPropagation();
                closeFreezePopup();
                freezeBtn.disabled = true;
                try {
                    const response = await postAction("/unfreeze", {uniq_id: uniqId});
                    if (response.ok) {
                        freezeBtn.classList.remove("active");
                    } else {
                        logActionError("unfreeze", response.status);
                    }
                } catch (err) {
                    console.error("Unfreeze request failed:", err);
                } finally {
                    freezeBtn.disabled = false;
                }
            });
        }
    } else {
        freezeBtn.title = "Freeze";
        freezeBtn.addEventListener("click", (e) => {
            e.stopPropagation();
            if (activeFreezePopup) {
                closeFreezePopup();
                return;
            }
            showFreezePopup(freezeBtn, uniqId);
        });
    }
    buttons.push(freezeBtn);

    if (indicator === "resolved" && assignedUserId) {
        const releaseBtn = createButton(RELEASE_ICON, "action-btn action-btn-release");
        releaseBtn.title = "Release";
        releaseBtn.addEventListener("click", async (e) => {
            e.stopPropagation();
            closeFreezePopup();
            releaseBtn.disabled = true;
            try {
                const response = await postAction("/release", {uniq_id: uniqId});
                if (!response.ok) {
                    releaseBtn.disabled = false;
                    logActionError("release", response.status);
                }
            } catch (err) {
                releaseBtn.disabled = false;
                console.error("Release request failed:", err);
            }
        });
        buttons.push(releaseBtn);
    }

    const authenticated = getIsAuthenticated();
    buttons.forEach(btn => {
        if (!authenticated && !btn.disabled) {
            btn.disabled = true;
            btn.classList.add("auth-disabled");
        }
        container.appendChild(btn);
    });

    onAuthChange((isAuth) => {
        buttons.forEach(btn => {
            if (isAuth) {
                if (btn.classList.contains("auth-disabled")) {
                    btn.disabled = false;
                    btn.classList.remove("auth-disabled");
                }
            } else {
                if (!btn.classList.contains("active") || !btn.classList.contains("inhibited")) {
                    btn.disabled = true;
                    btn.classList.add("auth-disabled");
                }
            }
        });
    });

    return container;
}

function createButton(iconHtml, className) {
    const btn = document.createElement("button");
    btn.className = className;
    btn.innerHTML = iconHtml;
    btn.type = "button";
    return btn;
}

function showFreezePopup(anchorBtn, uniqId) {
    closeFreezePopup();

    const popup = document.createElement("div");
    popup.className = "freeze-popup";

    FREEZE_OPTIONS.forEach(opt => {
        const item = document.createElement("div");
        item.className = "freeze-popup-option";
        item.textContent = opt.label;
        item.addEventListener("click", async (e) => {
            e.stopPropagation();
            closeFreezePopup();
            anchorBtn.disabled = true;
            try {
                const response = await postAction("/freeze", {uniq_id: uniqId, freeze_option: opt.value});
                if (response.ok) {
                    anchorBtn.classList.add("active");
                } else {
                    logActionError("freeze", response.status);
                }
            } catch (err) {
                console.error("Freeze request failed:", err);
            } finally {
                anchorBtn.disabled = false;
            }
        });
        popup.appendChild(item);
    });

    anchorBtn.style.position = "relative";
    anchorBtn.appendChild(popup);
    activeFreezePopup = popup;

    popup.addEventListener("click", (e) => e.stopPropagation());
}

async function postAction(endpoint, body) {
    const baseUrl = getBaseUrl();
    return fetch(`${baseUrl}${endpoint}`, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        credentials: "same-origin",
        body: JSON.stringify(body),
    });
}

function logActionError(action, status) {
    console.error(`${action} action failed:`, status);
}

export {initActionButtons, actionButtonsFormatter};
