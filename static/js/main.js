import {initializeTable, updateRelativeTimeFieldsInTable} from "./table.js";
import {setupWebSocketEvents, updateOnlineStatus, initHistoryToggle} from "./websocket.js";
import {loadFiltersFromURL, setupTableFiltering, updateZoomIcons} from "./filters.js";
import {setupSortingListener} from "./sorters.js";
import {updateRelativeTimeSpans, updateRelativeTimeFieldsInResponsiveData} from "./formatters.js";
import {ThemeManager} from "./theme.js";
import {ChainsManager} from "./chains.js";

updateOnlineStatus(false);

await initializeTable();

loadFiltersFromURL();
setupTableFiltering();
setupSortingListener();
setupWebSocketEvents();
initHistoryToggle();
ThemeManager.init();
ChainsManager.init();

// Update zoom icons after table initialization and filters are loaded
setTimeout(() => {
    updateZoomIcons();
}, 100);

// Update table relative time fields every second
setInterval(() => updateRelativeTimeFieldsInTable(), 1000);
setInterval(() => updateRelativeTimeFieldsInResponsiveData(), 1000);

// Update header block relative time spans every minute
setInterval(() => updateRelativeTimeSpans(), 60000);
