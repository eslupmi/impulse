import {table} from "./table.js";
import {ZOOM_IN_ICON, ZOOM_OUT_ICON} from "./constants.js";

const symbolicOperators = ["=", ">", "<", ">=", "<=", "!=", "=~", "!~"];
let defaultFilters = [];
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
    defaultFilters = [...filters];
    
    const urlParams = new URLSearchParams(window.location.search);
    const urlFilters = urlParams.get("filters") ? urlParams.get("filters").split(",") : [];

    if (urlFilters.length > 0) {
        urlFilters.forEach(filter => addFilterUI(filter));
    } else if (filters.length > 0) {
        filters.forEach(filter => addFilterUI(filter));
    }
    
    applyFilters();
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

// Check if current filters match default filters
function isDefaultFilters(currentFilters) {
    if (currentFilters.length !== defaultFilters.length) return false;
    
    return currentFilters.every(filter => defaultFilters.includes(filter));
}

// Get current filters from URL only
function getURLFilters() {
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get("filters") ? urlParams.get("filters").split(",").filter(f => f.trim()) : [];
}

// Get all active filters (default + URL filters, with URL taking precedence)
function getCurrentFilters() {
    const urlFilters = getURLFilters();
    
    if (urlFilters.length > 0) {
        return urlFilters;
    }
    
    return [...defaultFilters];
}

// Update filters in URL, avoiding default and empty filters
function updateFiltersInURL(filters) {
    const urlParams = new URLSearchParams(window.location.search);
    
    const cleanFilters = filters.filter(f => f && f.trim());
    
    if (cleanFilters.length === 0) {
        urlParams.delete("filters");
    } else if (isDefaultFilters(cleanFilters)) {
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

            value = value.replace(/^["']|["']$/g, '');
            
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

// Add a new filter to the UI
function addFilterUI(filter) {
    const filterContainer = document.getElementById("filter-container");

    const filterElement = document.createElement("div");
    filterElement.classList.add("filter-badge");

    const filterText = document.createElement("span");
    filterText.innerText = filter;
    filterElement.appendChild(filterText);

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
    const currentFilters = getCurrentFilters();
    const urlFilters = getURLFilters();
    
    const remainingFilters = currentFilters.filter(f => f !== filter);
    
    let newUrlFilters;
    
    if (urlFilters.length === 0) {
        newUrlFilters = remainingFilters;
    } else {
        newUrlFilters = remainingFilters;
    }
    
    updateFiltersInURL(newUrlFilters);

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

    const currentFilters = getCurrentFilters();

    if (!currentFilters.includes(formattedFilter)) {
        const newFilters = [...currentFilters, formattedFilter];
        updateFiltersInURL(newFilters);

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

// Separate the event listener setup into its own function
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
        
        const isZoomIcon = e.target.classList.contains("zoom-icon") || 
                           e.target.closest(".zoom-icon") !== null;
        
        if (!isZoomIcon) return;

        const field = cell.getColumn().getField();
        const value = cell.getValue();
        const newFilter = `${field}="${value}"`;

        const currentFilters = getCurrentFilters();

        if (!currentFilters.includes(newFilter)) {
            const newFilters = [...currentFilters, newFilter];
            updateFiltersInURL(newFilters);

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
    const filters = getCurrentFilters();
    
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
