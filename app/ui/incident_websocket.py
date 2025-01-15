from app.incident.incidents import Incidents
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

    def update_row(self, row_data):
        self.socketio.emit('update_row', row_data)

    def add_row(self, row_data):
        self.socketio.emit('add_row', row_data)

    def get_full_table(self, incidents: Incidents):
        values_to_get = {field['name']: field['object'] for field in self.table_config['labels']}
        data = incidents.get_table(values_to_get)
        self.socketio.emit('update_data', data)
