const socket = io.connect(location.origin);

// Formatters for different column types
const formatterMap = {
    "datetime": cell => formatTimestamp(cell.getValue()),
    "link": "link",
};

function formatTimestamp(unixTimestamp) {
    const date = new Date(unixTimestamp * 1000);
    return date.toLocaleString(navigator.language, {
        timeZone: Intl.DateTimeFormat().resolvedOptions().timeZone
    });
}

// Formatter parameters (for links, etc.)
const formatterParamsMap = {
    "link": (data) => {
        return {
            urlField: data.urlField,
            urlPrefix: "",
            target: "_blank",
        };
    },
};

// Custom sorters
const sorterMap = {
    "datetime": (a, b) => a - b,
    "link": "string",
};

// Mapping of custom filter operators to Tabulator's built-in operators
const tabulatorOperators = {
    "=": "=",
    "!=": "!=",
    "=~": "regex",
    "!~": "regex",
    // Additional operators from Tabulator
    "like": "like",
    "keywords": "keywords",
    "starts": "starts",
    "ends": "ends",
    "<": "<",
    "<=": "<=",
    ">": ">",
    ">=": ">=",
    "in": "in",
    "regex": "regex"
};
const symbolicOperators = ["=", ">", "<", ">=", "<=", "!=", "=~", "!~"];

// Initialize Tabulator instance
const table = new Tabulator("#data-table", {
    layout: "fitData",
    index: "uuid",
});

// Fetch table configuration and sorting, then initialize the table
async function initializeTable() {
    try {
        const [configResponse, sortingResponse] = await Promise.all([
            fetch('/table_config').then(res => res.json()),
            fetch('/table_sorting').then(res => res.json())
        ]);

        const columns = configResponse.map(column => {
            const columnSorter = column.type in sorterMap ? sorterMap[column.type] : "string"
            let cssClass = columnSorter === "string" ? "clickable-cell" : "unclickable-cell";
            cssClass += ` ${column.type || "regular"}-field`;
            return {
                title: column.title,
                field: column.field,
                visible: column.visible !== undefined ? column.visible : true,
                sorter: columnSorter,
                formatter: formatterMap[column.type] || undefined,
                formatterParams: column.type in formatterParamsMap ? formatterParamsMap[column.type](column) : undefined,
                cssClass: cssClass,
            }
        });

        applySorting(columns, sortingResponse);
    } catch (error) {
        console.error("Error initializing table:", error);
    }
}

// Apply sorting to the Tabulator instance
function applySorting(columns, sorters) {
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
    table.setSort(tableSorting.reverse());
}

// Show or hide filter error
function showFilterError(message) {
    const errorDiv = document.getElementById("filter-error");
    const filterInput = document.getElementById("filter-input");

    if (message) {
        errorDiv.innerText = message;
        errorDiv.classList.remove("hidden");
        filterInput.classList.add("has-error");
    } else {
        errorDiv.classList.add("hidden");
        filterInput.classList.remove("has-error");
    }
}

// Custom Negative Regex Filter for Tabulator
function customNegativeRegexFilter(rowData, parameters) {
    const cellValue = rowData[parameters.field];
    const regex = new RegExp(parameters.value, "i");

    return !regex.test(cellValue);
}

// Initialize filters from URL
function loadFiltersFromURL() {
    const urlParams = new URLSearchParams(window.location.search);
    const filters = urlParams.get("filters") ? urlParams.get("filters").split(",") : [];

    filters.forEach(filter => addFilterUI(filter));
    applyFilters();
}

// Improved filter parsing logic
function parseFilterString(filterString) {
    // Match filters in the form: key operator value (with optional quotes)
    const match = filterString.match(/^(.+?)(=~|!~|=|!=|like|keywords|starts|ends|<|<=|>|>=|in|regex)(.*)$/);

    if (!match) {
        showFilterError("Invalid filter format. Use format like status=\"firing\".");
        return;
    }

    let [, field, operator, value] = match;

    field = field.trim();
    operator = operator.trim();
    value = value.trim();

    return {field, operator, value};
}

// Validate if a string is a valid regex pattern
function isValidRegex(pattern) {
    try {
        new RegExp(pattern);
        return true;
    } catch (e) {
        return false;
    }
}

