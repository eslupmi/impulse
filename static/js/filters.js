import {table} from "./table.js";
import {isValidRegex, parseMatcher} from "./matcher.js";

function matchLabelValue(labelValue, searchValue, operator) {
    const labelStr = String(labelValue).toLowerCase();
    switch (operator) {
        case "=":
            return labelStr === searchValue;
        case "!=":
            return labelStr !== searchValue;
        case "=~":
            try {
                return new RegExp(searchValue, "i").test(labelStr);
            } catch (e) {
                return false;
            }
        case "!~":
            try {
                return !new RegExp(searchValue, "i").test(labelStr);
            } catch (e) {
                return false;
            }
        default:
            return false;
    }
}

function addTableFilterFromParsed(parsedFilter) {
    const {field, operator, value} = parsedFilter;
    const isRegex = operator === "=~" || operator === "!~";

    if (isRegex && !isValidRegex(value)) {
        showFilterError(`Invalid regex: ${value}`);
        return false;
    }

    const columnExists = table.getColumns().some(col => col.getField() === field);

    if (!columnExists) {
        table.addFilter(customResponsiveDataFilter, {field, operator, value});
        return true;
    }
    if (isRegex) {
        const anchoredRegex = `^${value}$`;

        if (operator === "=~") {
            table.addFilter(field, "regex", anchoredRegex);
        } else {
            table.addFilter(customNegativeRegexFilter, {field: field, value: anchoredRegex});
        }
        return true;
    }
    table.addFilter(field, operator, value);
    return true;
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

    const {field, value, operator} = parameters;
    const searchValue = value.toLowerCase();
    const labelValues = [
        responsiveData.group_labels?.[field],
        responsiveData.common_labels?.[field],
        ...(responsiveData.alerts || []).map(alert => alert.labels?.[field]),
    ].filter(value => value !== undefined && value !== null);

    if (!labelValues.length) labelValues.push("");

    const matches = labelValue => matchLabelValue(labelValue, searchValue, operator);
    return operator === "!=" || operator === "!~"
        ? labelValues.every(matches)
        : labelValues.some(matches);
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

function parseFilterString(filterString) {
    const parsed = parseMatcher(filterString.trim());
    return parsed && {field: parsed.label, operator: parsed.operator, value: parsed.value};
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
            addTableFilterFromParsed(parsedFilter);
        }
    });

    updateZoomIcons();
}

function validateAndFormatFilter(query) {
    const q = query.trim();
    if (!q || !validateMatcherClause(q).ok) return null;
    return q;
}

function createEditableFilterBadge({value, onChange, onRemove, onBadgeClick, validateAndFormat = validateAndFormatFilter}) {
    const badge = document.createElement("div");
    badge.className = "filter-badge";

    const text = document.createElement("span");
    text.className = "filter-badge-text";
    text.textContent = value;
    text.title = "Click to edit";

    const removeButton = document.createElement("span");
    removeButton.className = "cross";

    const startEdit = () => {
        if (badge.classList.contains("is-editing")) return;
        const current = text.textContent;
        badge.classList.add("is-editing");
        const input = document.createElement("input");
        input.type = "text";
        input.className = "filter-badge-edit-input";
        input.value = current;
        text.replaceWith(input);
        input.focus();
        input.setSelectionRange(current.length, current.length);

        const endEdit = () => {
            badge.classList.remove("is-editing");
            input.replaceWith(text);
        };

        input.addEventListener("keydown", (e) => {
            if (e.key === "Enter") {
                e.preventDefault();
                const next = validateAndFormat(input.value);
                if (!next) {
                    input.classList.add("filter-badge-edit-error");
                    return;
                }
                if (next === current) {
                    endEdit();
                    return;
                }
                if (onChange(next, current) === false) {
                    input.classList.add("filter-badge-edit-error");
                    return;
                }
                text.textContent = next;
                endEdit();
            } else if (e.key === "Escape") {
                e.preventDefault();
                endEdit();
            }
        });
        input.addEventListener("blur", () => {
            if (!badge.classList.contains("is-editing")) return;
            const next = validateAndFormat(input.value);
            if (!next) {
                endEdit();
                return;
            }
            if (next !== current && onChange(next, current) !== false) {
                text.textContent = next;
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
        onRemove(text.textContent);
    });

    badge.appendChild(text);
    badge.appendChild(removeButton);
    return badge;
}

// Add a new filter to the UI
function scrollFiltersToEnd() {
    document.getElementById("filter-container").scrollLeft = 0;
}

function addFilterUI(filter) {
    const filterList = document.getElementById("filter-list");

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

    filterList.appendChild(filterElement);
    scrollFiltersToEnd();
}

// Remove a filter from the UI and URL
function removeFilter(filter, filterElement) {
    let filters = getCurrentFilters();
    filters = filters.filter(f => f !== filter);
    updateFiltersInURL(filters);

    filterElement.remove();
    applyFilters();
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

    const {operator, value} = parsedFilter;

    if ((operator === "=~" || operator === "!~") && !isValidRegex(value)) {
        showFilterError(`Invalid regex: ${value}`);
        return;
    }

    let filters = getCurrentFilters();

    if (!filters.includes(query)) {
        filters.push(query);
        updateFiltersInURL(filters);

        addFilterUI(query);
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
        const filterList = document.getElementById("filter-list");
        const hasFilters = filterList.children.length > 0;
        scrollableFilters.classList.toggle("has-filters", hasFilters);

        // The RTL scroll container starts at the right edge and scrolls toward negative offsets.
        const {scrollLeft, scrollWidth, clientWidth} = filterContainer;
        const leftWrapper = document.querySelector(".arrow-wrapper.left");
        const rightWrapper = document.querySelector(".arrow-wrapper.right");
        leftWrapper.classList.toggle("visible", hasFilters && scrollLeft > clientWidth - scrollWidth + 2);
        rightWrapper.classList.toggle("visible", hasFilters && scrollLeft < -2);
    }

    filterContainer.addEventListener("scroll", updateArrowVisibility);

    const observer = new MutationObserver(updateArrowVisibility);
    observer.observe(filterContainer, { childList: true, subtree: true });

    new ResizeObserver(updateArrowVisibility).observe(filterContainer);

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
    const filterTexts = document.querySelectorAll("#filter-list .filter-badge-text");
    const text = Array.from(filterTexts).find(text => text.textContent === existingFilter);
    if (text) {
        text.textContent = newFilter;
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
        if (cell.getElement().classList.contains("unclickable-cell")) return;

        const field = cell.getColumn().getField();
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
    const {operator, value} = parsed;
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
