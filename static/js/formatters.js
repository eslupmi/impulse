import {ZOOM_IN_ICON, ZOOM_OUT_ICON, LINK_ICON} from "./constants.js";

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
    },
    "alerts_count": (cell) => {
        return formatAlertsCount(cell);
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
            formatType: data.formatType || "relative",
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
    return formatDate(date);
}

function formatDate(dateObj) {
    if (!(dateObj instanceof Date)) {
        dateObj = new Date(dateObj);
    }
    const offset = dateObj.getTimezoneOffset()
    dateObj = new Date(dateObj.getTime() - (offset*60*1000))

    const dateTime = dateObj.toISOString().split('T');
    const date = dateTime[0];
    const time = dateTime[1].split('.')[0];
    return `${date} ${time}`;
}

function formatDuration(seconds) {
    // Define time intervals in seconds
    const intervals = [
        {label: "d", seconds: 86400},    // Day
        {label: "h", seconds: 3600},     // Hour
        {label: "m", seconds: 60},       // Minute
    ];

    let result = [];

    for (let i = 0; i < intervals.length && result.length < 1; i++) {
        const {label, seconds: intervalSeconds} = intervals[i];
        const value = Math.floor(seconds / intervalSeconds);
        if (value > 0) {
            result.push(`${value}${label}`);
            seconds -= value * intervalSeconds;
        }
    }

    return result.length > 0 ? result[0] : "< 1m";
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

        if (columnColors && columnColors[columnName] && columnColors[columnName][cellValue]) {
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
            textDiv.className = "original-formatter";
            
            // Special handling for datetime formatter with relative time
            if (formatter === formatterMap.datetime && formatterParams.formatType === "relative") {
                const timeSpan = document.createElement("span");
                timeSpan.textContent = text;
                timeSpan.title = formatTimestamp(cell.getValue());
                textDiv.appendChild(timeSpan);
            } else {
                textDiv.textContent = text;
            }
            
            container.appendChild(textDiv);
        }
        
        // Add zoom icons for filterable cells
        if (!cell.getElement().classList.contains("unclickable-cell")) {
            // Add zoom-in icon (for "=" filter)
            const zoomInIcon = document.createElement("span");
            zoomInIcon.className = "zoom-icon zoom-in";
            zoomInIcon.innerHTML = ZOOM_IN_ICON;
            container.appendChild(zoomInIcon);
            
            // Add zoom-out icon (for "!=" filter)
            const zoomOutIcon = document.createElement("span");
            zoomOutIcon.className = "zoom-icon zoom-out";
            zoomOutIcon.innerHTML = ZOOM_OUT_ICON;
            container.appendChild(zoomOutIcon);
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
            
            // Add zoom icons for filterable cells
            if (!cell.getElement().classList.contains("unclickable-cell")) {
                // Add zoom-in icon (for "=" filter)
                const zoomInIcon = document.createElement("span");
                zoomInIcon.className = "zoom-icon zoom-in";
                zoomInIcon.innerHTML = ZOOM_IN_ICON;
                container.appendChild(zoomInIcon);
                
                // Add zoom-out icon (for "!=" filter)
                const zoomOutIcon = document.createElement("span");
                zoomOutIcon.className = "zoom-icon zoom-out";
                zoomOutIcon.innerHTML = ZOOM_OUT_ICON;
                container.appendChild(zoomOutIcon);
            }
            
            return container;
        };
    }
    
    return colorFormatter;
}

function formatIndicator(cell, params) {
    const indicatorDiv = document.createElement("div");
    indicatorDiv.className = `status-indicator ${cell.getValue().toLowerCase()}`;
    return indicatorDiv;
}

function formatAlertsCount(cell) {
    const count = cell.getValue();
    if (!count || count <= 1) {
        return null;
    }
    const circle = document.createElement("div");
    circle.className = "alerts-count-circle";
    circle.textContent = count;
    return circle;
}

function getColorMap() {
    return columnColors;
}

function setColorMap(colors) {
    columnColors = colors;
}

