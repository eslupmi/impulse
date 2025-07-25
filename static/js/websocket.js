import {table} from "./table.js";
import {updateZoomIcons} from "./filters.js";

let socket;

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
    const wsUrl = `${protocol}//${window.location.host}/ws`;
    
    socket = new WebSocket(wsUrl);

    socket.onopen = function(event) {
        console.log('WebSocket connected');
        updateOnlineStatus(true);
        // Request initial data
        socket.send(JSON.stringify({event: "request_data"}));
    };

    socket.onmessage = function(event) {
        try {
            const message = JSON.parse(event.data);
            const eventType = message.event;
            const data = message.data;

            switch(eventType) {
                case "add_row":
                    preserveScrollDuringOperation(() => {
                        table.addRow(data);
                        table.setSort(table.getSorters());
                        updateZoomIcons();
                    });
                    break;
                
                case "update_row":
                    preserveScrollDuringOperation(() => {
                        table.updateOrAddData([data]);
                        table.setSort(table.getSorters());
                        table.refreshFilter();
                        updateZoomIcons();
                    });
                    break;
                
                case "remove_row":
                    preserveScrollDuringOperation(() => {
                        const rows = table.searchRows('uuid', '=', data.uuid);
                        rows.forEach(row => row.delete());
                        updateZoomIcons();
                    });
                    break;
                
                case "update_data":
                    preserveScrollDuringOperation(() => {
                        table.updateOrAddData(data);
                        table.setSort(table.getSorters());
                        table.refreshFilter();
                        updateZoomIcons();
                    });
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
        // Attempt to reconnect after 3 seconds
        setTimeout(setupWebSocketEvents, 3000);
    };

    socket.onerror = function(error) {
        console.error('WebSocket error:', error);
        updateOnlineStatus(false);
    };
}

export {setupWebSocketEvents, updateOnlineStatus};
