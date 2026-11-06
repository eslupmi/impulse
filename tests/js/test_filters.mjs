// Run with: node --experimental-vm-modules --test tests/js/test_filters.mjs
import assert from "node:assert/strict";
import {readFile} from "node:fs/promises";
import test from "node:test";
import {createContext, SourceTextModule, SyntheticModule} from "node:vm";

const element = () => ({
    classList: {add() {}, remove() {}},
    appendChild() {}, addEventListener() {},
});
const calls = [];
const table = {
    getColumns: () => ["status", "incident.uniq_id"].map(field => ({getField: () => field})),
    getRows: () => [],
    clearFilter: () => { calls.length = 0; },
    addFilter: (...args) => calls.push(args),
};
const window = {
    location: new URL("https://impulse.example/"),
    history: {replaceState: (_, __, path) => { window.location = new URL(path, window.location); }},
};
const context = createContext({
    URLSearchParams, window,
    document: {getElementById: element, createElement: element, querySelectorAll: () => []},
});
const matcher = new SourceTextModule(await readFile(new URL("../../static/js/matcher.js", import.meta.url), "utf8"), {context});
const filters = new SourceTextModule(await readFile(new URL("../../static/js/filters.js", import.meta.url), "utf8"), {context});
await filters.link(specifier => specifier === "./matcher.js" ? matcher : new SyntheticModule(
    ["table"], function () { this.setExport("table", table); }, {context},
));
await filters.evaluate();
const api = filters.namespace;

function apply(query) {
    window.location.search = new URLSearchParams({filters: query}).toString();
    api.loadFiltersFromURL();
    assert.equal(calls.length, 1);
    return calls[0];
}

function matches(query, row) {
    const [callback, parameters] = apply(query);
    assert.equal(typeof callback, "function");
    return callback(row, parameters);
}

test("incident syntax is accepted only by UI filters, with existing quote styles", () => {
    for (const quote of ['"', "'", "`"]) {
        const query = `incident.uniq_id=${quote}abc${quote}`;
        const parsed = api.parseFilterString(` ${query} `);
        assert.equal(parsed.field, "incident.uniq_id");
        assert.equal(parsed.value, "abc");
        assert.equal(api.validateAndFormatFilter(query), query);
        assert.equal(matcher.namespace.validateMatcher(query).ok, false);
    }
    for (const query of ['incident.="x"', 'incident.payload.status="x"', 'payload.status="x"']) {
        assert.equal(api.parseFilterString(query), null);
    }
    assert.equal(api.validateMatchersCommaSeparated('incident.status="firing",severity!="info"').ok, true);
    assert.equal(api.validateMatcherClause('incident.status=~"["').ok, false);
});

test("incident filters use literal property keys ahead of columns or labels", () => {
    const row = {"incident.uniq_id": "ABC", _responsive_data: {group_labels: {"incident.uniq_id": "spoof"}}};
    assert.equal(matches('incident.uniq_id="abc"', row), true);
    assert.equal(matches('incident.uniq_id!="abc"', row), false);
    assert.equal(matches('incident.uniq_id="spoof"', row), false);
    for (const operator of ["=", "!=", "=~", "!~"]) {
        assert.equal(matches(`incident.unknown${operator}"spoof"`, {
            _responsive_data: {group_labels: {"incident.unknown": "spoof"}},
        }), false);
    }
    assert.equal(matches('incident.uniq_id="abc"', Object.create({"incident.uniq_id": "abc"})), false);
});

test("incident regex filters are anchored, case insensitive, and preserve escape meaning", () => {
    const row = {"incident.status": "FIRING"};
    assert.equal(matches('incident.status=~"firing|resolved"', row), true);
    assert.equal(matches('incident.status!~"firing|resolved"', row), false);
    assert.equal(matches('incident.status=~"fir"', row), false);
    assert.equal(matches('incident.status=~"firing|resolved"', {"incident.status": "firing-extra"}), false);
    assert.equal(matches('incident.status!~"firing|resolved"', {"incident.status": "extra-resolved"}), true);
    assert.equal(matches(String.raw`incident.status=~"\D+"`, row), true);
    assert.equal(matches(String.raw`incident.status!~"\D+"`, row), false);
    window.location.search = new URLSearchParams({filters: 'incident.status=~"["'}).toString();
    api.loadFiltersFromURL();
    assert.equal(calls.length, 0);
});

test("configured false, zero, and null properties remain searchable", () => {
    for (const [value, expected] of [[false, "false"], [0, "0"], [null, ""]]) {
        assert.equal(matches(`incident.value="${expected}"`, {"incident.value": value}), true);
    }
});

test("default filters populate the URL and existing column and label filters keep working", () => {
    window.location.search = "";
    api.loadFiltersFromArrayToURL(['incident.status="firing"']);
    assert.equal(window.location.searchParams.get("filters"), 'incident.status="firing"');
    api.loadFiltersFromURL();
    assert.equal(calls[0][0]({"incident.status": "firing"}, calls[0][1]), true);
    assert.deepEqual(apply('status="firing"'), ["status", "=", "firing"]);
    assert.equal(matches('severity="critical"', {_responsive_data: {common_labels: {severity: "critical"}}}), true);
    assert.equal(matches('severity!="critical"', {_responsive_data: {common_labels: {severity: "critical"}}}), false);
});