function createHeaderBlock(headerData) {
    if (!headerData || Object.keys(headerData).length === 0) {
        return null;
    }

    const headerDiv = document.createElement('div');
    headerDiv.className = 'alert-header';

    // Status badge
    if (headerData.status) {
        const statusBadge = document.createElement('span');
        statusBadge.className = `status-badge ${headerData.status.toLowerCase()}`;
        statusBadge.textContent = headerData.status;
        headerDiv.appendChild(statusBadge);
    }

    // Time info
    const time = headerData.status === "resolved" ? headerData.endsAt : headerData.startsAt;
    if (time) {
        // Create wrapper for time and its tooltip
        const timeWrapper = document.createElement('div');
        timeWrapper.className = 'time-wrapper';

        const timeSpan = document.createElement('span');
        const timeDate = new Date(time);
        const unixTimestamp = timeDate.getTime()/1000;
        timeSpan.textContent = formatRelativeTime(unixTimestamp);
        timeSpan.dataset.timestamp = unixTimestamp;
        timeSpan.dataset.startsAt = headerData.startsAt;
        timeSpan.dataset.endsAt = headerData.endsAt;
        timeSpan.dataset.status = headerData.status;
        timeSpan.className = 'relative-time';
        
        // Create tooltip with detailed time information
        const tooltipText = document.createElement('div');
        tooltipText.className = 'tooltip-text time-tooltip';
        updateTimeTooltip(tooltipText, timeSpan);
        
        timeWrapper.appendChild(timeSpan);
        timeWrapper.appendChild(tooltipText);
        headerDiv.appendChild(timeWrapper);
    }

    // Generator URL
    if (headerData.generatorURL) {
        const linkSpan = document.createElement('a');
        linkSpan.href = headerData.generatorURL;
        linkSpan.target = '_blank';
        linkSpan.className = 'generator-link';
        linkSpan.innerHTML = LINK_ICON;
        headerDiv.appendChild(linkSpan);
    }

    return headerDiv;
}

/**
 * Shared helper to create a pill (label or annotation) with truncation and tooltip.
 * @param {string} key
 * @param {string} value
 * @param {object} options - {wrapperClass, pillClass, highlighted, isCommonBlock}
 * @returns {HTMLElement}
 */
function createTruncatedPill(key, value, options = {}) {
    const { wrapperClass, pillClass, highlighted, isCommonBlock } = options;
    const wrapper = document.createElement('div');
    wrapper.className = wrapperClass;

    const pill = document.createElement('span');
    let pillClassName = pillClass;
    if (highlighted) {
        pillClassName += ' highlighted';
    }
    if (isCommonBlock !== undefined) {
        pillClassName += isCommonBlock ? ' common' : ' alert';
    }
    pill.className = pillClassName;
    pill.textContent = `${key}: ${value}`;

    // Check if the text is truncated
    const isTruncated = () => {
        const temp = document.createElement('span');
        temp.style.visibility = 'hidden';
        temp.style.position = 'absolute';
        temp.style.whiteSpace = 'nowrap';
        temp.textContent = `${key}: ${value}`;
        document.body.appendChild(temp);
        const fullWidth = temp.offsetWidth;
        temp.remove();
        return fullWidth > (isCommonBlock ? 430 : 285);
    };

    wrapper.appendChild(pill);

    if (isTruncated()) {
        const tooltipText = document.createElement('div');
        tooltipText.className = 'tooltip-text';
        tooltipText.textContent = `${key}: ${value}`;
        tooltipText.style.userSelect = 'text';
        tooltipText.style.webkitUserSelect = 'text';
        tooltipText.style.mozUserSelect = 'text';
        tooltipText.style.msUserSelect = 'text';
        wrapper.appendChild(tooltipText);
    }

    return wrapper;
}

function createLabelsBlock(labelsData, isCommonBlock = false) {
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
            labelsList.appendChild(createTruncatedPill(key, value, {
                wrapperClass: 'label-wrapper',
                pillClass: 'label',
                highlighted: true,
                isCommonBlock
            }));
        });
    }

    // Add regular labels
    if (labelsData.regular && Object.keys(labelsData.regular).length > 0) {
        Object.entries(labelsData.regular).forEach(([key, value]) => {
            labelsList.appendChild(createTruncatedPill(key, value, {
                wrapperClass: 'label-wrapper',
                pillClass: 'label',
                highlighted: false,
                isCommonBlock
            }));
        });
    }

    labelsDiv.appendChild(labelsList);
    return labelsDiv;
}

