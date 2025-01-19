from config import ui_config
from threading import Lock

class IncidentWS:
    _instance = None
    _lock = Lock()

    def __new__(cls, socketio):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(IncidentWS, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self, socketio):
        if not self._initialized:
            self.socketio = socketio
            self.table_config = ui_config
            self._initialized = True

    @classmethod
    def get_instance(cls):
        return cls._instance

    def update_row(self, incident):
        row_data = incident.get_table_data(self._get_values())
        self.socketio.emit('update_row', row_data)

    def add_row(self, incident):
        row_data = incident.get_table_data(self._get_values())
        self.socketio.emit('add_row', row_data)

    def remove_row(self, incident):
        row_data = incident.get_table_data(self._get_values())
        self.socketio.emit('remove_row', row_data)

    def get_full_table(self, incidents):
        data = incidents.get_table(self._get_values())
        self.socketio.emit('update_data', data)

    def _get_values(self):
        return {field['name']: field['value'] for field in self.table_config['columns']}
