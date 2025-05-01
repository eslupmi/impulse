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

function createHeaderBlock(headerData) {
    if (!headerData || Object.keys(headerData).length === 0) {
        return null;
    }

    const headerDiv = document.createElement('div');
    headerDiv.className = 'time-info';

    // Status badge
    if (headerData.status) {
        const statusBadge = document.createElement('span');
        statusBadge.className = `status-badge ${headerData.status.toLowerCase()}`;
        statusBadge.textContent = headerData.status;
        headerDiv.appendChild(statusBadge);
    }

    // Time info
    if (headerData.startsAt) {
        const timeSpan = document.createElement('span');
        timeSpan.textContent = `Started: ${new Date(headerData.startsAt).toLocaleString()}`;
        headerDiv.appendChild(timeSpan);
    }

    // Generator URL
    if (headerData.generatorURL) {
        const linkSpan = document.createElement('a');
        linkSpan.href = headerData.generatorURL;
        linkSpan.target = '_blank';
        linkSpan.className = 'generator-link';
        linkSpan.textContent = 'View in Prometheus';
        headerDiv.appendChild(linkSpan);
    }

    return headerDiv;
}

function createLabelsBlock(labelsData) {
    if (!labelsData || (Object.keys(labelsData.highlighted || {}).length === 0 && Object.keys(labelsData.regular || {}).length === 0)) {
        return null;
    }

    const labelsDiv = document.createElement('div');
    labelsDiv.className = 'block-labels';

    const labelsList = document.createElement('div');
    labelsList.className = 'labels-list';

    // Add highlighted labels
    if (labelsData.highlighted && Object.keys(labelsData.highlighted).length > 0) {
        Object.entries(labelsData.highlighted).forEach(([key, value]) => {
            const label = document.createElement('span');
            label.className = 'label highlighted';
            label.textContent = `${key}: ${value}`;
            labelsList.appendChild(label);
        });
    }

    // Add regular labels
    if (labelsData.regular && Object.keys(labelsData.regular).length > 0) {
        Object.entries(labelsData.regular).forEach(([key, value]) => {
            const label = document.createElement('span');
            label.className = 'label';
            label.textContent = `${key}: ${value}`;
            labelsList.appendChild(label);
        });
    }

    labelsDiv.appendChild(labelsList);
    return labelsDiv;
}

function createAnnotationsBlock(annotations) {
    if (!annotations || Object.keys(annotations).length === 0) {
        return null;
    }

    const annotationsDiv = document.createElement('div');
    annotationsDiv.className = 'block-annotations';

    Object.entries(annotations).forEach(([key, value]) => {
        const annotation = document.createElement('div');
        annotation.className = 'annotation';
        annotation.textContent = `${key}: ${value}`;
        annotationsDiv.appendChild(annotation);
    });

    return annotationsDiv;
}

function createInfoBlock(header, labels, annotations, isCommonBlock = false) {
    const block = document.createElement('div');
    block.className = `info-block ${isCommonBlock ? 'common-info-block' : 'alert-info-block'}`;

    // Add header if exists
    const headerBlock = createHeaderBlock(header);
    if (headerBlock) {
        block.appendChild(headerBlock);
    }

    // Add labels if exists
    const labelsBlock = createLabelsBlock(labels);
    if (labelsBlock) {
        block.appendChild(labelsBlock);
    }

    // Add annotations if exists
    const annotationsBlock = createAnnotationsBlock(annotations);
    if (annotationsBlock) {
        block.appendChild(annotationsBlock);
    }

    return block;
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
    
    // Common information block
    const commonBlock = createInfoBlock(
        {}, // No header for common block
        {
            highlighted: responsiveData.group_labels || {},
            regular: responsiveData.common_labels || {}
        },
        responsiveData.common_annotations || {},
        true // isCommonBlock flag
    );
    container.appendChild(commonBlock);

    // Alerts blocks wrapper
    if (responsiveData.alerts && responsiveData.alerts.length > 0) {
        const alertsWrapper = document.createElement('div');
        alertsWrapper.className = 'alerts-wrapper';
        
        responsiveData.alerts.forEach((alert) => {
            const alertBlock = createInfoBlock(
                {
                    status: alert.status,
                    startsAt: alert.startsAt,
                    endsAt: alert.endsAt,
                    generatorURL: alert.generatorURL
                },
                {
                    regular: alert.labels || {}
                },
                alert.annotations || {},
                false // isCommonBlock flag
            );
            alertsWrapper.appendChild(alertBlock);
        });

        container.appendChild(alertsWrapper);
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
