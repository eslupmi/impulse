import {formatterWrapper, formatterMap, formatterParamsMap, setColorMap,} from "./formatters.js";
import {loadFiltersFromArrayToURL} from "./filters.js";
import {initializeSorting} from "./sorters.js";

const relativeFields = [];

function createLabelsList(labels) {
    const labelsDiv = document.createElement('div');
    labelsDiv.className = 'labels-list';
    
    Object.entries(labels).forEach(([key, value]) => {
        if (value) {
            const labelSpan = document.createElement('span');
            labelSpan.className = 'label-pair';
            labelSpan.textContent = `${key}: ${value}`;
            labelsDiv.appendChild(labelSpan);
        }
    });
    
    return labelsDiv;
}

function responsiveLayoutCollapseFormatter(data) {
    console.log('Responsive collapse formatter called with data:', data);
    
    // Handle initial setup case
    if (!data || !Array.isArray(data)) {
        console.log('Initial setup or invalid data');
        return "";
    }

    // Find the object with _responsive_data field
    const responsiveDataItem = data.find(item => item.field === '_responsive_data');
    if (!responsiveDataItem?.value) {
        console.log('No responsive data found');
        return "";
    }

    const responsiveData = responsiveDataItem.value;
    console.log('Found responsive data:', responsiveData);

    // Create container element
    const container = document.createElement('div');
    container.className = 'responsive-collapse';
    
    // Group labels block
    if (Object.keys(responsiveData.group_labels).length > 0) {
        const groupBlock = document.createElement('div');
        groupBlock.className = 'info-block';
        groupBlock.appendChild(createLabelsList(responsiveData.group_labels));
        container.appendChild(groupBlock);
        
        const separator = document.createElement('hr');
        separator.className = 'block-separator';
        container.appendChild(separator);
    }

    // Common labels and annotations block
    if (Object.keys(responsiveData.common_labels).length > 0 || Object.keys(responsiveData.common_annotations).length > 0) {
        const commonBlock = document.createElement('div');
        commonBlock.className = 'info-block';
        
        if (Object.keys(responsiveData.common_labels).length > 0) {
            commonBlock.appendChild(createLabelsList(responsiveData.common_labels));
        }
        
        if (Object.keys(responsiveData.common_annotations).length > 0) {
            const summaryDiv = document.createElement('div');
            summaryDiv.className = 'summary';
            Object.entries(responsiveData.common_annotations).forEach(([key, value]) => {
                summaryDiv.textContent = `${key}: ${value}`;
            });
            commonBlock.appendChild(summaryDiv);
        }
        
        container.appendChild(commonBlock);
        
        if (responsiveData.alerts && responsiveData.alerts.length > 0) {
            const separator = document.createElement('hr');
            separator.className = 'block-separator';
            container.appendChild(separator);
        }
    }

    // Alerts blocks
    if (responsiveData.alerts && responsiveData.alerts.length > 0) {
        responsiveData.alerts.forEach((alert, index) => {
            const alertBlock = document.createElement('div');
            alertBlock.className = 'info-block';

            // Status badge and timing
            if (alert.status) {
                const statusDiv = document.createElement('div');
                statusDiv.className = 'labels-list';
                
                const statusSpan = document.createElement('span');
                statusSpan.className = 'label-pair';
                statusSpan.textContent = `${alert.status} Started: ${new Date(alert.startsAt).toLocaleString()}`;
                statusDiv.appendChild(statusSpan);
                
                if (alert.generatorURL) {
                    const linkSpan = document.createElement('span');
                    linkSpan.className = 'label-pair';
                    const link = document.createElement('a');
                    link.href = alert.generatorURL;
                    link.target = '_blank';
                    link.textContent = 'View in Prometheus';
                    linkSpan.appendChild(link);
                    statusDiv.appendChild(linkSpan);
                }
                
                alertBlock.appendChild(statusDiv);
            }

            // Alert specific labels
            if (Object.keys(alert.labels).length > 0) {
                alertBlock.appendChild(createLabelsList(alert.labels));
            }

            // Alert specific annotations
            if (Object.keys(alert.annotations).length > 0) {
                const annotationsDiv = document.createElement('div');
                annotationsDiv.className = 'summary';
                Object.entries(alert.annotations).forEach(([key, value]) => {
                    annotationsDiv.textContent = `${key}: ${value}`;
                });
                alertBlock.appendChild(annotationsDiv);
            }

            container.appendChild(alertBlock);

            if (index < responsiveData.alerts.length - 1) {
                const separator = document.createElement('hr');
                separator.className = 'block-separator';
                container.appendChild(separator);
            }
        });
    }
    
    console.log('Final container:', container);
    return container;
}

const tableOptions = {
    layout: "fitColumns",
    index: "uuid",
    responsiveLayout: "collapse",
    responsiveLayoutCollapseStartOpen: false,
    responsiveLayoutCollapseFormatter: responsiveLayoutCollapseFormatter,
    responsiveLayoutCollapseUseFormatters: false,
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
        const [configResponse, sortingResponse, colorsResponse, filtersResponse] = await Promise.all([
            fetch('/table_config').then(res => res.json()),
            fetch('/table_sorting').then(res => res.json()),
            fetch('/table_colors').then(res => res.json()),
            fetch('/table_filters').then(res => res.json()),
        ]);

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
