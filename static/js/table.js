import {getBaseUrl} from "./utils.js";
import {
    formatterMap,
    formatterParamsMap,
    formatterWrapper,
    responsiveLayoutCollapseFormatter,
    setColorMap,
} from "./formatters.js";
import {loadFiltersFromArrayToURL} from "./filters.js";
import {initializeSorting} from "./sorters.js";
import {initUserSelector, userSelectorFormatter} from "./user_selector.js";
import {initActionButtons, actionButtonsFormatter} from "./action_buttons.js";

const relativeFields = [];

const tableOptions = {
    layout: "fitColumns",
    pagination: "local",
    paginationSize: Math.floor((document.getElementById("data-table").clientHeight - 30) / 45),
    paginationAddRow: "table",
    index: "uniq_id",
    responsiveLayout: "collapse",
    responsiveLayoutCollapseStartOpen: false,
    responsiveLayoutCollapseFormatter: responsiveLayoutCollapseFormatter,
    responsiveLayoutCollapseUseFormatters: false,
    sortOrderReverse:true,
    placeholder: function() {
        return table.initialDataLoaded ? "No Incidents" : "Loading incidents...";
    },
    renderVertical: 'basic',
    rowFormatter: function(row) {
        const data = row.getData();
        if (data._is_frozen) {
            row.getElement().classList.add('frozen-row');
        } else {
            row.getElement().classList.remove('frozen-row');
        }
    },
};

const table = new Tabulator("#data-table", tableOptions);
table.initialDataLoaded = false;

// Custom sorters
const sorterMap = {
    "datetime": (a, b) => a - b,
    "link": "string",
    "indicator": undefined,
};

// Fetch table configuration and sorting, then initialize the table
async function initializeTable() {
    try {
        const baseUrl = getBaseUrl();
        const apiUrl = `${baseUrl}/ui_config`;
        
        const uiConfigResponse = await fetch(apiUrl).then(res => {
            if (!res.ok) {
                throw new Error(`HTTP error! status: ${res.status}`);
            }
            return res.json();
        });
        
        const configResponse = uiConfigResponse.table_config;
        const sortingResponse = uiConfigResponse.sorting;
        const colorsResponse = uiConfigResponse.colors;
        const filtersResponse = uiConfigResponse.filters;

        setColorMap(colorsResponse);
        loadFiltersFromArrayToURL(filtersResponse);
        initActionButtons(uiConfigResponse);

        await initUserSelector(baseUrl);

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

        columns.push(
            {
                title: "",
                field: "_action_state",
                width: 90,
                minWidth: 80,
                hozAlign: "right",
                resizable: false,
                headerSort: false,
                responsive: 0,
                formatter: actionButtonsFormatter,
                cssClass: "unclickable-cell action-buttons-column",
            },
            {
                title: "",
                field: "_assigned_user_id",
                width: 120,
                minWidth: 100,
                hozAlign: "right",
                resizable: false,
                headerSort: false,
                responsive: 0,
                formatter: userSelectorFormatter,
                cssClass: "unclickable-cell user-selector-column",
            },
            {
                formatter: "responsiveCollapse",
                width: 30,
                minWidth: 30,
                hozAlign: "center",
                resizable: false,
                headerSort: false,
                responsive: 0,
                title: "",
                field: "_collapse",
            },
            {
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
            },
        );

        initializeSorting(columns, sortingResponse);
        return uiConfigResponse;
    } catch (error) {
        console.error("Error initializing table:", error);
        return {frontend_modules: []};
    }
}

// Auto-update relative time fields every 10 seconds
function updateRelativeTimeFieldsInTable() {
    table.getRows().forEach(row => {
        row.getCells().forEach(cell => {
            if (relativeFields.includes(cell.getColumn().getField())) {
                cell.setValue(cell.getValue(), true);
            }
        });
    });
}

export {initializeTable, updateRelativeTimeFieldsInTable, table};
