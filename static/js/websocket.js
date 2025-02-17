import {table} from "./table.js";

const socket = io.connect(location.origin, {path: "/ws"});

// Handle WebSocket Events
function setupWebSocketEvents() {
    socket.on("add_row", rowData => {
        table.addRow(rowData);
        table.setSort(table.getSorters());
    });

    socket.on("update_row", rowData => {
        table.updateOrAddData([rowData]);
        table.setSort(table.getSorters());
    });

    socket.on("remove_row", rowData => {
        const rows = table.searchRows('uuid', '=', rowData.uuid);
        rows.forEach(row => row.delete());
    });

    socket.on("update_data", data => {
        table.setData(data);
        table.setSort(table.getSorters());
    });

    // Request initial data from WebSocket
    socket.emit("request_data");
}

export {setupWebSocketEvents};