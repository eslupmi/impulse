import {getBaseUrl} from "./utils.js";

let isAuthenticated = false;

function getElements() {
    return {
        status: document.getElementById("auth-status"),
        button: document.getElementById("auth-action-btn"),
    };
}

function getAuthErrorFromQuery() {
    const params = new URLSearchParams(window.location.search);
    const authError = params.get("auth_error");
    return authError || "";
}

function getNextPath() {
    return `${window.location.pathname}${window.location.search}`;
}

function setUiState(authenticated, userData, authError = "") {
    const {status, button} = getElements();
    if (!status || !button) {
        return;
    }

    if (authenticated) {
        const username = userData?.username || userData?.full_name || userData?.email || userData?.id || "user";
        status.textContent = `auth: ${username}`;
    } else if (authError) {
        status.textContent = `auth error: ${authError}`;
    } else {
        status.textContent = "auth: anonymous";
    }

    button.textContent = authenticated ? "Logout" : "Login";
    button.title = authenticated ? "Log out from current session" : "Authenticate with messenger";
}

async function refreshAuthState() {
    const baseUrl = getBaseUrl();
    try {
        const response = await fetch(`${baseUrl}/auth/me`, {
            method: "GET",
            credentials: "same-origin",
        });

        if (!response.ok) {
            isAuthenticated = false;
            setUiState(false, null, "me_failed");
            return;
        }

        const payload = await response.json();
        isAuthenticated = Boolean(payload?.authenticated);
        setUiState(isAuthenticated, payload?.user, getAuthErrorFromQuery());
    } catch (error) {
        isAuthenticated = false;
        setUiState(false, null, "network_error");
    }
}

async function handleAuthAction() {
    const baseUrl = getBaseUrl();
    if (isAuthenticated) {
        await fetch(`${baseUrl}/auth/logout`, {
            method: "POST",
            credentials: "same-origin",
        });
        isAuthenticated = false;
        setUiState(false, null);
        return;
    }

    const loginUrl = `${baseUrl}/auth/login?next=${encodeURIComponent(getNextPath())}`;
    window.location.assign(loginUrl);
}

async function initAuthControls() {
    const {button} = getElements();
    if (!button) {
        return;
    }

    button.addEventListener("click", async () => {
        await handleAuthAction();
    });

    await refreshAuthState();
}

export {initAuthControls};
