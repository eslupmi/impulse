import {table} from "./table.js";

// Apply sorting to the Tabulator instance
function initializeSorting(columns, sorters) {
    const tableSorting = sorters.map(sorter => {
        const rule = {
            column: sorter.column,
            dir: sorter.direction || "asc",
        };

        if (sorter.order) {
            rule.sorter = function (a, b, aRow, bRow, column, dir, sorterParams) {
                const order = sorterParams;
                const indexA = order.indexOf(a) !== -1 ? order.indexOf(a) : order.length;
                const indexB = order.indexOf(b) !== -1 ? order.indexOf(b) : order.length;
                return indexA - indexB;
            };
            rule.sorterParams = sorter.order;
        }

        return rule;
    });

    columns.forEach(column => {
        const columnSorter = tableSorting.find(sorter => sorter.column === column.field);
        if (columnSorter) {
            column.sorter = columnSorter.sorter;
            column.sorterParams = columnSorter.sorterParams || undefined;
        }
    });

    table.setColumns(columns);
    const urlSorters = loadSortingFromURL();
    if (urlSorters.length > 0) {
        table.setSort(urlSorters);
    } else {
        saveSortingToURL(tableSorting);
        table.setSort(tableSorting.reverse());
    }
}

// Save current sorting state to URL
function saveSortingToURL(sorters) {
    const urlParams = new URLSearchParams(window.location.search);
    const sortString = sorters
        .map(s => `${s.column}:${s.dir}`)
        .join(",");

    urlParams.set("sort", sortString);
    window.history.replaceState({}, "", `${window.location.pathname}?${urlParams}`);
}

// Load sorting from URL
function loadSortingFromURL() {
    const urlParams = new URLSearchParams(window.location.search);
    const sortString = urlParams.get("sort");

    if (!sortString) return [];

    return sortString.split(",").map(sorterStr => {
        const [column, dir] = sorterStr.split(":");
        return { column, dir: dir || "asc" };
    });
}

// Attach listener to update URL on manual sorting
function setupSortingListener() {
    table.on("dataSorted", (sorters, rows) => {
        const urlSorters = sorters.map(sorter => ({
            column: sorter.field,
            dir: sorter.dir,
        }));
        saveSortingToURL(urlSorters);
    });
}

export { initializeSorting, loadSortingFromURL, setupSortingListener };
