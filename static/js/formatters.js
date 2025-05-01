import {ZOOM_IN_ICON, ZOOM_OUT_ICON} from "./constants.js";

let columnColors = {}; // Store color mappings

// Formatters for different column types
const formatterMap = {
    "datetime": (cell, params) => {
        if (params.formatType === "relative") {
            return formatRelativeTime(cell.getValue(), params.precision);
        }
        return formatTimestamp(cell.getValue())
    },
    "link": "link",
    "indicator": (cell, params) => {
        return formatIndicator(cell, params);
    }
};

// Formatter parameters (for links, etc.)
const formatterParamsMap = {
    "link": (data) => {
        return {
            urlField: data.urlField,
            urlPrefix: "",
            target: "_blank",
        };
    },
    "datetime": (data) => {
        return {
            formatType: data.formatType || "absolute",
            precision: data.precision || 3,
        };
    }
};

function formatRelativeTime(unixTimestamp, precision = 3) {
    const now = new Date();
    const date = new Date(unixTimestamp * 1000);
    let diffSec = Math.floor((now - date) / 1000);

    if (diffSec < 0) return "in the future";

    // Define time intervals in seconds
    const intervals = [
        {label: "d", seconds: 86400},    // Day
        {label: "h", seconds: 3600},     // Hour
        {label: "m", seconds: 60},       // Minute
    ];

    let result = [];

    for (let i = 0; i < intervals.length && result.length < precision; i++) {
        const {label, seconds} = intervals[i];
        const value = Math.floor(diffSec / seconds);
        if (value > 0) {
            result.push(`${value}${label}`);
            diffSec -= value * seconds;
        }
    }

    return result.length > 0 ? `${result[0]} ago` : "< minute ago";
}

function formatTimestamp(unixTimestamp) {
    const date = new Date(unixTimestamp * 1000);
    return date.toLocaleString(navigator.language, {
        timeZone: Intl.DateTimeFormat().resolvedOptions().timeZone
    });
}

// Custom formatter to apply colors
function formatterWrapper(formatter) {
    // Special handling for indicator formatter
    if (formatter === formatIndicator) {
        return formatter;
    }
    
    function colorFormatter(cell, formatterParams) {
        const element = cell.getElement();
        // Skip if this cell contains a collapse toggle
        if (element && element.querySelector('.tabulator-responsive-collapse-toggle')) {
            return cell.getValue();
        }

        const columnName = cell.getColumn().getField();
        const cellValue = cell.getValue();
        let color = null;

        if (columnColors[columnName] && columnColors[columnName][cellValue]) {
            color = columnColors[columnName][cellValue];
        }

        // Create a container for the cell content
        const container = document.createElement("div");
        container.className = "cell-container";

        let text = "";
        if (typeof formatter === "function") {
            text = formatter(cell, formatterParams);
        } else {
            text = cellValue;
        }

        // Only create a pill-style label if we have a color
        if (color) {
            // Create a pill-style label with transparent background & colored border
            const pillDiv = document.createElement("div");
            pillDiv.textContent = text;
            pillDiv.className = "pill-label";
            pillDiv.style.border = `2px solid ${color}`;
            pillDiv.style.backgroundColor = "transparent";
            
            // Add the pill to the container
            container.appendChild(pillDiv);
        } else {
            // Just add the text directly
            const textDiv = document.createElement("div");
            textDiv.textContent = text;
            textDiv.className = "original-formatter";
            container.appendChild(textDiv);
        }
        
        // Add zoom icon for filterable cells
        if (!cell.getElement().classList.contains("unclickable-cell")) {
            const zoomIcon = document.createElement("span");
            zoomIcon.className = "zoom-icon zoom-in";
            
            // Check if this cell value is currently filtered
            const urlParams = new URLSearchParams(window.location.search);
            const filters = urlParams.get("filters") ? urlParams.get("filters").split(",") : [];
            const filterForThisCell = filters.find(f => {
                const match = f.match(/^(.+?)(=)(.*)$/);
                if (match) {
                    const [, field, operator, value] = match;
                    const trimmedValue = value.trim().replace(/^["']|["']$/g, '');
                    return field.trim() === columnName && trimmedValue === cellValue;
                }
                return false;
            });
            
            if (filterForThisCell) {
                zoomIcon.className = "zoom-icon zoom-out";
                zoomIcon.innerHTML = ZOOM_OUT_ICON;
            } else {
                zoomIcon.innerHTML = ZOOM_IN_ICON;
            }
            
            container.appendChild(zoomIcon);
        }
        
        return container;
    }

    // Handle string formatters (like "link")
    if (typeof formatter === "string") {
        return function(cell, formatterParams) {
            const element = cell.getElement();
            // Skip if this cell contains a collapse toggle
            if (element && element.querySelector('.tabulator-responsive-collapse-toggle')) {
                return cell.getValue();
            }

            // Create a container for the cell content
            const container = document.createElement("div");
            container.className = "cell-container";
            
            // Create the original formatter content
            const originalContent = document.createElement("div");
            originalContent.className = "original-formatter";
            
            // Apply the original formatter
            if (formatter === "link") {
                const linkParams = formatterParams || {};
                const urlField = linkParams.urlField || cell.getColumn().getField();
                const urlPrefix = linkParams.urlPrefix || "";
                const target = linkParams.target || "_blank";
                
                const link = document.createElement("a");
                link.href = urlPrefix + cell.getData()[urlField];
                link.target = target;
                link.textContent = cell.getValue();
                originalContent.appendChild(link);
            } else {
                originalContent.textContent = cell.getValue();
            }
            
            container.appendChild(originalContent);
            
            // Add zoom icon for filterable cells
            if (!cell.getElement().classList.contains("unclickable-cell")) {
                const zoomIcon = document.createElement("span");
                zoomIcon.className = "zoom-icon zoom-in";
                zoomIcon.style.cursor = "pointer";
                zoomIcon.style.marginLeft = "5px";
                zoomIcon.style.display = "inline-flex";
                zoomIcon.style.alignItems = "center";
                zoomIcon.style.justifyContent = "center";
                
                // Check if this cell value is currently filtered
                const urlParams = new URLSearchParams(window.location.search);
                const filters = urlParams.get("filters") ? urlParams.get("filters").split(",") : [];
                const filterForThisCell = filters.find(f => {
                    const match = f.match(/^(.+?)(=)(.*)$/);
                    if (match) {
                        const [, field, operator, value] = match;
                        const trimmedValue = value.trim().replace(/^["']|["']$/g, '');
                        return field.trim() === cell.getColumn().getField() && trimmedValue === cell.getValue();
                    }
                    return false;
                });
                
                if (filterForThisCell) {
                    zoomIcon.className = "zoom-icon zoom-out";
                    zoomIcon.innerHTML = ZOOM_OUT_ICON;
                } else {
                    zoomIcon.innerHTML = ZOOM_IN_ICON;
                }
                
                container.appendChild(zoomIcon);
            }
            
            return container;
        };
    }
    
    return colorFormatter;
}

function formatIndicator(cell, params) {
    const indicatorDiv = document.createElement("div");
    indicatorDiv.style.display = "inline-block";
    indicatorDiv.style.width = "6px";
    indicatorDiv.style.height = "35px";
    indicatorDiv.style.backgroundColor = cell.getValue();
    return indicatorDiv;
}

function getColorMap() {
    return columnColors;
}

function setColorMap(colors) {
    columnColors = colors;
}

export {formatterWrapper, setColorMap, formatterMap, formatterParamsMap,};
