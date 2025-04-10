import {initializeTable, updateRelativeTimeFields} from "./table.js";
import {setupWebSocketEvents} from "./websocket.js";
import {loadFiltersFromURL, setupTableFiltering, updateZoomIcons} from "./filters.js";
import {setupSortingListener} from "./sorters.js";


// **Initialize Everything**
initializeTable().then(() => {
    loadFiltersFromURL();
    setupTableFiltering();
    setupSortingListener();
    setupWebSocketEvents();
    
    // Update zoom icons after table initialization and filters are loaded
    setTimeout(() => {
        updateZoomIcons();
    }, 100);
    
    setInterval(() => updateRelativeTimeFields(), 1000);
});
