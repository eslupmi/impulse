import assert from "node:assert/strict";
import {readFile} from "node:fs/promises";
import {test} from "node:test";
import {createContext, SourceTextModule, SyntheticModule} from "node:vm";

test("assignment selector reads the API user map and excludes unavailable users", async () => {
    let users = {
        alice: {id: "U1", exists: true, full_name: "Alice"},
        bob: {id: "U2", exists: true, full_name: null},
        missing: {id: "U3", exists: false, full_name: "Missing"},
    };
    const context = createContext({
        console,
        fetch: async (url) => {
            assert.equal(url, "/impulse/assignment_users");
            return {ok: true, json: async () => users};
        },
    });
    const source = await readFile(new URL("../../static/js/user_selector.js", import.meta.url), "utf8");
    const selector = new SourceTextModule(source, {context});
    const imports = {
        "./utils.js": {getBaseUrl: () => "/impulse"},
        "./auth.js": {
            getCurrentUser: () => ({id: "U1"}),
            getIsAuthenticated: () => true,
            onAuthChange: () => {},
        },
    };
    await selector.link((name) => new SyntheticModule(Object.keys(imports[name]), function () {
        for (const [key, value] of Object.entries(imports[name])) {
            this.setExport(key, value);
        }
    }, {context}));
    await selector.evaluate();
    const {initUserSelector, getAuthUser, getAssignableUserById} = selector.namespace;

    await initUserSelector("/impulse");
    assert.equal(getAuthUser().full_name, "Alice");
    assert.equal(getAssignableUserById("U2").full_name, "bob");
    assert.equal(getAssignableUserById("U3"), null);

    users = {};
    await initUserSelector("/impulse");
    assert.equal(getAuthUser(), null);
    assert.equal(getAssignableUserById("U1"), null);
});
