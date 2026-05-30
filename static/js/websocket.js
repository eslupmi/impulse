import {table} from "./table.js";
import {updateZoomIcons} from "./filters.js";
import {getBaseUrl} from "./utils.js";

let socket;
let heartbeatInterval;
let heartbeatTimeout;
let showFullTable = false;
const HEARTBEAT_INTERVAL = 10000;
const HEARTBEAT_TIMEOUT = 5000;
const RECONNECT_DELAY = 3000;

// Update online status indicator
function updateOnlineStatus(isOnline) {
    const indicator = document.querySelector('.online-status-indicator');
    if (indicator) {
        if (isOnline) {
            indicator.textContent = 'online';
            indicator.className = 'online-status-indicator online';
        } else {
            indicator.textContent = 'offline';
            indicator.className = 'online-status-indicator offline';
        }
    }
}

// Start heartbeat mechanism
function startHeartbeat() {
    stopHeartbeat();

    heartbeatInterval = setInterval(() => {
        if (socket && socket.readyState === WebSocket.OPEN) {
            socket.send(JSON.stringify({event: "ping"}));

            heartbeatTimeout = setTimeout(() => {
                console.log('Heartbeat timeout - no pong received, connection appears dead');
                updateOnlineStatus(false);
                socket.close();
            }, HEARTBEAT_TIMEOUT);
        }
    }, HEARTBEAT_INTERVAL);
}

// Stop heartbeat mechanism
function stopHeartbeat() {
    if (heartbeatInterval) {
        clearInterval(heartbeatInterval);
        heartbeatInterval = null;
    }
    if (heartbeatTimeout) {
        clearTimeout(heartbeatTimeout);
        heartbeatTimeout = null;
    }
}

// Handle pong response
function handlePong() {
    if (heartbeatTimeout) {
        clearTimeout(heartbeatTimeout);
        heartbeatTimeout = null;
    }
    updateOnlineStatus(true);
}

// Precise scroll position preservation for necessary table operations
function preserveScrollDuringOperation(operation) {
    const scrollElement = table.rowManager.element;
    const savedScrollTop = scrollElement.scrollTop;
    const savedScrollLeft = scrollElement.scrollLeft;
    
    const result = operation();

    const restoreScroll = () => {
        if (scrollElement.scrollTop !== savedScrollTop) {
            scrollElement.scrollTop = savedScrollTop;
        }
        if (scrollElement.scrollLeft !== savedScrollLeft) {
            scrollElement.scrollLeft = savedScrollLeft;
        }
    };
    
    restoreScroll();
    
    requestAnimationFrame(() => {
        restoreScroll();
    });
    
    return result;
}

// Handle WebSocket Events
function setupWebSocketEvents() {
    // Create WebSocket connection
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const baseUrl = getBaseUrl();
    const wsUrl = `${protocol}//${window.location.host}${baseUrl}/ws`;
    
    socket = new WebSocket(wsUrl);

    socket.onopen = function(event) {
        console.log('WebSocket connected');
        updateOnlineStatus(true);
        startHeartbeat();
        table.initialDataLoaded = false;
        table.redraw();
        socket.send(JSON.stringify({event: "request_data", show_full_table: showFullTable}));
    };

    socket.onmessage = function(event) {
        try {
            const message = JSON.parse(event.data);
            const eventType = message.event;
            const data = message.data;

            switch(eventType) {
                case "add_row":
                    preserveScrollDuringOperation(() => {
                        if (showFullTable || (data.indicator !== 'closed' && data.indicator !== 'deleted')) {
                            table.addRow(data);
                            table.setSort(table.getSorters());
                            updateZoomIcons();
                        }
                    });
                    break;
                
                case "update_row":
                    preserveScrollDuringOperation(() => {
                        if (showFullTable || (data.indicator !== 'closed' && data.indicator !== 'deleted')) {
                            table.updateOrAddData([data]);
                            table.setSort(table.getSorters());
                            table.refreshFilter();
                            updateZoomIcons();
                        } else {
                            const rows = table.searchRows('uniq_id', '=', data.uniq_id);
                            rows.forEach(row => row.delete());
                            updateZoomIcons();
                        }
                    });
                    break;
                
                case "remove_row":
                    preserveScrollDuringOperation(() => {
                        const rows = table.searchRows('uniq_id', '=', data.uniq_id);
                        rows.forEach(row => row.delete());
                        updateZoomIcons();
                    });
                    break;
                
                case "update_data":
                    preserveScrollDuringOperation(() => {
                        if (!table.initialDataLoaded) {
                            table.initialDataLoaded = true;
                        }
                        let tableData = data;
                        if (!showFullTable) {
                            tableData = data.filter(row => row.indicator !== 'closed' && row.indicator !== 'deleted');
                        }
                        table.replaceData(tableData);
                        updateZoomIcons();
                    });
                    break;
                
                case "pong":
                    handlePong();
                    break;

                case "ui_chains_data":
                    if (typeof window.handleUiChainsData === 'function') {
                        window.handleUiChainsData(data);
                    }
                    break;

                case "ui_chains_saved":
                    if (typeof window.handleUiChainsSaved === 'function') {
                        window.handleUiChainsSaved(message.success);
                    }
                    break;

                case "module_message":
                    if (window.ImpulseModules && typeof window.ImpulseModules._resolveModuleMessage === 'function') {
                        window.ImpulseModules._resolveModuleMessage(message);
                    }
                    break;

                default:
                    console.log('Unknown WebSocket event:', eventType);
            }
        } catch (error) {
            console.error('Error parsing WebSocket message:', error);
        }
    };

    socket.onclose = function(event) {
        console.log('WebSocket disconnected');
        updateOnlineStatus(false);
        stopHeartbeat();
        setTimeout(setupWebSocketEvents, RECONNECT_DELAY);
    };

    socket.onerror = function(error) {
        console.error('WebSocket error:', error);
        updateOnlineStatus(false);
        stopHeartbeat();
    };
}

function toggleHistoryView() {
    showFullTable = !showFullTable;
    const button = document.getElementById('history-toggle');
    if (button) {
        if (showFullTable) {
            button.classList.add('active');
            button.title = 'Hide archive';
        } else {
            button.classList.remove('active');
            button.title = 'Show archive';
        }
    }
    
    if (socket && socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({event: "request_data", show_full_table: showFullTable}));
    } else {
        console.warn('WebSocket not connected, cannot reload table');
    }
}

function initHistoryToggle() {
    const button = document.getElementById('history-toggle');
    if (button) {
        button.addEventListener('click', toggleHistoryView);
        button.title = 'Show archive';
    }
}

function getSocket() {
    return socket;
}

export {setupWebSocketEvents, updateOnlineStatus, initHistoryToggle, getSocket};