// Apply filters to Tabulator table
function applyFilters() {
    const urlParams = new URLSearchParams(window.location.search);
    const filters = urlParams.get("filters") ? urlParams.get("filters").split(",") : [];

    table.clearFilter();
    showFilterError(null);

    filters.forEach(filter => {
        const parsedFilter = parseFilterString(filter);
        if (parsedFilter) {
            let {field, operator, value} = parsedFilter;

            value = value.replace(/^["']|["']$/g, '');
            if (operator === "=~" || operator === "!~") {
                if (!isValidRegex(value)) {
                    showFilterError(`Invalid regex: ${value}`);
                    return;
                }

                const anchoredRegex = `^${value}$`;

                if (operator === "=~") {
                    table.addFilter(field, "regex", anchoredRegex);
                } else {
                    table.addFilter(field, customNegativeRegexFilter, anchoredRegex);
                }
            } else if (tabulatorOperators[operator]) {
                table.addFilter(field, tabulatorOperators[operator], value);
            } else {
                console.warn(`Unsupported filter operator: ${operator}`);
            }
        }
    });
}

// Add a new filter to the UI
function addFilterUI(filter) {
    const filterContainer = document.getElementById("filter-container");

    // Create filter element
    const filterElement = document.createElement("div");
    filterElement.classList.add("filter-badge");

    // Filter text
    const filterText = document.createElement("span");
    filterText.innerText = filter;
    filterElement.appendChild(filterText);

    // Remove button
    const removeButton = document.createElement("span");
    removeButton.innerText = "✖";
    removeButton.addEventListener("click", () => removeFilter(filter, filterElement));
    filterElement.appendChild(removeButton);

    filterContainer.appendChild(filterElement);
}

// Remove a filter from the UI and URL
function removeFilter(filter, filterElement) {
    const urlParams = new URLSearchParams(window.location.search);
    let filters = urlParams.get("filters") ? urlParams.get("filters").split(",") : [];

    filters = filters.filter(f => f !== filter);
    urlParams.set("filters", filters.join(","));
    window.history.replaceState({}, "", `?${urlParams.toString()}`);

    filterElement.remove();
    applyFilters();
}

// Add filtering from table clicks (cell values) and input
function setupTableFiltering() {
    // Add a filter from the input field
    document.getElementById("filter-input").addEventListener("keypress", function (event) {
        if (event.key === "Enter") {
            const query = this.value.trim();
            if (!query) return;

            const parsedFilter = parseFilterString(query);
            if (!parsedFilter) {
                alert("Invalid filter format. Use format like status=\"firing\".");
                return;
            }

            let {field, operator, value} = parsedFilter;

            if ((operator === "=~" || operator === "!~") && !isValidRegex(value)) {
                showFilterError(`Invalid regex: ${value}`);
                return;
            }

            const formattedFilter = operator in symbolicOperators ? `${field}${operator}${value}` : `${field} ${operator} ${value}`;

            const urlParams = new URLSearchParams(window.location.search);
            let filters = urlParams.get("filters") ? urlParams.get("filters").split(",") : [];

            if (!filters.includes(formattedFilter)) {
                filters.push(formattedFilter);
                urlParams.set("filters", filters.join(","));
                window.history.replaceState({}, "", `?${urlParams.toString()}`);

                addFilterUI(formattedFilter);
                applyFilters();
            }

            this.value = "";
        }
    });

    // Add filtering from table clicks
    table.on("cellClick", (e, cell) => {
        if (cell.getElement().classList.contains("unclickable-cell")) return;
        console.log(e.target.tagName);
        if (e.target.tagName === "A") {
            e.stopPropagation(); // ✅ Prevents event from bubbling to `cellClick`
            return;
        }


        const field = cell.getColumn().getField();
        const value = cell.getValue();
        const newFilter = `${field}="${value}"`;

        const urlParams = new URLSearchParams(window.location.search);
        let filters = urlParams.get("filters") ? urlParams.get("filters").split(",") : [];

        if (!filters.includes(newFilter)) {
            filters.push(newFilter);
            urlParams.set("filters", filters.join(","));
            window.history.replaceState({}, "", `?${urlParams.toString()}`);

            addFilterUI(newFilter);
            applyFilters();
        }
    });

}

// Handle WebSocket Events
function setupWebSocketEvents() {
    socket.on("add_row", rowData => {
        table.addRow(rowData);
        table.setSort(table.getSorters());
    });

    socket.on("update_row", rowData => {
        table.updateOrAddData([rowData]);
        table.setSort(table.getSorters());
    });

    socket.on("remove_row", rowData => {
        const rows = table.searchRows('uuid', '=', rowData.uuid);
        rows.forEach(row => row.delete());
    });

    socket.on("update_data", data => {
        table.setData(data);
        table.setSort(table.getSorters());
    });

    // Request initial data from WebSocket
    socket.emit("request_data");
}

// **Initialize Everything**
initializeTable();
loadFiltersFromURL();
setupTableFiltering();
setupWebSocketEvents();
