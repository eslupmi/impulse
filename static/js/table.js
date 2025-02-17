import {formatterWrapper, formatterMap, formatterParamsMap, setColorMap,} from "./formatters.js";
import {loadFiltersFromArrayToURL} from "./filters.js";

let relativeFields = [];

const table = new Tabulator("#data-table", {
    layout: "fitData",
    index: "uuid",
});

// Custom sorters
const sorterMap = {
    "datetime": (a, b) => a - b,
    "link": "string",
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
            return {
                title: column.title,
                field: column.field,
                visible: column.visible !== undefined ? column.visible : true,
                sorter: columnSorter,
                formatter: formatterWrapper(formatterMap[columnType] || undefined),
                formatterParams: columnType in formatterParamsMap ? formatterParamsMap[columnType](column) : undefined,
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
