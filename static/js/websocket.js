import {table} from "./table.js";
import {updateZoomIcons} from "./filters.js";

const socket = io.connect(location.origin, {path: "/ws"});

// Handle WebSocket Events
function setupWebSocketEvents() {
    socket.on("add_row", rowData => {
        table.addRow(rowData);
        table.setSort(table.getSorters());
        updateZoomIcons();
    });

    socket.on("update_row", rowData => {
        table.updateOrAddData([rowData]);
        table.setSort(table.getSorters());
        updateZoomIcons();
    });

    socket.on("remove_row", rowData => {
        const rows = table.searchRows('uuid', '=', rowData.uuid);
        rows.forEach(row => row.delete());
        updateZoomIcons();
    });

    socket.on("update_data", data => {
        table.setData(data);
        table.setSort(table.getSorters());
        updateZoomIcons();
    });

    // Request initial data from WebSocket
    socket.emit("request_data");
}

export {setupWebSocketEvents};
