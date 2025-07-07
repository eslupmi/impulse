import {table} from "./table.js";
const defaultSorting = [];

// Apply sorting to the Tabulator instance
function initializeSorting(columns, sorters) {
    columns.forEach(column => {
        const columnSorter = sorters.find(sorter => sorter.column === column.field);
        if (columnSorter?.order) {
            column.sorter = (a, b, aRow, bRow, column, dir, sorterParams) => {
                const order = sorterParams;
                const indexA = order.indexOf(a) !== -1 ? order.indexOf(a) : order.length;
                const indexB = order.indexOf(b) !== -1 ? order.indexOf(b) : order.length;
                return indexA - indexB;
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
        const defaultSortingCopy = defaultSorting.map(sorter => ({
            column: sorter.column,
            dir: sorter.dir
        }));
        table.setSort(defaultSortingCopy);
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
    
    const queryString = urlParams.toString();
    const newUrl = queryString ? `${window.location.pathname}?${queryString}` : window.location.pathname;
    window.history.replaceState({}, "", newUrl);
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

// Check if current sorting matches default sorting
function isDefaultSorting(sorters) {
    if (sorters.length !== defaultSorting.length) return false;
    
    return sorters.every((sorter, index) => {
        const defaultSorter = defaultSorting[index];
        return sorter.column === defaultSorter.column && sorter.dir === defaultSorter.dir;
    });
}

// Attach listener to update URL on manual sorting
function setupSortingListener() {
    table.on("dataSorted", (sorters, rows) => {
        const urlSorters = sorters.map(sorter => ({
            column: sorter.field,
            dir: sorter.dir,
        }));
        
        // Don't save to URL if it matches default sorting
        if (isDefaultSorting(urlSorters)) {
            saveSortingToURL([]); // Clear sorting from URL
        } else {
            saveSortingToURL(urlSorters);
        }
    });
}

export { initializeSorting, loadSortingFromURL, setupSortingListener };
