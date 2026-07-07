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

function createUserSelector({
    userId: initialUserId = "",
    fullName: initialFullName = "",
    inputId = "",
    allowClear = true,
    readonlyExtra = false,
    frozen = false,
    onSelectUser,
    onClearUser,
}) {
    let currentUserId = String(initialUserId || "");
    let currentFullName = initialFullName || "";

    const container = document.createElement("div");
    container.className = "user-selector-container";

    const wrapper = document.createElement("div");
    wrapper.className = "user-selector-wrapper";

    const input = document.createElement("input");
    input.type = "text";
    input.className = "user-selector";
    input.autocomplete = "off";
    input.placeholder = CLEAR_LABEL;
    if (inputId) {
        input.id = inputId;
    }
    if (currentUserId) {
        input.value = currentFullName;
        input.classList.add("has-value");
    }

    const optionsEl = document.createElement("div");
    optionsEl.className = "user-selector-options hidden";

    let activeOptionIndex = -1;
    let isBusy = false;

    function setReadonlyState() {
        const readonly = frozen || readonlyExtra || !getIsAuthenticated();
        input.readOnly = readonly;
        input.classList.toggle("readonly", readonly);
    }

    function addUserOption(user) {
        const optionEl = document.createElement("div");
        optionEl.className = "user-selector-option";
        optionEl.textContent = user.full_name;
        optionEl.dataset.userId = String(user.user_id);
        optionEl.addEventListener("mousedown", (event) => {
            event.preventDefault();
            applyUserSelection(user);
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
            applyClearSelection();
        });
        optionsEl.appendChild(optionEl);
    }

    function renderOptions(showAll = false) {
        if (frozen) {
            hideOptions();
            return;
        }
        const query = input.value.trim().toLowerCase();
        const {authUser, others} = getOptionUsers(showAll, query);

        optionsEl.innerHTML = "";
        if (allowClear && (showAll || !query)) {
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

    function setLocalValue(userId, fullName) {
        currentUserId = String(userId || "");
        currentFullName = fullName || "";
        input.value = currentFullName;
        if (currentUserId) {
            input.classList.add("has-value");
        } else {
            input.classList.remove("has-value");
        }
    }

    function selectActiveOption() {
        const optionNodes = optionsEl.querySelectorAll(".user-selector-option");
        if (activeOptionIndex < 0 || activeOptionIndex >= optionNodes.length) {
            return;
        }
        const node = optionNodes[activeOptionIndex];
        if (node.dataset.clear) {
            applyClearSelection();
            return;
        }
        const user = assignableUsers.find(u => String(u.user_id) === node.dataset.userId);
        if (user) {
            applyUserSelection(user);
        }
    }

    async function applyClearSelection() {
        if (isBusy) {
            return;
        }
        if (!currentUserId) {
            setLocalValue("", "");
            hideOptions();
            return;
        }

        if (onClearUser) {
            isBusy = true;
            input.disabled = true;
            try {
                const success = await onClearUser();
                if (success) {
                    setLocalValue("", "");
                } else {
                    input.value = currentFullName;
                }
            } finally {
                isBusy = false;
                input.disabled = false;
                hideOptions();
            }
            return;
        }

        setLocalValue("", "");
        hideOptions();
    }

    async function applyUserSelection(user) {
        const userId = String(user.user_id);
        if (isBusy || userId === currentUserId) {
            input.value = currentFullName;
            hideOptions();
            return;
        }

        if (onSelectUser) {
            isBusy = true;
            input.disabled = true;
            try {
                const success = await onSelectUser(user);
                if (success) {
                    setLocalValue(userId, user.full_name);
                } else {
                    input.value = currentFullName;
                }
            } finally {
                isBusy = false;
                input.disabled = false;
                hideOptions();
            }
            return;
        }

        setLocalValue(userId, user.full_name);
        hideOptions();
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

    return {
        element: container,
        getValue() {
            return {userId: currentUserId, fullName: currentFullName};
        },
        setValue(userId, fullName) {
            setLocalValue(userId, fullName);
        },
        setDefaultToAuthUser() {
            const authUser = getAuthUser();
            if (authUser) {
                setLocalValue(authUser.user_id, authUser.full_name);
            }
        },
        destroy() {
            optionsEl.remove();
            container.remove();
        },
    };
}

function userSelectorFormatter(cell) {
    const indicator = cell.getData().indicator;
    if (indicator === "closed" || indicator === "deleted") {
        const empty = document.createElement("div");
        empty.className = "user-selector-container";
        return empty;
    }

    const currentUserId = String(cell.getData()._assigned_user_id || "");
    const currentFullName = cell.getData()._assigned_fullname || "";
    const isReadonlyExtra = currentUserId
        && !assignableUsers.some(u => String(u.user_id) === currentUserId)
        && currentFullName;

    const selector = createUserSelector({
        userId: currentUserId,
        fullName: currentFullName,
        allowClear: true,
        readonlyExtra: Boolean(isReadonlyExtra),
        frozen: Boolean(cell.getData()._is_frozen),
        onSelectUser: async (user) => {
            const uniqId = cell.getData().uniq_id;
            const baseUrl = getBaseUrl();
            const response = await fetch(`${baseUrl}/assign`, {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                credentials: "same-origin",
                body: JSON.stringify({uniq_id: uniqId, user_id: String(user.user_id)}),
            });
            if (!response.ok) {
                console.error("Assignment failed:", response.status);
            }
            return response.ok;
        },
        onClearUser: async () => {
            const uniqId = cell.getData().uniq_id;
            const baseUrl = getBaseUrl();
            const response = await fetch(`${baseUrl}/assign`, {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                credentials: "same-origin",
                body: JSON.stringify({uniq_id: uniqId, user_id: ""}),
            });
            if (!response.ok) {
                console.error("Unassignment failed:", response.status);
            }
            return response.ok;
        },
    });

    return selector.element;
}

function getAssignableUserById(userId) {
    return assignableUsers.find(u => String(u.user_id) === String(userId)) || null;
}

export {initUserSelector, userSelectorFormatter, createUserSelector, getAuthUser, getAssignableUserById};
