const mountRegistry = new Map();
const loadedScripts = new Set();
const loadedStyles = new Set();

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

function mountExtensionPoint(mountPoint, container, context = {}) {
    const callbacks = mountRegistry.get(mountPoint) || [];
    callbacks.forEach((callback) => {
        try {
            callback(container, context);
        } catch (error) {
            console.error(`Extension mount failed for ${mountPoint}:`, error);
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
        script.onerror = () => reject(new Error(`Failed to load extension script: ${url}`));
        document.body.appendChild(script);
    });
}

async function initializeFrontendExtensions(manifests = []) {
    window.ImpulseExtensions = window.ImpulseExtensions || {
        registerMount,
        mount: mountExtensionPoint,
    };

    for (const manifest of manifests) {
        try {
            await loadStyle(manifest.style_url);
            await loadScript(manifest.script_url);
        } catch (error) {
            console.error("Failed to load frontend extension:", manifest.extension_id, error);
        }
    }
}

window.ImpulseExtensions = window.ImpulseExtensions || {
    registerMount,
    mount: mountExtensionPoint,
};

export {initializeFrontendExtensions, mountExtensionPoint};
