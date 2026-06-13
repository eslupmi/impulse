import {table} from "./table.js";

const symbolicOperators = new Set(["=", ">", "<", ">=", "<=", "!=", "=~", "!~"]);
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

// Custom filter for responsive data labels
function customResponsiveDataFilter(rowData, parameters) {
    const responsiveData = rowData._responsive_data;
    if (!responsiveData) return false;

    const { field, value, operator } = parameters;
    const searchValue = value.toLowerCase();

    const labelMatches = (labelValue) => {
        const labelStr = String(labelValue).toLowerCase();
        switch (operator) {
            case "=":
                return labelStr === searchValue;
            case "!=":
                return labelStr !== searchValue;
            case "=~":
                try {
                    const regex = new RegExp(searchValue, "i");
                    return regex.test(labelStr);
                } catch (e) {
                    return false;
                }
            case "!~":
                try {
                    const regex = new RegExp(searchValue, "i");
                    return !regex.test(labelStr);
                } catch (e) {
                    return false;
                }
            default:
                return false;
        }
    };

    if (responsiveData.group_labels && responsiveData.group_labels[field]) {
        if (labelMatches(responsiveData.group_labels[field])) {
            return true;
        }
    }

    if (responsiveData.common_labels && responsiveData.common_labels[field]) {
        if (labelMatches(responsiveData.common_labels[field])) {
            return true;
        }
    }

    if (responsiveData.alerts) {
        for (const alert of responsiveData.alerts) {
            if (alert.labels && alert.labels[field]) {
                if (labelMatches(alert.labels[field])) {
                    return true;
                }
            }
        }
    }

    return false;
}