function createAnnotationsBlock(annotations, isCommonBlock = false) {
    if (!annotations || Object.keys(annotations).length === 0) {
        return null;
    }

    const annotationsDiv = document.createElement('div');
    annotationsDiv.className = 'block-annotations';

    Object.entries(annotations).forEach(([key, value]) => {
        annotationsDiv.appendChild(createTruncatedPill(key, value, {
            wrapperClass: 'annotation-wrapper',
            pillClass: `annotation${isCommonBlock ? ' common' : ' alert'}`,
            highlighted: false,
            isCommonBlock
        }));
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
    const labelsBlock = createLabelsBlock(labels, isCommonBlock);
    if (labelsBlock) {
        block.appendChild(labelsBlock);
    }

    // Add annotations if exists
    const annotationsBlock = createAnnotationsBlock(annotations, isCommonBlock);
    if (annotationsBlock) {
        block.appendChild(annotationsBlock);
    }

    return block;
}

function createSimpleCommonBlock(responsiveData) {
    const commonBlock = document.createElement('div');
    commonBlock.className = 'simple-common-block';

    const info = responsiveData.incident_info || {};
    
    const infoStack = document.createElement('div');
    infoStack.className = 'info-stack';
    
    const statusSpan = document.createElement('span');
    statusSpan.className = 'info-item';
    statusSpan.innerHTML = `<strong>status:</strong> <span class="status-value ${info.status}">${info.status}</span>`;
    infoStack.appendChild(statusSpan);
    
    const createdTimeAgo = formatRelativeTime(info.created);
    const createdSpan = document.createElement('span');
    createdSpan.className = 'info-item info-item-time';
    createdSpan.dataset.timestamp = info.created;
    createdSpan.innerHTML = `<strong>created:</strong> <div class="relative-time-label">${createdTimeAgo}</div>`;
    createdSpan.title = formatTimestamp(info.created);
    infoStack.appendChild(createdSpan);
    
    const updatedTimeAgo = formatRelativeTime(info.updated);
    const updatedSpan = document.createElement('span');
    updatedSpan.className = 'info-item info-item-time';
    updatedSpan.dataset.timestamp = info.updated;
    updatedSpan.innerHTML = `<strong>updated:</strong> <div class="relative-time-label">${updatedTimeAgo}</div>`;
    updatedSpan.title = formatTimestamp(info.updated);
    infoStack.appendChild(updatedSpan);
    
    const assignedSpan = document.createElement('span');
    assignedSpan.className = 'info-item';
    assignedSpan.innerHTML = `<strong>assigned to:</strong> ${info.assigned_fullname ? info.assigned_fullname : '-'}`;
    infoStack.appendChild(assignedSpan);
    
    if (info.link) {
        const linkSpan = document.createElement('span');
        linkSpan.className = 'info-item';
        linkSpan.innerHTML = `<strong>link:</strong> <a href="${info.link}" target="_blank" class="incident-link">${LINK_ICON}</a>`;
        infoStack.appendChild(linkSpan);
    }
    
    if (info.task_link) {
        const taskLinkSpan = document.createElement('span');
        taskLinkSpan.className = 'info-item';
        taskLinkSpan.innerHTML = `<strong>task:</strong> <a href="${info.task_link}" target="_blank" class="incident-link">${LINK_ICON}</a>`;
        infoStack.appendChild(taskLinkSpan);
    }
    
    commonBlock.appendChild(infoStack);

    // Common labels section
    if ((responsiveData.common_labels && Object.keys(responsiveData.common_labels).length > 0) || (responsiveData.group_labels && Object.keys(responsiveData.group_labels).length > 0)) {
        const commonLabelsSection = document.createElement('div');
        commonLabelsSection.className = 'labels-section';
        
        const commonLabelsHeader = document.createElement('div');
        commonLabelsHeader.className = 'section-header';
        commonLabelsHeader.innerHTML = '<strong>common labels:</strong>';
        commonLabelsSection.appendChild(commonLabelsHeader);
        
        if (responsiveData.group_labels) {
            Object.entries(responsiveData.group_labels).forEach(([key, value]) => {
                const labelWrapper = createTruncatedPill(key, value, {
                    wrapperClass: 'label-wrapper',
                    pillClass: 'label group-label',
                    highlighted: false,
                    isCommonBlock: true
                });
                commonLabelsSection.appendChild(labelWrapper);
            });
        }
        
        if (responsiveData.common_labels) {
            Object.entries(responsiveData.common_labels).forEach(([key, value]) => {
                const labelWrapper = createTruncatedPill(key, value, {
                    wrapperClass: 'label-wrapper',
                    pillClass: 'label',
                    highlighted: false,
                    isCommonBlock: true
                });
                commonLabelsSection.appendChild(labelWrapper);
            });
        }
        
        commonBlock.appendChild(commonLabelsSection);
    }

    // Common annotations section
    if (responsiveData.common_annotations && Object.keys(responsiveData.common_annotations).length > 0) {
        const commonAnnotationsSection = document.createElement('div');
        commonAnnotationsSection.className = 'annotations-section';
        
        const commonAnnotationsHeader = document.createElement('div');
        commonAnnotationsHeader.className = 'section-header';
        commonAnnotationsHeader.innerHTML = '<strong>common annotations:</strong>';
        commonAnnotationsSection.appendChild(commonAnnotationsHeader);
        
        Object.entries(responsiveData.common_annotations).forEach(([key, value]) => {
            const annotationWrapper = createTruncatedPill(key, value, {
                wrapperClass: 'annotation-wrapper',
                pillClass: 'annotation',
                highlighted: false,
                isCommonBlock: true
            });
            commonAnnotationsSection.appendChild(annotationWrapper);
        });
        
        commonBlock.appendChild(commonAnnotationsSection);
    }

    return commonBlock;
}

function responsiveLayoutCollapseFormatter(data) {

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

    // Create main container element
    const container = document.createElement('div');
    container.className = 'responsive-collapse';

    // Create common information block (always show if we have incident info or group labels)
    if ((responsiveData.incident_info) || 
        (responsiveData.group_labels && Object.keys(responsiveData.group_labels).length > 0)) {
        const commonBlock = createSimpleCommonBlock(responsiveData);
        container.appendChild(commonBlock);
    }

    // Create alerts section
    if (responsiveData.alerts && responsiveData.alerts.length > 0) {
        const alertsSection = document.createElement('div');
        alertsSection.className = 'alerts-section';

        // Add "alerts:" label
        const alertsLabel = document.createElement('div');
        alertsLabel.className = 'alerts-label';
        alertsLabel.textContent = 'alerts:';
        alertsSection.appendChild(alertsLabel);

        // Create alerts wrapper
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
                    highlighted: {},
                    regular: alert.labels || {}
                },
                alert.annotations || {},
                false // isCommonBlock flag
            );
            alertsWrapper.appendChild(alertBlock);
        });

        alertsSection.appendChild(alertsWrapper);
        container.appendChild(alertsSection);
    }

    return container;
}

