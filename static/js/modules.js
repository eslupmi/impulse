import {getSocket} from "./websocket.js";

const mountRegistry = new Map();
const loadedScripts = new Set();
const loadedStyles = new Set();

const pendingModuleMessages = new Map();
let moduleMessageSeq = 0;
const MODULE_MESSAGE_TIMEOUT_MS = 15000;

/** OSS calls mountModulePoint("app.ready", document.body) after scripts load; modules choose DOM targets. */

function normalizeUrl(url) {
    if (!url) return null;
    if (/^https?:\/\//.test(url)) return url;
    return url.startsWith("/") ? `${window.location.origin}${url}` : url;
}

function registerMount(mountPoint, callback) {
    if (!mountPoint || typeof callback !== "function") return;
    const callbacks = mountRegistry.get(mountPoint) || [];
    callbacks.push(callback);
    mountRegistry.set(mountPoint, callbacks);
}

function mountModulePoint(mountPoint, container, context = {}) {
    const callbacks = mountRegistry.get(mountPoint) || [];
    callbacks.forEach((callback) => {
        try {
            callback(container, context);
        } catch (error) {
            console.error(`Module mount failed for ${mountPoint}:`, error);
        }
    });
    return callbacks.length;
}

function loadStyle(url) {
    const normalizedUrl = normalizeUrl(url);
    if (!normalizedUrl || loadedStyles.has(normalizedUrl)) {
        return Promise.resolve();
    }

    loadedStyles.add(normalizedUrl);
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = normalizedUrl;
    document.head.appendChild(link);
    return Promise.resolve();
}

function loadScript(url) {
    const normalizedUrl = normalizeUrl(url);
    if (!normalizedUrl || loadedScripts.has(normalizedUrl)) {
        return Promise.resolve();
    }

    loadedScripts.add(normalizedUrl);
    return new Promise((resolve, reject) => {
        const script = document.createElement("script");
        script.src = normalizedUrl;
        script.async = false;
        script.onload = resolve;
        script.onerror = () => reject(new Error(`Failed to load module script: ${url}`));
        document.body.appendChild(script);
    });
}

/**
 * Send a request/response message to a backend module hook over the main OSS
 * websocket. Resolves with the handler's ``data`` payload or rejects with an
 * Error carrying the server-provided error ``code``.
 */
function sendModuleMessage(moduleName, hook, params = {}, {timeoutMs = MODULE_MESSAGE_TIMEOUT_MS} = {}) {
    const socket = getSocket();
    if (!socket || socket.readyState !== WebSocket.OPEN) {
        return Promise.reject(new Error("WebSocket is not connected"));
    }

    const requestId = `mm-${Date.now()}-${++moduleMessageSeq}`;
    return new Promise((resolve, reject) => {
        const timer = window.setTimeout(() => {
            pendingModuleMessages.delete(requestId);
            reject(new Error(`module_message '${moduleName}.${hook}' timed out`));
        }, timeoutMs);

        pendingModuleMessages.set(requestId, {resolve, reject, timer});
        socket.send(JSON.stringify({
            event: "module_message",
            module: moduleName,
            hook,
            request_id: requestId,
            params,
        }));
    });
}

/** Called by websocket.js when a module_message response arrives. */
function resolveModuleMessage(message) {
    const requestId = message && message.request_id;
    if (!requestId || !pendingModuleMessages.has(requestId)) return;

    const {resolve, reject, timer} = pendingModuleMessages.get(requestId);
    window.clearTimeout(timer);
    pendingModuleMessages.delete(requestId);

    if (message.ok) {
        resolve(message.data);
    } else {
        const error = new Error((message.error && message.error.message) || "module_message failed");
        error.code = message.error && message.error.code;
        reject(error);
    }
}

async function initializeFrontendModules(manifests = []) {
    for (const manifest of manifests) {
        try {
            await loadStyle(manifest.style_url);
            await loadScript(manifest.script_url);
        } catch (error) {
            console.error("Failed to load frontend module:", manifest.module_id, error);
        }
    }
}

window.ImpulseModules = window.ImpulseModules || {};
Object.assign(window.ImpulseModules, {
    registerMount,
    mount: mountModulePoint,
    sendModuleMessage,
    _resolveModuleMessage: resolveModuleMessage,
});

export {initializeFrontendModules, mountModulePoint};
