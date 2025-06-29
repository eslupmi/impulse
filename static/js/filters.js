import {table} from "./table.js";
import {ZOOM_IN_ICON, ZOOM_OUT_ICON} from "./constants.js";

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

// Custom filter for responsive data labels
function customResponsiveDataFilter(rowData, parameters) {
    const responsiveData = rowData._responsive_data;
    if (!responsiveData) return false;

    const { field, value, operator } = parameters;
    const searchValue = value.toLowerCase();

    // Helper function to check if a label matches
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

    // Check group labels
    if (responsiveData.group_labels && responsiveData.group_labels[field]) {
        if (labelMatches(responsiveData.group_labels[field])) {
            return true;
        }
    }

    // Check common labels
    if (responsiveData.common_labels && responsiveData.common_labels[field]) {
        if (labelMatches(responsiveData.common_labels[field])) {
            return true;
        }
    }

    // Check alert labels
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
            
            // Check if the field exists in the table columns
            const columnExists = table.getColumns().some(col => col.getField() === field);
            
            if (!columnExists) {
                // If field doesn't exist in columns, try to filter using responsive data
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
    
    // Update zoom icons after applying filters
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
    removeButton.classList.add("cross");
    removeButton.innerText = "";
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

// Add scroll functionality
function setupFilterContainerScroll() {
    const filterContainer = document.getElementById("filter-container");
    const scrollableFilters = document.getElementById("scrollable-filters");
    const leftArrow = document.querySelector(".scroll-arrow.left");
    const rightArrow = document.querySelector(".scroll-arrow.right");
    
    // Check if all required elements exist
    if (!filterContainer || !leftArrow || !rightArrow || !scrollableFilters) {
        console.warn("Required elements for filter scrolling not found");
        return;
    }

    const scrollAmount = 200; // Amount to scroll on each click

    // Setup arrow click handlers
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

    // Handle mouse wheel scrolling
    filterContainer.addEventListener("wheel", (e) => {
        e.preventDefault();
        filterContainer.scrollLeft += e.deltaY;
    });

    // Function to update arrow visibility
    function updateArrowVisibility() {
        const hasFilters = filterContainer.children.length > 0;
        scrollableFilters.classList.toggle("has-filters", hasFilters);
        
        const leftWrapper = document.querySelector(".arrow-wrapper.left");
        const rightWrapper = document.querySelector(".arrow-wrapper.right");
        
        if (hasFilters) {
            // Show left arrow if we're not at the start
            leftWrapper.classList.toggle("visible", filterContainer.scrollLeft > 0);
            
            // Show right arrow if we're not at the end
            // Use a small threshold to account for rounding errors
            const isAtEnd = Math.abs(filterContainer.scrollWidth - filterContainer.clientWidth - filterContainer.scrollLeft) < 2;
            rightWrapper.classList.toggle("visible", !isAtEnd);
        } else {
            leftWrapper.classList.remove("visible");
            rightWrapper.classList.remove("visible");
        }
    }

    // Show/hide arrows based on scroll position and filter presence
    filterContainer.addEventListener("scroll", updateArrowVisibility);

    // Update arrow visibility when filters are added or removed
    const observer = new MutationObserver(updateArrowVisibility);
    observer.observe(filterContainer, { childList: true, subtree: true });

    // Initial arrow visibility
    updateArrowVisibility();
}

// Initialize all filter functionality
function initializeFilters() {
    // Wait for a short moment to ensure DOM is fully rendered
    setTimeout(() => {
        setupFilterContainerScroll();
        setupFilterEventListeners();
    }, 0);
}

// Update the setupTableFiltering function to include scroll setup
export function setupTableFiltering() {
    // Wait for DOM to be fully loaded
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initializeFilters);
    } else {
        initializeFilters();
    }
}

// Separate the event listener setup into its own function
function setupFilterEventListeners() {
    // Add a filter from the input field
    document.getElementById("filter-input").addEventListener("keypress", function (event) {
        if (event.key === "Enter") {
            addFilterFromInput();
        }
    });

    document.getElementById("add-filter-btn").addEventListener("click", addFilterFromInput);

    // Add filtering from table clicks - only when clicking the zoom icon
    table.on("cellClick", (e, cell) => {
        if (cell.getElement().classList.contains("unclickable-cell")) return;
        if (e.target.tagName === "A") {
            e.stopPropagation();
            return;
        }
        
        // Check if the click was on a zoom icon or its SVG/path elements
        const isZoomIcon = e.target.classList.contains("zoom-icon") || 
                           e.target.closest(".zoom-icon") !== null;
        
        if (!isZoomIcon) return;

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

// Function to update zoom icons based on current filters
function updateZoomIcons() {
    const urlParams = new URLSearchParams(window.location.search);
    const filters = urlParams.get("filters") ? urlParams.get("filters").split(",") : [];
    
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
        
        const zoomIcon = cell.getElement().querySelector(".zoom-icon");
        if (zoomIcon) {
            if (!value || value === '' || value === null || value === undefined) {
                zoomIcon.classList.add("hidden");
                return;
            }
            
            zoomIcon.classList.remove("hidden");
            
            const filterForThisCell = filters.find(f => {
                const match = f.match(/^(.+?)(=)(.*)$/);
                if (match) {
                    const [, fieldName, operator, filterValue] = match;
                    const trimmedValue = filterValue.trim().replace(/^["']|["']$/g, '');
                    return fieldName.trim() === field && trimmedValue === value;
                }
                return false;
            });
            
            if (filterForThisCell) {
                zoomIcon.className = "zoom-icon zoom-out";
                zoomIcon.innerHTML = ZOOM_OUT_ICON;
            } else {
                zoomIcon.className = "zoom-icon zoom-in";
                zoomIcon.innerHTML = ZOOM_IN_ICON;
            }
        }
    });
}

export {loadFiltersFromArrayToURL, loadFiltersFromURL, updateZoomIcons}
