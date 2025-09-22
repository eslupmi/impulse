from datetime import datetime

from app.im.template import JinjaTemplate, update_alerts
from app.incident.incident import IncidentConfig, Incident
from app.logging import logger
from app.queue.handlers.base_handler import BaseHandler
from app.time import unix_sleep_to_timedelta
from config import INCIDENT_ACTUAL_VERSION, incident, experimental


class AlertHandler(BaseHandler):
    """
    AlertHandler class is responsible for handling the alert event.

    :param queue: AsyncQueue instance
    :param application: Application instance
    :param incidents: Incidents instance
    :param route: Route instance
    """
    __slots__ = ['queue', 'application', 'incidents', 'route']

    def __init__(self, queue, application, incidents, route):
        super().__init__(queue, application, incidents)
        self.route = route

    async def handle(self, alert_state):
        incident_ = self.incidents.get(alert=alert_state)
        if incident_ is None:
            await self._handle_create(alert_state)
        else:
            logger.debug(f'New Alertmanager event for incident {incident_.uuid}:')
            logger.debug(f'{alert_state}')
            await self._handle_update(incident_.uuid, incident_, alert_state)

    async def _handle_create(self, alert_state):
        channel_name, chain_name = self.route.get_route(alert_state)
        channel = self.app.channels[channel_name]

        status = alert_state['status']
        updated_datetime = datetime.utcnow()
        status_update_datetime = datetime.utcnow() + unix_sleep_to_timedelta(incident['timeouts'].get(status))

        config = IncidentConfig(
            application_type=self.app.type,
            application_url=self.app.url,
            application_team=self.app.team
        )
        incident_ = Incident(
            payload=alert_state,
            status=status,
            channel_id=channel['id'],
            config=config,
            chain=[],
            chain_enabled=True,
            status_enabled=True,
            updated=updated_datetime,
            status_update_datetime=status_update_datetime,
            assigned_user_id="",
            assigned_user="",
            assigned_fullname="",
            version=INCIDENT_ACTUAL_VERSION
        )
        await self._create_thread(incident_, alert_state)
        incident_.dump()

        self.incidents.add(incident_)

        logger.info(f'Incident {incident_.uuid} created. Link: {incident_.link}')
        [logger.info(f'  {i}: {alert_state["groupLabels"][i]}') for i in alert_state['groupLabels'].keys()]
        logger.debug(f'{alert_state}')

        await self.queue.put(status_update_datetime, 'update_status', incident_.uuid)

        incident_.generate_chain(self.app.chains, chain_name)
        await self.queue.recreate(status, incident_.uuid, incident_.chain)

    async def _handle_update(self, uuid_, incident_, alert_state):
        is_new_firing_alerts_added = False
        is_some_firing_alerts_removed = False
        prev_status = incident_.status

        # Generate chain from scratch if incident chain is empty
        if prev_status == 'resolved' and incident_.chain_enabled and incident_.chain == []:
            _, chain_name = self.route.get_route(alert_state)
            incident_.generate_chain(self.app.chains, chain_name)
            
        await self.queue.recreate(alert_state.get('status'), uuid_, incident_.get_chain())

        # Check new alerts firing or old alerts resolved
        chain_recreate = experimental.get('recreate_chain', False)
        if incident['notifications']['new_firing'] or chain_recreate:
            is_new_firing_alerts_added = incident_.is_new_firing_alerts_added(alert_state)
        if incident['notifications']['partial_resolved']:
            is_some_firing_alerts_removed = incident_.is_some_firing_alerts_removed(alert_state)
        is_status_updated, is_state_updated = incident_.update_state(alert_state)
        
        # Experimental !
        if prev_status == 'firing' and chain_recreate and is_new_firing_alerts_added:
            incident_.chain_enabled = True

        if is_state_updated or is_status_updated:
            await self.app.update(
                uuid_, incident_, alert_state['status'], alert_state, is_status_updated,
                incident_.chain_enabled, incident_.status_enabled
            )

        if prev_status == 'firing' and incident_.status == 'firing':
            # Experimental !
            if is_new_firing_alerts_added and chain_recreate:
                await self._new_alerts_recreate_chain(alert_state, incident_, uuid_)
            # Some alerts status change notification
            if (is_new_firing_alerts_added or is_some_firing_alerts_removed) and incident_.status_enabled:
                await self._notify_new_fire_alert(
                    incident_, is_new_firing_alerts_added, is_some_firing_alerts_removed,
                    uuid_, chain_recreate
                )
        await self.queue.update(uuid_, incident_.status_update_datetime, incident_.status)

    async def _notify_new_fire_alert(self, incident_, new_alerts_f, new_alerts_r, uuid_, experimental_recreate):
        """
        Notify about new firing alerts added to the incident
        """
        header = self.app.format_text_italic(
            self.app.header_template.form_message(incident_.payload, incident_)
        )
        fields = {
            'type': self.app.type,
            'firing': new_alerts_f,
            'resolved': new_alerts_r,
            'recreate': experimental_recreate
        }
        text = JinjaTemplate(update_alerts).form_notification(fields)
        if self.app.type == 'telegram':
            message = text
        else:
            message = header + '\n' + text
        await self.app.post_thread(incident_.channel_id, incident_.ts, message)
        if new_alerts_f:
            logger.info(f"Incident {uuid_} updated with new alerts firing")
        elif new_alerts_r:
            logger.info(f"Incident {uuid_} updated with some alerts resolved")

    async def _new_alerts_recreate_chain(self, alert_state, incident_, uuid_):
        """
        EXPERIMENTAL: release incident and recreate chain by new firing alerts
        """
        await self.queue.delete_by_id(incident_.uuid, delete_steps=True, delete_status=False)
        _, chain_name = self.route.get_route(alert_state)
        incident_.chain = []
        incident_.generate_chain(self.app.chains, chain_name)
        await self.queue.recreate(incident_.status, incident_.uuid, incident_.chain)
        incident_.dump()
        logger.info(f"Incident {uuid_} chain recreated")

    async def _create_thread(self, incident_, alert_state):
        body = self.app.body_template.form_message(alert_state, incident_)
        header = self.app.header_template.form_message(alert_state, incident_)
        status_icons = self.app.status_icons_template.form_message(alert_state, incident_)
        thread_id = await self.app.create_thread(
            incident_.channel_id, body, header, status_icons, status=alert_state['status']
        )
        incident_.set_thread(thread_id, self.app.public_url)
        return thread_id
