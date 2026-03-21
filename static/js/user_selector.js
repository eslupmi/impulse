import {getBaseUrl} from "./utils.js";

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

    const currentUserId = String(cell.getData()._assigned_user_id || "");
    const currentFullName = cell.getData()._assigned_fullname || "";

    const select = document.createElement("select");
    select.className = "user-selector";

    if (!currentUserId) {
        const emptyOption = document.createElement("option");
        emptyOption.value = "";
        emptyOption.textContent = "\u2014";
        emptyOption.selected = true;
        select.appendChild(emptyOption);
    }

    let currentInList = false;
    assignableUsers.forEach(user => {
        const option = document.createElement("option");
        option.value = user.user_id;
        option.textContent = user.full_name;
        if (String(user.user_id) === currentUserId) {
            option.selected = true;
            currentInList = true;
        }
        select.appendChild(option);
    });

    if (currentUserId && !currentInList && currentFullName) {
        const extraOption = document.createElement("option");
        extraOption.value = currentUserId;
        extraOption.textContent = currentFullName;
        extraOption.selected = true;
        extraOption.disabled = true;
        select.insertBefore(extraOption, select.children[1]);
    }

    if (currentUserId) {
        select.classList.add("has-value");
    }

    select.addEventListener("click", (e) => {
        e.stopPropagation();
    });

    select.addEventListener("change", async (e) => {
        e.stopPropagation();
        const selectedUserId = select.value;
        if (!selectedUserId) return;

        const uniqId = cell.getData().uniq_id;
        select.disabled = true;

        try {
            const baseUrl = getBaseUrl();
            const response = await fetch(`${baseUrl}/assign`, {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({uniq_id: uniqId, user_id: selectedUserId}),
            });

            if (!response.ok) {
                console.error("Assignment failed:", response.status);
                select.value = currentUserId || "";
            } else {
                select.classList.add("has-value");
                const emptyOpt = select.querySelector('option[value=""]');
                if (emptyOpt) emptyOpt.remove();
            }
        } catch (error) {
            console.error("Assignment request failed:", error);
            select.value = currentUserId || "";
        } finally {
            select.disabled = false;
        }
    });

    container.appendChild(select);
    return container;
}

function getAssignableUsers() {
    return assignableUsers;
}

export {initUserSelector, userSelectorFormatter, getAssignableUsers};
