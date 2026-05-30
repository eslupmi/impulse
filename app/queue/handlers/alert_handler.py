from datetime import datetime, timezone
from typing import TYPE_CHECKING
from app.config.config import get_config
from app.modules import dispatch_hook, incident_hook_payload
from app.im.template import update_alerts
from app.incident.incident import IncidentConfig, Incident
from app.jinja_template import JinjaTemplate
from app.logging import logger
from app.queue.constants import QueueItemType
from app.queue.handlers.base_handler import BaseHandler
from app.time import unix_sleep_to_timedelta

if TYPE_CHECKING:
    from app.queue.queue import AsyncQueue
    from app.im.application import Application
    from app.incident.incidents import Incidents
    from app.route.route import Route
    from app.inhibition.manager import InhibitionManager

class AlertHandler(BaseHandler):
    """
    AlertHandler class is responsible for handling the alert event.

    :param queue: AsyncQueue instance
    :param application: Application instance
    :param incidents: Incidents instance
    :param route: Route instance
    :param inhibition_manager: InhibitionManager instance for inhibition rule handling
    """
    __slots__ = ['route', 'inhibition_manager']

    def __init__(self, queue: 'AsyncQueue', application: 'Application', incidents: 'Incidents', route: 'Route', inhibition_manager: 'InhibitionManager'):
        super().__init__(queue, application, incidents)
        self.route = route
        self.inhibition_manager = inhibition_manager

    async def handle(self, alert_state):
        incident_ = self.incidents.get(alert=alert_state)
        if incident_ is None:
            await self._handle_create(alert_state)
        else:
            await self._handle_update(incident_.uuid, incident_, alert_state)

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
            chain=[],
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

        will_be_inhibited = self.inhibition_manager.would_be_inhibited(incident_)
        if will_be_inhibited:
            incident_.frozen_by_inhibition = True

        thread_id = await self._create_thread(incident_)
        if thread_id is None:
            logger.warning(
                "Incident creation aborted: failed to create thread",
                extra={'channel_id': incident_.channel_id, 'messenger': self.app.type.value},
            )
            return

        self.incidents.add(incident_)
        await self.inhibition_manager.process_incident(incident_)
        incident_.dump()

        dispatch_hook("incident.created", incident_hook_payload(incident_.uniq_id))

        if will_be_inhibited:
            logger.info("Incident created (inhibited)", extra={'uuid': incident_.uuid, 'link': incident_.link})
        else:
            logger.info("Incident created", extra={'uuid': incident_.uuid, 'link': incident_.link})

        await self.queue.put(status_update_datetime, QueueItemType.UPDATE_STATUS, incident_.uniq_id)

        incident_.generate_chain(self.app.chains, chain_name)
        # Don't schedule chain steps if incident is inhibited
        if not will_be_inhibited:
            await self.queue.recreate(status, incident_.uniq_id, incident_.chain, incident_.chain_active_seconds)

    async def _handle_update(self, uuid_, incident_, alert_state):
        config = get_config()

        if incident_.is_frozen() and incident_.status in ['closed', 'deleted']:
            logger.debug("Ignoring alert for frozen incident", extra={'uuid': uuid_})
            return

        prev_status = incident_.status
        self._regenerate_chain_if_needed(incident_, alert_state, prev_status)
        await self.queue.recreate(alert_state.get('status'), incident_.uniq_id, incident_.get_chain(), incident_.chain_active_seconds)

        is_new_firing_alerts_added, is_some_firing_alerts_removed = self._check_alert_changes(config, incident_, alert_state)
        previous_firing_start_datetime = incident_.updated
        is_status_updated, is_state_updated = incident_.update_state(alert_state)
        if is_status_updated and incident_.status == 'resolved':
            incident_.accumulate_chain_time(previous_firing_start_datetime)

        await self._handle_inhibition_state_change(incident_, prev_status)

        if is_status_updated:
            dispatch_hook("incident.status_changed", incident_hook_payload(incident_.uniq_id))

        if is_state_updated:
            dispatch_hook("incident.alert_changed", incident_hook_payload(incident_.uniq_id))

        if is_state_updated or is_status_updated:
            await self.app.update(
                incident_, alert_state['status'], alert_state, is_status_updated,
                incident_.chain_enabled, incident_.frozen_until, incident_.task_link
            )

        should_notify = prev_status == 'firing' and incident_.status == 'firing' and not incident_.is_frozen()
        if should_notify and (is_new_firing_alerts_added or is_some_firing_alerts_removed):
            await self._notify_new_fire_alert(incident_, is_new_firing_alerts_added, is_some_firing_alerts_removed, uuid_)
        await self.queue.update(incident_.uniq_id, incident_.status_update_datetime, incident_.status)

    ### PRIVATE METHODS ###

    def _regenerate_chain_if_needed(self, incident_, alert_state, prev_status):
        """Generate chain from scratch if incident chain is empty and was resolved."""
        if prev_status == 'resolved' and incident_.chain_enabled and incident_.chain == []:
            _, chain_name = self.route.get_route(alert_state)
            incident_.generate_chain(self.app.chains, chain_name)

    @staticmethod
    def _check_alert_changes(config, incident_, alert_state):
        """Check if new alerts are firing or some alerts resolved."""
        is_new_firing = config.incident.notifications.new_firing and incident_.is_new_firing_alerts_added(alert_state)
        is_some_resolved = config.incident.notifications.partial_resolved and incident_.is_some_firing_alerts_removed(alert_state)
        return is_new_firing, is_some_resolved

    async def _handle_inhibition_state_change(self, incident_, prev_status):
        """Handle inhibition manager updates based on status change."""
        if incident_.status == 'resolved':
            await self.inhibition_manager.handle_resolved(incident_)
        elif incident_.status == 'firing' and prev_status != 'firing':
            await self.inhibition_manager.process_incident(incident_)

    async def _notify_new_fire_alert(self, incident_, new_alerts_f, new_alerts_r, uuid_):
        """
        Notify about new firing alerts added to the incident
        """
        header = self.app.header_template.form_message(incident_.payload, incident_)
        fields = {
            'type': self.app.type,
            'firing': new_alerts_f,
            'resolved': new_alerts_r
        }
        text = JinjaTemplate(update_alerts).form_notification(fields)
        if self.app.type == 'telegram':
            message = text
        else:
            message = header + '\n' + text
        await self.app.post_to_thread(incident_.channel_id, incident_.ts, message)
        if new_alerts_f:
            logger.info("Incident updated with new alerts firing", extra={'uuid': uuid_})
        elif new_alerts_r:
            logger.info("Incident updated with some alerts resolved", extra={'uuid': uuid_})

    async def _create_thread(self, incident_):
        body, header, status_icons = self.app.form_body_header_status_icons(incident_)
        thread_id = await self.app.create_incident_message(incident_, body, header, status_icons)
        if not thread_id or thread_id == 'None/None':
            return None
        incident_.ts = thread_id
        incident_.link = incident_.generate_link(self.app.public_url)
        return thread_id
