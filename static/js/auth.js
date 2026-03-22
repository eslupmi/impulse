import {getBaseUrl} from "./utils.js";

let isAuthenticated = false;
const authListeners = [];

function getElements() {
    return {
        wrapper: document.getElementById("auth-controls"),
        username: document.getElementById("auth-username"),
        loginBtn: document.getElementById("auth-login-btn"),
        logoutBtn: document.getElementById("auth-logout-btn"),
    };
}

function getNextPath() {
    return `${globalThis.location.pathname}${globalThis.location.search}`;
}

function setUiState(authenticated, userData) {
    const {wrapper, username} = getElements();
    if (!wrapper) {
        return;
    }

    if (authenticated && userData) {
        const displayName = userData.full_name || userData.username || userData.email || userData.id || "user";
        username.textContent = displayName;
        wrapper.classList.add("logged-in");
    } else {
        username.textContent = "";
        wrapper.classList.remove("logged-in");
    }
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
            setUiState(false, null);
            return;
        }

        const payload = await response.json();
        isAuthenticated = Boolean(payload?.authenticated);
        setUiState(isAuthenticated, payload?.user);
        authListeners.forEach(cb => cb(isAuthenticated));
    } catch {
        isAuthenticated = false;
        setUiState(false, null);
        authListeners.forEach(cb => cb(false));
    }
}

async function handleLogin() {
    const baseUrl = getBaseUrl();
    const loginUrl = `${baseUrl}/auth/login?next=${encodeURIComponent(getNextPath())}`;
    globalThis.location.assign(loginUrl);
}

async function handleLogout() {
    const baseUrl = getBaseUrl();
    await fetch(`${baseUrl}/auth/logout`, {
        method: "POST",
        credentials: "same-origin",
    });
    isAuthenticated = false;
    setUiState(false, null);
    authListeners.forEach(cb => cb(false));
}

async function initAuthControls() {
    const {loginBtn, logoutBtn} = getElements();
    if (!loginBtn || !logoutBtn) {
        return;
    }

    loginBtn.addEventListener("click", handleLogin);
    logoutBtn.addEventListener("click", handleLogout);

    await refreshAuthState();
}

function getIsAuthenticated() {
    return isAuthenticated;
}

function onAuthChange(callback) {
    authListeners.push(callback);
}

export {initAuthControls, getIsAuthenticated, onAuthChange};
