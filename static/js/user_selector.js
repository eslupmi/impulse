import {getBaseUrl} from "./utils.js";
import {getCurrentUser, getIsAuthenticated, onAuthChange} from "./auth.js";

let assignableUsers = [];

const CLEAR_LABEL = "\u2014";

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
    input.placeholder = CLEAR_LABEL;
    if (currentUserId) {
        input.value = currentFullName;
        input.classList.add("has-value");
    }

    const optionsEl = document.createElement("div");
    optionsEl.className = "user-selector-options hidden";

    const isReadonlyExtra = currentUserId && !assignableUsers.some(u => String(u.user_id) === currentUserId) && currentFullName;
    const isFrozen = Boolean(cell.getData()._is_frozen);
    let activeOptionIndex = -1;
    let isAssigning = false;

    function setReadonlyState() {
        const readonly = isFrozen || isReadonlyExtra || !getIsAuthenticated();
        input.readOnly = readonly;
        input.classList.toggle("readonly", readonly);
    }

    function getAuthUser() {
        const authUser = getCurrentUser();
        if (!authUser?.id) {
            return null;
        }
        return assignableUsers.find(u => String(u.user_id) === String(authUser.id)) || null;
    }

    function getOtherUsers() {
        const authUser = getAuthUser();
        const authId = authUser ? String(authUser.user_id) : null;
        return assignableUsers
            .filter(u => !authId || String(u.user_id) !== authId)
            .sort((a, b) => a.full_name.localeCompare(b.full_name));
    }

    function getOptionUsers(showAll, query) {
        const authUser = getAuthUser();
        const others = getOtherUsers();
        if (showAll || !query) {
            return {authUser, others};
        }
        return {
            authUser: authUser && authUser.full_name.toLowerCase().includes(query) ? authUser : null,
            others: others.filter(u => u.full_name.toLowerCase().includes(query)),
        };
    }

    function addUserOption(user) {
        const optionEl = document.createElement("div");
        optionEl.className = "user-selector-option";
        optionEl.textContent = user.full_name;
        optionEl.dataset.userId = String(user.user_id);
        optionEl.addEventListener("mousedown", (event) => {
            event.preventDefault();
            selectUser(user);
        });
        optionsEl.appendChild(optionEl);
    }

    function addDivider() {
        const divider = document.createElement("div");
        divider.className = "user-selector-divider";
        optionsEl.appendChild(divider);
    }

    function getFirstUserOptionIndex() {
        const optionNodes = optionsEl.querySelectorAll(".user-selector-option");
        for (let i = 0; i < optionNodes.length; i++) {
            if (optionNodes[i].dataset.userId) {
                return i;
            }
        }
        return optionNodes.length > 0 ? 0 : -1;
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
        optionNodes[nextIndex].scrollIntoView({block: "nearest"});
    }

    function hideOptions() {
        optionsEl.classList.add("hidden");
    }

    function positionOptions() {
        const rect = input.getBoundingClientRect();
        optionsEl.style.top = `${rect.bottom + 1}px`;
        optionsEl.style.left = `${rect.left}px`;
        optionsEl.style.width = `${rect.width}px`;
    }

    function mountOptions() {
        if (optionsEl.parentElement !== document.body) {
            document.body.appendChild(optionsEl);
        }
    }

    function addClearOption() {
        const optionEl = document.createElement("div");
        optionEl.className = "user-selector-option";
        optionEl.textContent = CLEAR_LABEL;
        optionEl.dataset.clear = "1";
        optionEl.addEventListener("mousedown", (event) => {
            event.preventDefault();
            clearUser();
        });
        optionsEl.appendChild(optionEl);
    }

    function renderOptions(showAll = false) {
        if (isFrozen) {
            hideOptions();
            return;
        }
        const query = input.value.trim().toLowerCase();
        const {authUser, others} = getOptionUsers(showAll, query);

        optionsEl.innerHTML = "";
        if (showAll || !query) {
            addClearOption();
            if (authUser || others.length > 0) {
                addDivider();
            }
        }
        if (authUser) {
            addUserOption(authUser);
            if (others.length > 0) {
                addDivider();
            }
        }
        others.forEach(user => addUserOption(user));

        if (optionsEl.children.length > 0) {
            mountOptions();
            positionOptions();
            optionsEl.classList.remove("hidden");
            setActiveOption(getFirstUserOptionIndex());
        } else {
            activeOptionIndex = -1;
            hideOptions();
        }
    }

    function selectActiveOption() {
        const optionNodes = optionsEl.querySelectorAll(".user-selector-option");
        if (activeOptionIndex < 0 || activeOptionIndex >= optionNodes.length) {
            return;
        }
        const node = optionNodes[activeOptionIndex];
        if (node.dataset.clear) {
            clearUser();
            return;
        }
        const user = assignableUsers.find(u => String(u.user_id) === node.dataset.userId);
        if (user) {
            selectUser(user);
        }
    }

    async function clearUser() {
        if (isAssigning || !currentUserId) {
            input.value = "";
            input.classList.remove("has-value");
            hideOptions();
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
                body: JSON.stringify({uniq_id: uniqId, user_id: ""}),
            });

            if (response.ok) {
                currentUserId = "";
                currentFullName = "";
                input.value = "";
                input.classList.remove("has-value");
            } else {
                console.error("Unassignment failed:", response.status);
                input.value = currentFullName;
            }
        } catch (error) {
            console.error("Unassignment request failed:", error);
            input.value = currentFullName;
        } finally {
            isAssigning = false;
            input.disabled = false;
            hideOptions();
        }
    }

    async function selectUser(user) {
        const userId = String(user.user_id);
        if (isAssigning || userId === currentUserId) {
            input.value = currentFullName;
            hideOptions();
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
            hideOptions();
        }
    }

    setReadonlyState();

    onAuthChange(() => setReadonlyState());

    function selectInputText() {
        if (!input.readOnly) {
            input.select();
        }
    }

    input.addEventListener("mousedown", (e) => {
        e.stopPropagation();
        if (document.activeElement !== input) {
            e.preventDefault();
            input.focus({preventScroll: true});
        }
    });

    input.addEventListener("click", (e) => {
        e.stopPropagation();
        selectInputText();
        renderOptions(true);
    });

    input.addEventListener("focus", () => {
        selectInputText();
        renderOptions(true);
    });
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
            hideOptions();
        }
    });
    input.addEventListener("blur", () => {
        setTimeout(() => {
            hideOptions();
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
            hideOptions();
        }
    });

    wrapper.appendChild(input);
    container.appendChild(wrapper);
    return container;
}

export {initUserSelector, userSelectorFormatter};
