from app.queue.handlers.base_handler import BaseHandler


class StatusUpdateHandler(BaseHandler):
    """
    StatusUpdateHandler class is responsible for handling the status update event.
    """
    def handle(self, uuid_):
        incident = self.incidents.by_uuid[uuid_]
        status_updated = incident.set_next_status()

        self.app.update(
            uuid_, incident, incident.status, incident.last_state,
            status_updated, incident.chain_enabled, incident.status_enabled
        )

        if incident.status == 'closed':
            self.queue.delete_by_id(uuid_)
            self.incidents.del_by_uuid(uuid_)
        elif incident.status == 'unknown':
            self.queue.update(uuid_, incident.status_update_datetime, incident.status)