function updateTimeTooltip(tooltipText, timeSpan) {
    const startsAt = timeSpan.dataset.startsAt;
    const endsAt = timeSpan.dataset.endsAt;
    const status = timeSpan.dataset.status;
    
    const createdTime = new Date(startsAt);
    const createdTimeStr = formatDate(createdTime);
    const createdTimeAgo = formatRelativeTime(createdTime.getTime()/1000);
    
    let tooltipContent = `Created: ${createdTimeAgo} (${createdTimeStr})`;
    
    // Calculate firing duration for both resolved and non-resolved alerts
    const endTime = status === "resolved" ? new Date(endsAt) : new Date();
    const firingDuration = Math.floor((endTime - createdTime) / 1000);
    const firingDurationStr = formatDuration(firingDuration);
    tooltipContent += `\nFiring for: ${firingDurationStr}`;
    
    if (status === "resolved" && endsAt) {
        const resolvedTime = new Date(endsAt);
        const resolvedTimeStr = formatDate(resolvedTime);
        const resolvedTimeAgo = formatRelativeTime(resolvedTime.getTime()/1000);
        tooltipContent += `\nResolved: ${resolvedTimeAgo} (${resolvedTimeStr})`;
    }
    
    tooltipText.textContent = tooltipContent;
}

function updateRelativeTimeSpans() {
    document.querySelectorAll('.tabulator-responsive-collapse-toggle.open').forEach(toggle => {
        const collapseArea = toggle.parentElement.parentElement.querySelector('.tabulator-responsive-collapse')
        if (!collapseArea) return;
        
        collapseArea.querySelectorAll('.relative-time').forEach(timeSpan => {
            const timestamp = Number.parseFloat(timeSpan.dataset.timestamp);
            if (!Number.isNaN(timestamp)) {
                timeSpan.textContent = formatRelativeTime(timestamp);
                // Update tooltip if it exists
                const tooltipText = timeSpan.querySelector('.tooltip-text');
                if (tooltipText) {
                    updateTimeTooltip(tooltipText, timeSpan);
                }
            }
        });
    });
}

function updateRelativeTimeFieldsInResponsiveData() {
    document.querySelectorAll('.responsive-collapse').forEach(collapse => {
            collapse.querySelectorAll('.info-item-time').forEach(timeSpan => {
            const timestamp = Number.parseFloat(timeSpan.dataset.timestamp);
            if (!Number.isNaN(timestamp)) {
                timeSpan.querySelector('.relative-time-label').textContent = formatRelativeTime(timestamp);
            }
        });
    });
}

export {formatterWrapper, setColorMap, formatterMap, formatterParamsMap, responsiveLayoutCollapseFormatter, updateRelativeTimeSpans, updateRelativeTimeFieldsInResponsiveData};
