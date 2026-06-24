import {getBaseUrl} from "./utils.js";
import {getIsAuthenticated, onAuthChange} from "./auth.js";

let assignableUsers = [];

async function initUserSelector(baseUrl) {
    try {
        const response = await fetch(`${baseUrl}/assignment_users`);
        if (response.ok) {
            assignableUsers = await response.json();
        }
    } catch (error) {
        console.error("Failed to load assignable users:", error);
    }
}

function userSelectorFormatter(cell) {
    const container = document.createElement("div");
    container.className = "user-selector-container";

    const indicator = cell.getData().indicator;
    if (indicator === "closed" || indicator === "deleted") {
        return container;
    }

    let currentUserId = String(cell.getData()._assigned_user_id || "");
    let currentFullName = cell.getData()._assigned_fullname || "";

    const wrapper = document.createElement("div");
    wrapper.className = "user-selector-wrapper";

    const input = document.createElement("input");
    input.type = "text";
    input.className = "user-selector";
    input.autocomplete = "off";
    input.placeholder = "\u2014";
    if (currentUserId) {
        input.value = currentFullName;
        input.classList.add("has-value");
    }

    const optionsEl = document.createElement("div");
    optionsEl.className = "user-selector-options hidden";

    const currentInList = assignableUsers.some(u => String(u.user_id) === currentUserId);
    const isReadonlyExtra = currentUserId && !currentInList && currentFullName;
    let activeOptionIndex = -1;
    let isAssigning = false;

    function getUsers() {
        return [...assignableUsers].sort((a, b) => a.full_name.localeCompare(b.full_name));
    }

    function setActiveOption(index) {
        const optionNodes = optionsEl.querySelectorAll(".user-selector-option");
        if (optionNodes.length === 0) {
            activeOptionIndex = -1;
            return;
        }
        const nextIndex = Math.max(0, Math.min(index, optionNodes.length - 1));
        activeOptionIndex = nextIndex;
        optionNodes.forEach((node, nodeIndex) => {
            node.classList.toggle("active", nodeIndex === nextIndex);
        });
    }

    function selectActiveOption() {
        const optionNodes = optionsEl.querySelectorAll(".user-selector-option");
        if (activeOptionIndex < 0 || activeOptionIndex >= optionNodes.length) {
            return;
        }
        const user = getUsers().find(u => u.full_name === optionNodes[activeOptionIndex].textContent);
        if (user) {
            selectUser(user);
        }
    }

    function positionOptions() {
        const rect = input.getBoundingClientRect();
        optionsEl.style.top = `${rect.bottom + 4}px`;
        optionsEl.style.left = `${rect.left}px`;
        optionsEl.style.width = `${rect.width}px`;
    }

    function renderOptions(showAll = false) {
        const query = input.value.trim().toLowerCase();
        const filtered = showAll || !query
            ? getUsers()
            : getUsers().filter(u => u.full_name.toLowerCase().includes(query));

        optionsEl.innerHTML = "";
        filtered.forEach(user => {
            const optionEl = document.createElement("div");
            optionEl.className = "user-selector-option";
            optionEl.textContent = user.full_name;
            optionEl.addEventListener("mousedown", (event) => {
                event.preventDefault();
                selectUser(user);
            });
            optionsEl.appendChild(optionEl);
        });
        activeOptionIndex = -1;

        if (filtered.length > 0) {
            positionOptions();
            optionsEl.classList.remove("hidden");
        } else {
            optionsEl.classList.add("hidden");
        }
    }

    async function selectUser(user) {
        const userId = String(user.user_id);
        if (isAssigning || userId === currentUserId) {
            input.value = currentFullName;
            optionsEl.classList.add("hidden");
            return;
        }

        const uniqId = cell.getData().uniq_id;
        isAssigning = true;
        input.disabled = true;

        try {
            const baseUrl = getBaseUrl();
            const response = await fetch(`${baseUrl}/assign`, {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                credentials: "same-origin",
                body: JSON.stringify({uniq_id: uniqId, user_id: userId}),
            });

            if (response.ok) {
                currentUserId = userId;
                currentFullName = user.full_name;
                input.value = currentFullName;
                input.classList.add("has-value");
            } else {
                console.error("Assignment failed:", response.status);
                input.value = currentFullName;
            }
        } catch (error) {
            console.error("Assignment request failed:", error);
            input.value = currentFullName;
        } finally {
            isAssigning = false;
            input.disabled = false;
            optionsEl.classList.add("hidden");
        }
    }

    if (isReadonlyExtra) {
        input.readOnly = true;
    }

    if (!getIsAuthenticated()) {
        input.readOnly = true;
        input.classList.add("readonly");
    }

    onAuthChange((authenticated) => {
        if (authenticated) {
            if (!isReadonlyExtra) {
                input.readOnly = false;
            }
            input.classList.remove("readonly");
        } else {
            input.readOnly = true;
            input.classList.add("readonly");
        }
    });

    input.addEventListener("mousedown", (e) => {
        e.stopPropagation();
        if (document.activeElement !== input) {
            e.preventDefault();
            input.focus({preventScroll: true});
        }
    });

    input.addEventListener("click", (e) => {
        e.stopPropagation();
        renderOptions(true);
    });

    input.addEventListener("focus", () => renderOptions(true));
    input.addEventListener("input", () => renderOptions(false));
    input.addEventListener("keydown", (event) => {
        if (event.key === "ArrowDown") {
            event.preventDefault();
            if (optionsEl.classList.contains("hidden")) {
                renderOptions(true);
            }
            setActiveOption(activeOptionIndex + 1);
            return;
        }
        if (event.key === "ArrowUp") {
            event.preventDefault();
            if (optionsEl.classList.contains("hidden")) {
                renderOptions(true);
            }
            if (activeOptionIndex < 0) {
                const optionNodes = optionsEl.querySelectorAll(".user-selector-option");
                setActiveOption(optionNodes.length - 1);
            } else {
                setActiveOption(activeOptionIndex - 1);
            }
            return;
        }
        if (event.key === "Enter") {
            if (!optionsEl.classList.contains("hidden") && activeOptionIndex >= 0) {
                event.preventDefault();
                selectActiveOption();
            }
            return;
        }
        if (event.key === "Escape") {
            optionsEl.classList.add("hidden");
        }
    });
    input.addEventListener("blur", () => {
        setTimeout(() => {
            optionsEl.classList.add("hidden");
            input.value = currentFullName;
            if (currentUserId) {
                input.classList.add("has-value");
            } else {
                input.classList.remove("has-value");
            }
        }, 100);
    });
    wrapper.addEventListener("mouseleave", () => {
        if (document.activeElement !== input) {
            optionsEl.classList.add("hidden");
        }
    });

    wrapper.appendChild(input);
    wrapper.appendChild(optionsEl);
    container.appendChild(wrapper);
    return container;
}

export {initUserSelector, userSelectorFormatter};