// Initialize filters from URL
function loadFiltersFromArrayToURL(filters) {
    const urlParams = new URLSearchParams(window.location.search);
    const activeFilters = urlParams.get("filters") ? urlParams.get("filters").split(",") : [];

    if (!activeFilters.length && filters.length > 0) {
        urlParams.set("filters", filters.join(","));
        const queryString = urlParams.toString();
        const newUrl = queryString ? `${window.location.pathname}?${queryString}` : window.location.pathname;
        window.history.replaceState({}, "", newUrl);
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
    const match = filterString.match(/^(.+?)(=~|!~|=|!=|like|keywords|starts|ends|<|<=|>|>=|in|regex)(.*)$/);

    if (!match) {
        return;
    }

    let [, field, operator, value] = match;

    field = field.trim();
    operator = operator.trim();
    value = value.trim();

    return {field, operator, value};
}

// Get current filters from URL
function getCurrentFilters() {
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get("filters") ? urlParams.get("filters").split(",").filter(f => f.trim()) : [];
}

// Update filters in URL
function updateFiltersInURL(filters) {
    const urlParams = new URLSearchParams(window.location.search);

    const cleanFilters = filters.filter(f => f && f.trim());

    if (cleanFilters.length === 0) {
        urlParams.delete("filters");
    } else {
        urlParams.set("filters", cleanFilters.join(","));
    }

    const queryString = urlParams.toString();
    const newUrl = queryString ? `${window.location.pathname}?${queryString}` : window.location.pathname;
    window.history.replaceState({}, "", newUrl);
}

// Apply filters to Tabulator table
function applyFilters() {
    const filters = getCurrentFilters();

    table.clearFilter();
    showFilterError(null);

    filters.forEach(filter => {
        const parsedFilter = parseFilterString(filter);
        if (parsedFilter) {
            let {field, operator, value} = parsedFilter;

            value = value.replace(/^(?:["'])|(?:["'])$/g, '');

            const columnExists = table.getColumns().some(col => col.getField() === field);

            if (!columnExists) {
                if (operator === "=~" || operator === "!~") {
                    if (!isValidRegex(value)) {
                        showFilterError(`Invalid regex: ${value}`);
                        return;
                    }
                }
                table.addFilter(customResponsiveDataFilter, {field, operator, value});
            } else if (operator === "=~" || operator === "!~") {
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

    updateZoomIcons();
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

function formatFilterClause(parsed) {
    let {field, operator, value} = parsed;
    value = value.replace(/^(?:["'])|(?:["'])$/g, "");
    return symbolicOperators.has(operator) ? `${field}${operator}"${value}"` : `${field} ${operator} ${value}`;
}

function validateAndFormatFilter(query) {
    const q = query.trim();
    if (!q) return null;
    const parsed = parseFilterString(q);
    if (!parsed || !validateMatcherClause(q).ok) return null;
    return formatFilterClause(parsed);
}

function createEditableFilterBadge({value, onChange, onRemove, onBadgeClick}) {
    let current = value;
    const badge = document.createElement("div");
    badge.className = "filter-badge";

    const text = document.createElement("span");
    text.className = "filter-badge-text";
    text.textContent = current;
    text.title = "Click to edit";

    const removeButton = document.createElement("span");
    removeButton.className = "cross";

    const endEdit = () => {
        badge.classList.remove("is-editing");
        const input = badge.querySelector(".filter-badge-edit-input");
        if (input) {
            input.replaceWith(text);
        }
        text.textContent = current;
    };

    const startEdit = () => {
        if (badge.classList.contains("is-editing")) return;
        badge.classList.add("is-editing");
        const input = document.createElement("input");
        input.type = "text";
        input.className = "filter-badge-edit-input";
        input.value = current;
        text.replaceWith(input);
        input.focus();
        input.select();

        input.addEventListener("keydown", (e) => {
            if (e.key === "Enter") {
                e.preventDefault();
                const formatted = validateAndFormatFilter(input.value);
                if (!formatted) {
                    input.classList.add("filter-badge-edit-error");
                    return;
                }
                if (formatted === current) {
                    endEdit();
                    return;
                }
                if (onChange(formatted, current) === false) {
                    input.classList.add("filter-badge-edit-error");
                    return;
                }
                current = formatted;
                endEdit();
            } else if (e.key === "Escape") {
                e.preventDefault();
                endEdit();
            }
        });
        input.addEventListener("blur", () => {
            if (!badge.classList.contains("is-editing")) return;
            const formatted = validateAndFormatFilter(input.value);
            if (!formatted) {
                endEdit();
                return;
            }
            if (formatted !== current && onChange(formatted, current) !== false) {
                current = formatted;
            }
            endEdit();
        });
        input.addEventListener("input", () => input.classList.remove("filter-badge-edit-error"));
    };

    text.addEventListener("click", (e) => {
        e.stopPropagation();
        startEdit();
    });
    if (onBadgeClick) {
        badge.addEventListener("click", onBadgeClick);
    }
    removeButton.addEventListener("click", (e) => {
        e.stopPropagation();
        onRemove(current);
    });

    badge.appendChild(text);
    badge.appendChild(removeButton);
    return badge;
}

// Add a new filter to the UI
function addFilterUI(filter) {
    const filterContainer = document.getElementById("filter-container");

    const filterElement = createEditableFilterBadge({
        value: filter,
        onChange: (newFilter, oldFilter) => {
            let filters = getCurrentFilters();
            const idx = filters.indexOf(oldFilter);
            if (idx === -1) return false;
            if (filters.includes(newFilter) && newFilter !== oldFilter) return false;
            filters[idx] = newFilter;
            updateFiltersInURL(filters);
            applyFilters();
            showFilterError(null);
            return true;
        },
        onRemove: (f) => removeFilter(f, filterElement),
    });

    filterContainer.appendChild(filterElement);
    updateFilterLayout();
}

// Remove a filter from the UI and URL
function removeFilter(filter, filterElement) {
    let filters = getCurrentFilters();
    filters = filters.filter(f => f !== filter);
    updateFiltersInURL(filters);

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
        alert("Invalid filter format. Example: status=\"firing\".");
        return;
    }

    let {operator, value} = parsedFilter;

    if ((operator === "=~" || operator === "!~") && !isValidRegex(value)) {
        showFilterError(`Invalid regex: ${value}`);
        return;
    }

    const formattedFilter = formatFilterClause(parsedFilter);

    let filters = getCurrentFilters();

    if (!filters.includes(formattedFilter)) {
        filters.push(formattedFilter);
        updateFiltersInURL(filters);

        addFilterUI(formattedFilter);
        applyFilters();
    }

    inputField.value = "";
    showFilterError(null);
}

// Add scroll functionality
function setupFilterContainerScroll() {
    const filterContainer = document.getElementById("filter-container");
    const scrollableFilters = document.getElementById("scrollable-filters");
    const leftArrow = document.querySelector(".scroll-arrow.left");
    const rightArrow = document.querySelector(".scroll-arrow.right");

    if (!filterContainer || !leftArrow || !rightArrow || !scrollableFilters) {
        console.warn("Required elements for filter scrolling not found");
        return;
    }

    const scrollAmount = 200;

    leftArrow.onclick = () => {
        filterContainer.scrollBy({
            left: -scrollAmount,
            behavior: "smooth"
        });
    };

    rightArrow.onclick = () => {
        filterContainer.scrollBy({
            left: scrollAmount,
            behavior: "smooth"
        });
    };

    filterContainer.addEventListener("wheel", (e) => {
        e.preventDefault();
        filterContainer.scrollLeft += e.deltaY;
    });

    function updateArrowVisibility() {
        const hasFilters = filterContainer.children.length > 0;
        scrollableFilters.classList.toggle("has-filters", hasFilters);

        const leftWrapper = document.querySelector(".arrow-wrapper.left");
        const rightWrapper = document.querySelector(".arrow-wrapper.right");

        if (hasFilters) {
            leftWrapper.classList.toggle("visible", filterContainer.scrollLeft > 0);

            const isAtEnd = Math.abs(filterContainer.scrollWidth - filterContainer.clientWidth - filterContainer.scrollLeft) < 2;
            rightWrapper.classList.toggle("visible", !isAtEnd);
        } else {
            leftWrapper.classList.remove("visible");
            rightWrapper.classList.remove("visible");
        }
    }

    filterContainer.addEventListener("scroll", updateArrowVisibility);

    const observer = new MutationObserver(updateArrowVisibility);
    observer.observe(filterContainer, { childList: true, subtree: true });

    updateArrowVisibility();
}

// Initialize all filter functionality
function initializeFilters() {
    setTimeout(() => {
        setupFilterContainerScroll();
        setupFilterEventListeners();
    }, 0);
}

// Update the setupTableFiltering function to include scroll setup
export function setupTableFiltering() {
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initializeFilters);
    } else {
        initializeFilters();
    }
}

// Update filter badge UI when filter value changes
function updateFilterBadgeUI(existingFilter, newFilter) {
    const filterElements = document.querySelectorAll(".filter-badge");
    const filterElement = Array.from(filterElements).find(badge => {
        return badge.querySelector(".filter-badge-text")?.textContent === existingFilter;
    });
    
    if (filterElement) {
        const textSpan = filterElement.querySelector(".filter-badge-text");
        if (textSpan) {
            textSpan.innerText = newFilter;
        }
        // Update remove button handler with new filter
        const removeButton = filterElement.querySelector(".cross");
        if (removeButton) {
            removeButton.replaceWith(removeButton.cloneNode(true));
            filterElement.querySelector(".cross").addEventListener("click", () => removeFilter(newFilter, filterElement));
        }
    }
}

// Handle zoom icon click to add or update filter
function handleZoomIconClick(field, value, isZoomOut) {
    const operator = isZoomOut ? "!=" : "=";
    const oppositeOperator = isZoomOut ? "=" : "!=";
    const newFilter = `${field}${operator}"${value}"`;
    const existingOppositeFilter = `${field}${oppositeOperator}"${value}"`;

    let filters = getCurrentFilters();

    // If filter already exists, do nothing
    if (filters.includes(newFilter)) {
        return;
    }

    // If opposite filter exists, replace operator in it
    if (filters.includes(existingOppositeFilter)) {
        filters = filters.filter(f => f !== existingOppositeFilter);
        filters.push(newFilter);
        updateFiltersInURL(filters);
        updateFilterBadgeUI(existingOppositeFilter, newFilter);
    } else {
        // Add new filter
        filters.push(newFilter);
        updateFiltersInURL(filters);
        addFilterUI(newFilter);
    }
    
    applyFilters();
}

function setupFilterEventListeners() {
    document.getElementById("filter-input").addEventListener("keypress", function (event) {
        if (event.key === "Enter") {
            addFilterFromInput();
        }
    });

    document.getElementById("add-filter-btn").addEventListener("click", addFilterFromInput);

    table.on("cellClick", (e, cell) => {
        if (cell.getElement().classList.contains("unclickable-cell")) return;
        if (e.target.tagName === "A") {
            e.stopPropagation();
            return;
        }

        const zoomIcon = e.target.closest(".zoom-icon");
        if (!zoomIcon) return;

        const field = cell.getColumn().getField();
        const value = cell.getValue();
        const isZoomOut = zoomIcon.classList.contains("zoom-out");
        
        handleZoomIconClick(field, value, isZoomOut);
    });
}

// Function to update zoom icons based on current filters
function updateZoomIcons() {
    // Get all cells in the table
    const cells = table.getRows().flatMap(row => row.getCells());

    cells.forEach(cell => {
        const column = cell.getColumn();
        // Skip the responsive collapse column
        if (column.getDefinition().formatter === 'responsiveCollapse') return;

        if (cell.getElement().classList.contains("unclickable-cell")) return;

        const field = column.getField();
        if (!field) return;

        const value = cell.getValue();

        const zoomInIcon = cell.getElement().querySelector(".zoom-icon.zoom-in");
        const zoomOutIcon = cell.getElement().querySelector(".zoom-icon.zoom-out");

        if (zoomInIcon && zoomOutIcon) {
            if (!value || value === '' || value === null || value === undefined) {
                zoomInIcon.classList.add("hidden");
                zoomOutIcon.classList.add("hidden");
                return;
            }

            // Always show both icons
            zoomInIcon.classList.remove("hidden");
            zoomOutIcon.classList.remove("hidden");
        }
    });
}

function validateMatcherClause(clause) {
    const q = clause.trim();
    if (!q) return {ok: true};
    const parsed = parseFilterString(q);
    if (!parsed) return {ok: false};
    let {operator, value} = parsed;
    value = value.replace(/^(?:["'])|(?:["'])$/g, "");
    if ((operator === "=~" || operator === "!~") && !isValidRegex(value)) {
        return {ok: false};
    }
    return {ok: true};
}

function validateMatchersCommaSeparated(s) {
    if (!String(s).trim()) return {ok: true};
    const parts = String(s).split(",").map((p) => p.trim()).filter(Boolean);
    for (const p of parts) {
        if (!validateMatcherClause(p).ok) return {ok: false};
    }
    return {ok: true};
}

export {
    loadFiltersFromArrayToURL,
    loadFiltersFromURL,
    updateZoomIcons,
    validateMatchersCommaSeparated,
    parseFilterString,
    validateMatcherClause,
    createEditableFilterBadge,
    validateAndFormatFilter,
}
