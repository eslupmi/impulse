import {initializeTable, updateRelativeTimeFields} from "./table.js";
import {setupWebSocketEvents} from "./websocket.js";
import {loadFiltersFromURL, setupTableFiltering} from "./filters.js";
import {setupSortingListener} from "./sorters.js";


// **Initialize Everything**
initializeTable().then(() => {
    loadFiltersFromURL();
    setupTableFiltering();
    setupSortingListener();
    setupWebSocketEvents();
    setInterval(() => updateRelativeTimeFields(), 1000);
});
