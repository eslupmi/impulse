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

    :param queue: Queue instance
    :param application: Application instance
    :param incidents: Incidents instance
    :param route: Route instance
    """
    __slots__ = ['queue', 'application', 'incidents', 'route']

    def __init__(self, queue, application, incidents, route):
        super().__init__(queue, application, incidents)
        self.route = route

    def handle(self, alert_state):
        incident_ = self.incidents.get(alert=alert_state)
        if incident_ is None:
            self._handle_create(alert_state)
        else:
            logger.debug(f'New Alertmanager event for incident {incident_.uuid}:')
            logger.debug(f'{alert_state}')
            self._handle_update(incident_.uuid, incident_, alert_state)

    def _handle_create(self, alert_state):
        channel_name, chain_name = self.route.get_route(alert_state)
        channel = self.app.channels[channel_name]

        status = alert_state['status']
        updated_datetime = datetime.utcnow()
        status_update_datetime = datetime.utcnow() + unix_sleep_to_timedelta(incident['timeouts'].get(status))

        chain = self.app.chains.get(chain_name)
        config = IncidentConfig(
            application_type=self.app.type,
            application_url=self.app.url,
            application_team=self.app.team
        )
        incident_ = Incident(
            last_state=alert_state,
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
            version=INCIDENT_ACTUAL_VERSION
        )
        self._create_thread(incident_, alert_state)
        incident_.dump()

        self.incidents.add(incident_)

        logger.info(f'Incident {incident_.uuid} created. Link: {incident_.link}')
        [logger.info(f'  {i}: {alert_state["groupLabels"][i]}') for i in alert_state['groupLabels'].keys()]
        logger.debug(f'{alert_state}')

        self.queue.put(status_update_datetime, 'update_status', incident_.uuid)

        incident_.generate_chain(chain)
        self.queue.recreate(status, incident_.uuid, incident_.chain)

    def _handle_update(self, uuid_, incident_, alert_state):
        is_new_firing_alerts_added = False
        is_some_firing_alerts_removed = False

        prev_status = incident_.status
        if prev_status == 'resolved':
            chain = incident_.get_chain()
            self.queue.recreate(alert_state.get('status'), uuid_, chain)

        chain_recreate = experimental.get('recreate_chain', False)
        if incident.get('alerts_firing_notifications') or chain_recreate:
            is_new_firing_alerts_added = incident_.is_new_firing_alerts_added(alert_state)
        if incident.get('alerts_resolved_notifications'):
            is_some_firing_alerts_removed = incident_.is_some_firing_alerts_removed(alert_state)

        is_status_updated, is_state_updated = incident_.update_state(alert_state)

        if prev_status == 'firing' and chain_recreate and is_new_firing_alerts_added:
            incident_.chain_enabled = True

        if is_state_updated or is_status_updated:
            self.app.update(
                uuid_, incident_, alert_state['status'], alert_state, is_status_updated,
                incident_.chain_enabled, incident_.status_enabled
            )

        if prev_status == 'firing' and incident_.status == 'firing':
            if is_new_firing_alerts_added:
                if chain_recreate:
                    self._new_alerts_recreate_chain(alert_state, incident_, uuid_)
            if (is_new_firing_alerts_added or is_some_firing_alerts_removed) and incident_.status_enabled:
                self._notify_new_fire_alert(
                    incident_, is_new_firing_alerts_added, is_some_firing_alerts_removed,
                    uuid_, chain_recreate
                )
        self.queue.update(uuid_, incident_.status_update_datetime, incident_.status)

    def _notify_new_fire_alert(self, incident_, new_alerts_f, new_alerts_r, uuid_, experimental_recreate):
        """
        Notify about new firing alerts added to the incident
        """
        header = self.app.format_text_italic(
            self.app.header_template.form_message(incident_.last_state, incident_)
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
        self.app.post_thread(incident_.channel_id, incident_.ts, message)
        if new_alerts_f:
            logger.info(f"Incident {uuid_} updated with new alerts firing")
        elif new_alerts_r:
            logger.info(f"Incident {uuid_} updated with some alerts resolved")

    def _new_alerts_recreate_chain(self, alert_state, incident_, uuid_):
        """
        EXPERIMENTAL: release incident and recreate chain by new firing alerts
        """
        self.queue.delete_by_id(incident_.uuid, delete_steps=True, delete_status=False)
        _, chain_name = self.route.get_route(alert_state)
        chain = self.app.chains.get(chain_name)
        incident_.recreate_chain(chain)
        self.queue.recreate(incident_.status, incident_.uuid, incident_.chain)
        incident_.dump()
        logger.info(f"Incident {uuid_} chain recreated")

    def _create_thread(self, incident_, alert_state):
        body = self.app.body_template.form_message(alert_state, incident_)
        header = self.app.header_template.form_message(alert_state, incident_)
        status_icons = self.app.status_icons_template.form_message(alert_state, incident_)
        thread_id = self.app.create_thread(
            incident_.channel_id, body, header, status_icons, status=alert_state['status']
        )
        incident_.set_thread(thread_id, self.app.public_url)
        return thread_id
