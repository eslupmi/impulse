from app.queue.handlers.base_handler import BaseHandler


class StatusUpdateHandler(BaseHandler):
    """
    StatusUpdateHandler class is responsible for handling the status update event.
    """
    async def handle(self, uniq_id):
        incident = self.incidents.uniq_ids.get(uniq_id)
        new_status = incident.next_status[incident.status]
        if new_status == 'closed':
            self.incidents.remove_file(incident)
        status_updated = incident.update_status(new_status)

        if incident.status != 'deleted':
            await self.app.update(
                incident, incident.status, incident.payload,
                status_updated, incident.chain_enabled, incident.status_enabled, incident.task_link
            )

        if incident.status == 'unknown' or incident.status == 'closed':
            await self.queue.update(uniq_id, incident.status_update_datetime, incident.status)

        if incident.status == 'closed':
            await self.queue.delete_by_id(uniq_id, delete_steps=True, delete_status=False)

        if incident.status == 'deleted':
            self.incidents.del_by_uniq_id(uniq_id)
