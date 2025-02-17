import {initializeTable, updateRelativeTimeFields} from "./table.js";
import {setupWebSocketEvents} from "./websocket.js";
import {loadFiltersFromURL, setupTableFiltering} from "./filters.js";


// **Initialize Everything**
initializeTable().then(() => {
    loadFiltersFromURL();
    setupTableFiltering();
    setupWebSocketEvents();
    setInterval(() => updateRelativeTimeFields(), 10000);
});
