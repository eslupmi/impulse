from copy import deepcopy
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from app.config.config import get_config
from app.config.validation import MessengerType
from app.im.template import (
    incident_notifications_new_firing,
    incident_notifications_partial_resolved,
)
from app.incident.incident import Incident, IncidentConfig
from app.jinja_template import JinjaTemplate
from app.logging import logger
from app.queue.constants import QueueItemType
from app.queue.handlers.base_handler import BaseHandler
from app.time import unix_sleep_to_timedelta

if TYPE_CHECKING:
    from app.im.application import Application
    from app.incident.incidents import Incidents
    from app.inhibition.manager import InhibitionManager
    from app.maintenance.manager import MaintenanceManager
    from app.queue.queue import AsyncQueue
    from app.route.route import Route

class AlertHandler(BaseHandler):
    """
    AlertHandler class is responsible for handling the alert event.

    :param queue: AsyncQueue instance
    :param application: Application instance
    :param incidents: Incidents instance
    :param route: Route instance
    :param inhibition_manager: InhibitionManager instance for inhibition rule handling
    :param maintenance_manager: MaintenanceManager instance for time-bounded maintenance windows
    """
    __slots__ = ['inhibition_manager', 'maintenance_manager', 'route']

    def __init__(self, queue: 'AsyncQueue', application: 'Application', incidents: 'Incidents', route: 'Route',
                 inhibition_manager: 'InhibitionManager', maintenance_manager: 'MaintenanceManager'):
        super().__init__(queue, application, incidents)
        self.route = route
        self.inhibition_manager = inhibition_manager
        self.maintenance_manager = maintenance_manager

    async def handle(self, alert_state):
        incident_ = self.incidents.get(alert=alert_state)
        if incident_ is None:
            await self._handle_create(alert_state)
        else:
            await self._handle_update(incident_, alert_state)

    async def _handle_create(self, alert_state):
        config = get_config()

        channel_name, chain_name = self.route.get_route(alert_state)
        channel = self.app.channels[channel_name]

        status = alert_state['status']
        updated_datetime = datetime.now(timezone.utc)
        timeout_value = config.incident.timeouts.get(status)
        status_update_datetime = datetime.now(timezone.utc) + unix_sleep_to_timedelta(timeout_value)

        incident_config = IncidentConfig(
            application_type=self.app.type,
            application_url=self.app.url,
            application_team=self.app.team
        )
        incident_ = Incident(
            payload=alert_state,
            status=status,
            channel_id=channel['id'],
            config=incident_config,
            chain_steps=[],
            chain_enabled=True,
            status_enabled=True,
            updated=updated_datetime,
            status_update_datetime=status_update_datetime,
            assigned_user_id="",
            assigned_user="",
            assigned_fullname="",
            messenger_type=self.app.type.value,
            version=config.INCIDENT_ACTUAL_VERSION
        )

        will_match_maintenance = self.maintenance_manager.would_match_active_window(incident_)
        will_be_inhibited = self.inhibition_manager.would_be_inhibited(incident_)

        thread_id = await self._create_thread(incident_)
        if thread_id is None:
            logger.warning(
                "Incident creation aborted: failed to create thread",
                extra={'channel_id': incident_.channel_id, 'messenger': self.app.type.value},
            )
            return

        self.incidents.add(incident_)
        await self.inhibition_manager.process_incident(incident_)
        await self.maintenance_manager.process_incident(incident_)
        incident_.dump()

        if will_match_maintenance:
            logger.info("Incident created (maintenance)", extra={'uniq_id': incident_.uniq_id, 'link': incident_.link})
        elif will_be_inhibited:
            logger.info("Incident created (inhibited)", extra={'uniq_id': incident_.uniq_id, 'link': incident_.link})
        else:
            logger.info("Incident created", extra={'uniq_id': incident_.uniq_id, 'link': incident_.link})

        await self.queue.put(status_update_datetime, QueueItemType.UPDATE_STATUS, incident_.uniq_id)

        incident_.generate_chain(self.app.chains, chain_name)
        if not (will_be_inhibited or will_match_maintenance):
            await self.queue.recreate(status, incident_.uniq_id, incident_.chain_steps, incident_.chain_active_seconds)

    async def _handle_update(self, incident_, alert_state):
        config = get_config()

        if incident_.is_frozen and incident_.status in ['closed', 'deleted']:
            logger.debug("Ignoring alert for frozen incident", extra={'uniq_id': incident_.uniq_id})
            return

        prev_status = incident_.status
        previous_payload = deepcopy(incident_.payload)
        self._regenerate_chain_if_needed(incident_, alert_state, prev_status)
        await self.queue.recreate(alert_state.get('status'), incident_.uniq_id, incident_.get_chain(), incident_.chain_active_seconds)

        is_new_firing_alerts_added, is_some_firing_alerts_removed = self._check_alert_changes(config, incident_, alert_state)
        previous_firing_start_datetime = incident_.updated
        is_status_updated, is_state_updated = incident_.update_state(alert_state)
        if is_status_updated and incident_.status == 'resolved':
            incident_.accumulate_chain_time(previous_firing_start_datetime)

        await self._handle_inhibition_state_change(incident_, prev_status)

        if is_state_updated or is_status_updated:
            await self.app.update(
                incident_, alert_state['status'], alert_state, is_status_updated,
                incident_.chain_enabled, incident_.frozen_until, incident_.task_link,
                previous_payload=previous_payload,
            )

        should_notify = prev_status == 'firing' and incident_.status == 'firing' and not incident_.is_frozen
        if should_notify and is_new_firing_alerts_added:
            await self._notify_alert_change(
                incident_, incident_notifications_new_firing, 'new alerts firing',
                alert_state, previous_payload,
            )
        if should_notify and is_some_firing_alerts_removed:
            await self._notify_alert_change(
                incident_, incident_notifications_partial_resolved, 'some alerts resolved',
                alert_state, previous_payload,
            )
        await self.queue.update(incident_.uniq_id, incident_.status_update_datetime, incident_.status)

    ### PRIVATE METHODS ###

    def _regenerate_chain_if_needed(self, incident_, alert_state, prev_status):
        """Generate chain from scratch if incident chain is empty and was resolved."""
        if prev_status == 'resolved' and incident_.chain_enabled and incident_.chain_steps == []:
            _, chain_name = self.route.get_route(alert_state)
            incident_.generate_chain(self.app.chains, chain_name)

    @staticmethod
    def _check_alert_changes(config, incident_, alert_state):
        """Check if new alerts are firing or some alerts resolved."""
        is_new_firing = config.incident.notifications.new_firing and incident_.is_new_firing_alerts_added(alert_state)
        is_some_resolved = config.incident.notifications.partial_resolved and incident_.is_some_firing_alerts_removed(alert_state)
        return is_new_firing, is_some_resolved

    async def _handle_inhibition_state_change(self, incident_, prev_status):
        """Handle inhibition and maintenance manager updates based on status change."""
        if incident_.status == 'resolved':
            await self.inhibition_manager.handle_resolved(incident_)
        elif incident_.status == 'firing' and prev_status != 'firing':
            await self.inhibition_manager.process_incident(incident_)
            await self.maintenance_manager.process_incident(incident_)

    async def _notify_alert_change(self, incident_, templates, log_message, payload, previous_payload):
        header = self.app.header_template.form_message(incident_.payload, incident_)
        text = JinjaTemplate(templates[self.app.type.value]).form_notification(
            payload=payload,
            previous_payload=previous_payload,
            incident=incident_.serialize(),
        )
        if self.app.type == MessengerType.TELEGRAM:
            message = text
        else:
            message = header + '\n' + text
        await self.app.post_to_thread(incident_.channel_id, incident_.ts, message)
        logger.info(f'Incident updated with {log_message}', extra={'uniq_id': incident_.uniq_id})

    async def _create_thread(self, incident_):
        body, header, status_icons = self.app.form_body_header_status_icons(incident_)
        thread_id = await self.app.create_incident_message(incident_, body, header, status_icons)
        if not thread_id or thread_id == 'None/None':
            return None
        incident_.ts = thread_id
        incident_.link = incident_.generate_link(self.app.public_url)
        return thread_id
