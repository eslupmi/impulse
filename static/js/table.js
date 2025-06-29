import {
    formatterMap,
    formatterParamsMap,
    formatterWrapper,
    responsiveLayoutCollapseFormatter,
    setColorMap,
} from "./formatters.js";
import {loadFiltersFromArrayToURL} from "./filters.js";
import {initializeSorting} from "./sorters.js";

const relativeFields = [];

const tableOptions = {
    layout: "fitColumns",
    pagination: "local",
    paginationSize: 25,
    index: "uuid",
    responsiveLayout: "collapse",
    responsiveLayoutCollapseStartOpen: false,
    responsiveLayoutCollapseFormatter: responsiveLayoutCollapseFormatter,
    responsiveLayoutCollapseUseFormatters: false,
    sortOrderReverse:true,
    placeholder:"No Data Available",
    renderVertical: 'basic',
};

const table = new Tabulator("#data-table", tableOptions);

// Custom sorters
const sorterMap = {
    "datetime": (a, b) => a - b,
    "link": "string",
    "indicator": undefined,
};

// Fetch table configuration and sorting, then initialize the table
async function initializeTable() {
    try {
        const uiConfigResponse = await fetch('/ui_config').then(res => res.json());
        
        const configResponse = uiConfigResponse.table_config;
        const sortingResponse = uiConfigResponse.sorting;
        const colorsResponse = uiConfigResponse.colors;
        const filtersResponse = uiConfigResponse.filters;

        setColorMap(colorsResponse);
        loadFiltersFromArrayToURL(filtersResponse);

        const columns = [];

        // Add hidden column for responsive data
        columns.push({
            title: "Responsive Data",
            field: "_responsive_data",
            visible: true,
            responsive: 1,
            headerSort: false,
            minWidth: 5000, // Large width to force responsive mode
            width: 5000,
            cssClass: "dummy-column",
        });

        // Add the regular columns
        configResponse.forEach(column => {
            const columnType = column.type || "string";
            const columnSorter = columnType in sorterMap ? sorterMap[columnType] : "string"
            if (columnType === "datetime" && column.formatType === "relative") {
                relativeFields.push(column.field);
            }
            let cssClass = columnSorter === "string" ? "clickable-cell" : "unclickable-cell";
            cssClass += ` ${columnType || "regular"}-field`;

            // Special handling for indicator type
            let formatter;
            if (columnType === "indicator") {
                formatter = formatterMap[columnType];
            } else {
                formatter = formatterWrapper(formatterMap[columnType] || undefined);
            }

            const columLayout = {
                title: column.title,
                field: column.field,
                visible: column.visible !== undefined ? column.visible : true,
                sorter: columnSorter,
                headerSort: column.headerSort !== undefined ? column.headerSort : true,
                formatter: formatter,
                formatterParams: columnType in formatterParamsMap ? formatterParamsMap[columnType](column) : undefined,
                cssClass: cssClass,
                vertAlign: "middle",
                responsive: 0, // Keep regular columns always visible
            }
            if (columnType === "indicator") {
                columLayout.minWidth = 37;
                columLayout.maxWidth = 37;
                columLayout.resizable = false;
            }
            columns.push(columLayout);
        });

        // Add the responsive collapse column at the end
        columns.push({
            formatter: "responsiveCollapse",
            width: 30,
            minWidth: 30,
            hozAlign: "center",
            resizable: false,
            headerSort: false,
            responsive: 0,
            title: "",
            field: "_collapse",
        });

        // Add alerts count column
        columns.push({
            title: "",
            field: "_alerts_count",
            width: 30,
            minWidth: 30,
            maxWidth: 30,
            hozAlign: "center",
            resizable: false,
            headerSort: false,
            responsive: 0,
            formatter: formatterMap["alerts_count"],
            cssClass: "unclickable-cell alerts-count-column",
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
