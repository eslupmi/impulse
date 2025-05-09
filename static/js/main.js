import {initializeTable, updateRelativeTimeFields} from "./table.js";
import {setupWebSocketEvents} from "./websocket.js";
import {loadFiltersFromURL, setupTableFiltering, updateZoomIcons} from "./filters.js";
import {setupSortingListener} from "./sorters.js";
import {updateRelativeTimeSpans} from "./formatters.js";
import {ThemeManager} from "./theme.js";


// **Initialize Everything**
initializeTable().then(() => {
    loadFiltersFromURL();
    setupTableFiltering();
    setupSortingListener();
    setupWebSocketEvents();
    ThemeManager.init();
    
    // Update zoom icons after table initialization and filters are loaded
    setTimeout(() => {
        updateZoomIcons();
    }, 100);
    
    // Update table relative time fields every second
    setInterval(() => updateRelativeTimeFields(), 1000);
    
    // Update header block relative time spans every minute
    setInterval(() => updateRelativeTimeSpans(), 60000);
});
