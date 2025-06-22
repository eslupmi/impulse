import {table} from "./table.js";

// Apply sorting to the Tabulator instance
function initializeSorting(columns, sorters) {
    const defaultSorting = [];
    
    columns.forEach(column => {
        const columnSorter = sorters.find(sorter => sorter.column === column.field);
        if (columnSorter?.order) {
            column.sorter = (a, b, aRow, bRow, column, dir, sorterParams) => {
                const order = sorterParams;
                const indexA = order.indexOf(a) !== -1 ? order.indexOf(a) : order.length;
                const indexB = order.indexOf(b) !== -1 ? order.indexOf(b) : order.length;
                return indexB - indexA;
            };
            column.sorterParams = columnSorter.order;
        }
    });

    sorters.forEach(sorter => {
        if (sorter.direction && sorter.direction !== "none") {
            defaultSorting.push({
                column: sorter.column,
                dir: sorter.direction
            });
        }
    });

    table.setColumns(columns);
    const urlSorters = loadSortingFromURL();
    if (urlSorters.length > 0) {
        table.setSort(urlSorters);
    } else if (defaultSorting.length > 0) {
        saveSortingToURL(defaultSorting);
        table.setSort(defaultSorting.reverse());
    }
}

// Save current sorting state to URL
function saveSortingToURL(sorters) {
    const urlParams = new URLSearchParams(window.location.search);
    
    if (sorters?.length > 0) {
        urlParams.set("sort", sorters.map(s => `${s.column}:${s.dir}`).join(","));
    } else {
        urlParams.delete("sort");
    }
    
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
