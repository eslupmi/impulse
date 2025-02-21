import {formatterWrapper, formatterMap, formatterParamsMap, setColorMap,} from "./formatters.js";
import {loadFiltersFromArrayToURL} from "./filters.js";
import {initializeSorting} from "./sorters.js";

let relativeFields = [];

const table = new Tabulator("#data-table", {
    layout: "fitData",
    index: "uuid",
});

// Custom sorters
const sorterMap = {
    "datetime": (a, b) => a - b,
    "link": "string",
    "indicator": undefined,
};

// Fetch table configuration and sorting, then initialize the table
async function initializeTable() {
    try {
        const [configResponse, sortingResponse, colorsResponse, filtersResponse] = await Promise.all([
            fetch('/table_config').then(res => res.json()),
            fetch('/table_sorting').then(res => res.json()),
            fetch('/table_colors').then(res => res.json()),
            fetch('/table_filters').then(res => res.json()),
        ]);

        setColorMap(colorsResponse);
        loadFiltersFromArrayToURL(filtersResponse);

        const columns = configResponse.map(column => {
            const columnType = column.type || "string";
            const columnSorter = columnType in sorterMap ? sorterMap[columnType] : "string"
            if (columnType === "datetime" && column.formatType === "relative") {
                relativeFields.push(column.field);
            }
            let cssClass = columnSorter === "string" ? "clickable-cell" : "unclickable-cell";
            cssClass += ` ${columnType || "regular"}-field`;
            const columLayout = {
                title: column.title,
                field: column.field,
                visible: column.visible !== undefined ? column.visible : true,
                sorter: columnSorter,
                headerSort: column.headerSort !== undefined ? column.headerSort : true,
                formatter: formatterWrapper(formatterMap[columnType] || undefined),
                formatterParams: columnType in formatterParamsMap ? formatterParamsMap[columnType](column) : undefined,
                cssClass: cssClass,
            }
            if (columnType === "indicator") {
                columLayout.minWidth = 5;
                columLayout.resizable = false;
            }
            return columLayout
        });

        initializeSorting(columns, sortingResponse);
    } catch (error) {
        console.error("Error initializing table:", error);
    }
}

// Auto-update relative time fields every 10 seconds
function updateRelativeTimeFields() {
    table.getRows().forEach(row => {
        row.getCells().forEach(cell => {
            if (relativeFields.includes(cell.getColumn().getField())) {
                cell.setValue(cell.getValue(), true);
            }
        });
    });
}

export {initializeTable, updateRelativeTimeFields, table};
