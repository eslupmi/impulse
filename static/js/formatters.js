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

    return result.length > 0 ? `${result.join(" ")} ago` : "< minute ago";
}

function formatTimestamp(unixTimestamp) {
    const date = new Date(unixTimestamp * 1000);
    return date.toLocaleString(navigator.language, {
        timeZone: Intl.DateTimeFormat().resolvedOptions().timeZone
    });
}

// Custom formatter to apply colors
function formatterWrapper(formatterFunction) {
    function colorFormatter(cell, formatterParams) {
        const columnName = cell.getColumn().getField();
        const cellValue = cell.getValue();

        if (columnColors[columnName] && columnColors[columnName][cellValue]) {
            cell.getElement().style.backgroundColor = columnColors[columnName][cellValue];
            cell.getElement().style.color = "#fff";
        }

        if (typeof formatterFunction === "function") {
            return formatterFunction(cell, formatterParams);
        } else {
            return cellValue;
        }
    }

    return colorFormatter;
}

function getColorMap() {
    return columnColors;
}

function setColorMap(colors) {
    columnColors = colors;
}

export {formatterWrapper, setColorMap, formatterMap, formatterParamsMap,};
