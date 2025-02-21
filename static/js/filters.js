import {table} from "./table.js";

const symbolicOperators = ["=", ">", "<", ">=", "<=", "!=", "=~", "!~"];
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

// Validate regex pattern
function isValidRegex(pattern) {
    try {
        new RegExp(pattern);
        return true;
    } catch (e) {
        return false;
    }
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
function loadFiltersFromArrayToURL(filters) {
    const urlParams = new URLSearchParams(window.location.search);
    const activeFilters = urlParams.get("filters") ? urlParams.get("filters").split(",") : [];

    if (!activeFilters.length) {
        urlParams.set("filters", filters.join(","));
        window.history.replaceState({}, "", `?${urlParams.toString()}`);
    }
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
                    table.addFilter(customNegativeRegexFilter, {field: field, value: anchoredRegex});
                }
            } else if (tabulatorOperators[operator]) {
                table.addFilter(field, tabulatorOperators[operator], value);
            } else {
                console.warn(`Unsupported filter operator: ${operator}`);
            }
        }
    });
}

// Update filter container layout dynamically
function updateFilterLayout() {
    const filterWrapper = document.getElementById("filter-wrapper");
    const filters = document.querySelectorAll(".filter-badge");

    if (filters.length > 0) {
        filterWrapper.classList.add("has-filters");
    } else {
        filterWrapper.classList.remove("has-filters");
    }
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
    updateFilterLayout();
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
    updateFilterLayout();
}

// Handle adding filters from the input field and button
function addFilterFromInput() {
    const inputField = document.getElementById("filter-input");
    const query = inputField.value.trim();
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

    const formattedFilter = symbolicOperators.includes(operator) ? `${field}${operator}${value}` : `${field} ${operator} ${value}`;

    const urlParams = new URLSearchParams(window.location.search);
    let filters = urlParams.get("filters") ? urlParams.get("filters").split(",") : [];

    if (!filters.includes(formattedFilter)) {
        filters.push(formattedFilter);
        urlParams.set("filters", filters.join(","));
        window.history.replaceState({}, "", `?${urlParams.toString()}`);

        addFilterUI(formattedFilter);
        applyFilters();
    }

    inputField.value = "";
    showFilterError(null);
}


// Add filtering from table clicks (cell values) and input
export function setupTableFiltering() {
    // Add a filter from the input field
    document.getElementById("filter-input").addEventListener("keypress", function (event) {
        if (event.key === "Enter") {
            addFilterFromInput();
        }
    });

    document.getElementById("add-filter-btn").addEventListener("click", addFilterFromInput);

    // Add filtering from table clicks
    table.on("cellClick", (e, cell) => {
        if (cell.getElement().classList.contains("unclickable-cell")) return;
        if (e.target.tagName === "A") {
            e.stopPropagation();
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
        } else {
            const filterElements = document.querySelectorAll(`.filter-badge span`)
            const filterElement = Array.from(filterElements).find(el => el.innerText === newFilter);
            removeFilter(newFilter, filterElement.parentElement);
        }
    });

}

export {loadFiltersFromArrayToURL, loadFiltersFromURL}