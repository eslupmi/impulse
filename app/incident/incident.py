import asyncio
import json
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Dict, Optional, TYPE_CHECKING

import yaml

from app.config.config import get_config
from app.config.environment import get_environment_config
from app.config.validation import MessengerType
from app.im.channel_manager import ChannelManager
from app.im.chain.ui_chains_store import ui_chains_store
from app.incident.freeze import FreezeSource, MAINTENANCE_PARENT_SENTINEL
from app.logging import logger
from app.queue.constants import QueueItemType
from app.time import unix_sleep_to_timedelta
from app.tools import NoAliasDumper
from app.ui.websocket import incident_ws
from app.utils import get_attr_by_key_chain, normalize_param, filter_dict_keys

if TYPE_CHECKING:
    from app.im.application import Application
    from app.queue.queue import AsyncQueue


@dataclass
class IncidentConfig:
    application_type: str
    application_url: str
    application_team: str


@dataclass
class Incident:
    payload: Dict
    status: str
    channel_id: str
    config: IncidentConfig
    status_update_datetime: datetime
    assigned_user_id: str
    assigned_user: str
    assigned_fullname: str
    messenger_type: str
    chain: List[Dict] = field(default_factory=list)
    chain_enabled: bool = False
    status_enabled: bool = False
    updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    created: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    version: str = get_config().INCIDENT_ACTUAL_VERSION
    uniq_id: str = field(default=None)
    uuid: str = field(init=False)
    ts: str = field(default='')
    link: str = field(default='')
    task_link: str = field(default='')
    task_creation_in_progress: bool = False
    closed: Optional[datetime] = field(default=None)
    frozen_until: Optional[datetime] = field(default=None)
    frozen_until_source: Optional[str] = field(default=None)
    chain_active_seconds: float = 0.0
    childs: List[str] = field(default_factory=list)  # Target incident uniq_ids that this incident inhibits
    parents: List[str] = field(default_factory=list)  # Source incident uniq_ids that inhibit this incident

    next_status = {
        'firing': 'unknown',
        'unknown': 'closed',
        'resolved': 'closed',
        'closed': 'deleted'
    }

    def __post_init__(self):
        if not self.created:
            self.created = datetime.now(timezone.utc)
        self.uuid = self.gen_uuid(self.payload.get('groupLabels'))
        if not self.uniq_id:
            self.uniq_id = self.gen_uniq_id(self.payload.get('groupLabels'), self.created)

    @property
    def frozen_by_maintenance(self) -> bool:
        return MAINTENANCE_PARENT_SENTINEL in self.parents

    @property
    def frozen_by_inhibition(self) -> bool:
        return any(parent != MAINTENANCE_PARENT_SENTINEL for parent in self.parents)

    def generate_link(self, public_url) -> str:
        if self.config.application_type == MessengerType.SLACK:
            return f'{public_url}' + f'archives/{self.channel_id}/p{self.ts.replace(".", "")}'
        elif self.config.application_type == MessengerType.MATTERMOST:
            return f'{self.config.application_url}/{self.config.application_team.lower()}/pl/{self.ts}'
        elif self.config.application_type == MessengerType.TELEGRAM:
            return f'https://t.me/c/{str(self.channel_id)[4:]}/{self.ts}'
        return ''

    def generate_chain(self, chains, chain_name=None):
        if chain_name is None:
            return

        chain = chains.get(chain_name)
        steps = None
        if chain is not None:
            try:
                steps = chain.steps
            except AttributeError:
                logger.error(f'Chain {chain_name} does not have steps attribute')
                return
        else:
            chain_config = get_config().messenger.chains.get(chain_name) if get_config().messenger.chains else None
            if isinstance(chain_config, dict) and chain_config.get("type") == "ui":
                steps = ui_chains_store.get_steps_for_now(chain_name)
            else:
                logger.warning("Chain not found", extra={'chain': chain_name})
                return
            
        if not steps:
            logger.debug("Chain has no steps", extra={'chain': chain_name})
            return

        steps = self._unchain(chains, steps)

        cumulative_delay = 0.0
        for index, step in enumerate(steps):
            type_, value = self._get_step_type_and_value(step)
            if type_ == 'wait':
                cumulative_delay += unix_sleep_to_timedelta(value).total_seconds()
            else:
                self.chain_put(index=index, delay=cumulative_delay, type_=type_, identifier=value)
        self.chain_active_seconds = 0.0
        self.dump()

    def release(self):
        self.chain = []
        self.chain_active_seconds = 0.0
        self.assigned_user_id = ""
        self.assigned_user = ""
        self.assigned_fullname = ""
        self.chain_enabled = True
        self.dump()

    def freeze(self, until: datetime, user, source: FreezeSource):
        """Freeze the incident until the specified datetime (preserves underlying status)
        Assigns the user who froze the incident (when provided) and disables chains.
        When user is None (auto-freeze sources like maintenance) assignee fields are kept."""
        self.accumulate_chain_time(self.updated)
        self.frozen_until = until
        self.frozen_until_source = source.value
        if user is not None:
            self.assigned_user_id = user.id
            self.assigned_user = user.username
            self.assigned_fullname = user.name
        self.chain_enabled = False
        self.dump()
        logger.info("Incident frozen", extra={'uuid': self.uuid, 'frozen_until': until})

    def unfreeze(self):
        """Clear all freeze sources."""
        self.frozen_until = None
        self.frozen_until_source = None
        self.parents = []
        self.dump()
        logger.info("Incident unfrozen", extra={'uuid': self.uuid})

    def clear_time_freeze(self):
        """Clear only time-based freeze state, preserving parent-based freezes."""
        self.frozen_until = None
        self.frozen_until_source = None
        self.dump()
        logger.info("Incident time freeze cleared", extra={'uuid': self.uuid})

    def remove_freeze_parent(self, parent: str):
        if parent in self.parents:
            self.parents.remove(parent)
            self.dump()
            logger.info("Incident freeze parent removed", extra={'uuid': self.uuid, 'parent': parent})

    def set_maintenance_parent(self):
        if MAINTENANCE_PARENT_SENTINEL not in self.parents:
            self.parents.append(MAINTENANCE_PARENT_SENTINEL)
        self.dump()

    def freeze_by_inhibition(self):
        """Sync inhibition freeze side effects after caller records source uniq_id in parents."""
        self.accumulate_chain_time(self.updated)
        self.dump()
        logger.info("Incident frozen by inhibition", extra={'uuid': self.uuid})

    def is_frozen(self) -> bool:
        return self.frozen_until is not None or len(self.parents) > 0

    def can_manual_unfreeze(self) -> bool:
        return (
            self.frozen_until is not None
            and self.frozen_until_source == FreezeSource.TIME.value
            and len(self.parents) == 0
        )

    def accumulate_chain_time(self, updated):
        """Accumulate chain active time from self.updated until now. Updates self.updated.
        Must be called before any state change that affects chain activity."""
        now = datetime.now(timezone.utc)
        delta = (now - updated).total_seconds()
        if delta > 0:
            self.chain_active_seconds += delta

    def get_chain(self) -> List[Dict]:
        if not self.chain_enabled:
            return []
        return self.chain

    def chain_put(self, index: int, delay: float, type_: str, identifier: str):
        self.chain.insert(index, {
            'delay': delay,
            'type': type_,
            'identifier': identifier,
            'done': False,
            'result': None
        })

    def chain_update(self, index: int, done: bool, result: Optional[str]):
        self.chain[index]['done'] = done
        self.chain[index]['result'] = result
        self.dump()

    @classmethod
    def load(cls, dump_file: str, incident_config: IncidentConfig):
        config = get_config()
        with open(dump_file, 'r') as f:
            content = yaml.load(f, Loader=yaml.CLoader)
        incident_ = cls(
            payload=content.get('payload'),
            status=content.get('status'),
            channel_id=content.get('channel_id'),
            config=incident_config,
            chain=content.get('chain', []),
            chain_enabled=content.get('chain_enabled', False),
            closed=content.get('closed', None),
            status_enabled=content.get('status_enabled', False),
            status_update_datetime=content.get('status_update_datetime'),
            updated=content.get('updated'),
            created=content.get('created'),
            assigned_user_id=content.get('assigned_user_id', ''),
            assigned_user=content.get('assigned_user', ''),
            assigned_fullname=content.get('assigned_fullname', ''),
            messenger_type=content.get('messenger_type', ''),
            uniq_id=content.get('uniq_id', ''),
            version=content.get('version', config.INCIDENT_ACTUAL_VERSION),
            frozen_until=content.get('frozen_until', None),
            frozen_until_source=content.get('frozen_until_source', None),
            chain_active_seconds=content.get('chain_active_seconds', 0.0),
            childs=content.get('childs', []),
            parents=content.get('parents', []),
        )
        incident_.ts = content.get('ts')
        incident_.link = incident_.generate_link(incident_config.application_url)
        incident_.task_link = content.get('task_link', '')
        return incident_

    def get_current_filename(self) -> str:
        """Get the current filename based on incident state"""
        env_config = get_environment_config()
        if self.status == 'closed' or self.status == 'deleted':
            closed_str = self._datetime_serialize(self.closed)
            return f'{env_config.incidents_path}/{self.uuid}__{closed_str}.yml'
        else:
            return f'{env_config.incidents_path}/{self.uuid}.yml'

    def dump(self):
        data = {
            "chain_enabled": self.chain_enabled,
            "chain": self.chain,
            "channel_id": self.channel_id,
            "closed": self.closed,
            "payload": self.payload,
            "status_enabled": self.status_enabled,
            "status_update_datetime": self.status_update_datetime,
            "status": self.status,
            "ts": self.ts,
            "updated": self.updated,
            "created": self.created,
            "assigned_user_id": self.assigned_user_id,
            "assigned_user": self.assigned_user,
            "assigned_fullname": self.assigned_fullname,
            "messenger_type": self.messenger_type,
            "uniq_id": self.uniq_id,
            "version": self.version,
            "task_link": self.task_link,
            "frozen_until": self.frozen_until,
            "frozen_until_source": self.frozen_until_source,
            "chain_active_seconds": self.chain_active_seconds,
            "childs": self.childs,
            "parents": self.parents,
        }
        incident_filename = self.get_current_filename()
        try:
            with open(incident_filename, 'w') as f:
                yaml.dump(data, f, NoAliasDumper, default_flow_style=False)
        except OSError as e:
            logger.error("Failed to write incident file", extra={'file': incident_filename, 'error': str(e)})
        # Schedule async websocket update
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(incident_ws.update_row(self))
        except RuntimeError:
            # No event loop running, skip websocket update
            pass

    def serialize(self) -> Dict:
        return {
            "chain_enabled": self.chain_enabled,
            "chain": self.chain,
            "channel_id": self.channel_id,
            "channel_name": ChannelManager().get_channel_name_by_id(self.channel_id),
            "closed": self.closed,
            "payload": self.payload,
            "status_enabled": self.status_enabled,
            "status_update_datetime": self.status_update_datetime,
            "status": self.status,
            "updated": self.updated,
            "created": self.created,
            "assigned_user_id": self.assigned_user_id,
            "assigned_user": self.assigned_user,
            "assigned_fullname": self.assigned_fullname,
            "messenger_type": self.messenger_type,
            "link": self.link,
            "ts": self.ts,
            "task_link": self.task_link,
            "uuid": self.uuid,
            "uniq_id": self.uniq_id,
            "frozen_until": self.frozen_until,
            "frozen_until_source": self.frozen_until_source,
            "is_frozen": self.is_frozen(),
            "frozen_by_inhibition": self.frozen_by_inhibition,
            "frozen_by_maintenance": self.frozen_by_maintenance,
            "chain_active_seconds": self.chain_active_seconds,
            "childs": self.childs,
            "parents": self.parents,
        }

    def get_table_data(self, params) -> Dict:
        alerts = self.payload.get('alerts', [])
        if len(alerts) > 1:
            group_labels = self.payload.get('groupLabels', {})
            common_labels = self.payload.get('commonLabels', {})
            common_annotations = self.payload.get('commonAnnotations', {})
        else:
            group_labels = {}
            common_labels = {}
            common_annotations = {}
        
        display_status = 'frozen' if self.is_frozen() else self.status
        
        data = {
            'uniq_id': self.uniq_id,
            'indicator': display_status,
            '_alerts_count': len(self.payload.get('alerts', [])),
            '_is_frozen': self.is_frozen(),
            '_action_state': f"{self.is_frozen()}|{self.status}|{self.assigned_user_id or ''}|{bool(self.task_link)}|{self.frozen_by_inhibition}|{self.frozen_by_maintenance}",
            '_assigned_user_id': self.assigned_user_id or '',
            '_assigned_fullname': self.assigned_fullname or '',
            '_responsive_data': {
                'group_labels': group_labels,
                'common_labels': filter_dict_keys(common_labels, group_labels),
                'common_annotations': common_annotations,
                'incident_info': {
                    'status': self.status,
                    'frozen_until': normalize_param(self.frozen_until) if self.frozen_until else None,
                    'frozen_by_inhibition': self.frozen_by_inhibition,
                    'frozen_by_maintenance': self.frozen_by_maintenance,
                    'created': normalize_param(self.created) if self.created else None,
                    'updated': normalize_param(self.updated) if self.updated else None,
                    'assigned_fullname': self.assigned_fullname if self.assigned_fullname else None,
                    'link': self.link,
                    'task_link': self.task_link,
                },
                'alerts': [
                    {
                        'status': alert.get('status', ''),
                        'startsAt': alert.get('startsAt', ''),
                        'endsAt': alert.get('endsAt', ''),
                        'generatorURL': alert.get('generatorURL', ''),
                        'labels': filter_dict_keys(alert.get('labels', {}), common_labels),
                        'annotations': filter_dict_keys(alert.get('annotations', {}), common_annotations)
                    }
                    for alert in alerts
                ]
            }
        }
        data_object = {'incident': self, 'payload': self.payload}
        for key, value in params.items():
            param = get_attr_by_key_chain(data_object, None, *value.split('.'))
            data[key] = normalize_param(param)
        return data

    def update_status(self, status: str) -> bool:
        now = datetime.now(timezone.utc)
        self._schedule_status_change_by_timeout(status, now)
        if self.status != status:
            old_filename = self.get_current_filename()
            self._set_status(status)
            self.updated = now
            self.dump()
            new_filename = self.get_current_filename()
            if old_filename != new_filename:
                self._remove_old_file(old_filename)
            return True
        self.dump()
        return False

    def update_state(self, alert_state: Dict) -> tuple[bool, bool]:
        update_status = self.update_status(alert_state['status'])
        state_updated = self.payload != alert_state
        if state_updated:
            self.payload = alert_state
            self.dump()
        return update_status, state_updated

    def is_new_firing_alerts_added(self, alert_state: Dict) -> bool:
        old_alerts_labels = self._get_firing_alerts_labels(self.payload)
        new_alerts_labels = self._get_firing_alerts_labels(alert_state)
        return any(label not in old_alerts_labels for label in new_alerts_labels)

    def is_some_firing_alerts_removed(self, alert_state: Dict) -> bool:
        old_alerts_labels = self._get_firing_alerts_labels(self.payload)
        new_alerts_labels = self._get_firing_alerts_labels(alert_state)
        return any(label not in new_alerts_labels for label in old_alerts_labels)

    @staticmethod
    def gen_uuid(group_labels: Dict) -> str:
        return str(uuid.uuid5(uuid.NAMESPACE_OID, json.dumps(group_labels)))

    @staticmethod
    def gen_uniq_id(group_labels: Dict, datetime_: datetime) -> str:
        return str(uuid.uuid5(
            uuid.NAMESPACE_OID,
            json.dumps({'group_labels': group_labels, 'datetime': datetime_.isoformat()})
        ))

    ### PRIVATE METHODS ###

    def _set_status(self, status: str):
        self.status = status
        logger.debug("Status updated", extra={'uuid': self.uuid, 'status': status})
        if status == 'closed' and not self.closed:
            self.closed = datetime.now(timezone.utc)

    def _schedule_status_change_by_timeout(self, status, now):
        if status != 'deleted':
            config = get_config()
            timeout_value = config.incident.timeouts.get(status)
            self.status_update_datetime = now + unix_sleep_to_timedelta(timeout_value)

    def _unchain(self, chains, steps):
        if not any(self._step_has_chain(step) for step in steps):
            return steps

        extended_steps = []
        for step in steps:
            type_, value = self._get_step_type_and_value(step)
            if type_ == 'chain':
                nested_chain = chains.get(value)
                if nested_chain is None:
                    logger.warning("Chain not found", extra={'chain': value})
                    continue
                nested_steps = nested_chain.steps
                extended_steps.extend(self._unchain(chains, nested_steps))
            else:
                extended_steps.append({type_: value})
        return extended_steps

    @staticmethod
    def _get_step_type_and_value(step):
        """Extract step type and value from either SimpleChainStep object or dictionary"""
        if hasattr(step, 'get_type_and_value'):
            return step.get_type_and_value()
        elif isinstance(step, dict):
            return next(iter(step.items()))
        else:
            raise ValueError(f"Unknown step format: {step}")

    @staticmethod
    def _step_has_chain(step):
        """Check if step has a chain reference"""
        if hasattr(step, 'has_chain'):
            return step.has_chain()
        elif isinstance(step, dict):
            return 'chain' in step
        return False

    @staticmethod
    def _remove_old_file(old_filename: str):
        """Remove old incident file"""
        try:
            if os.path.exists(old_filename):
                os.remove(old_filename)
                logger.debug("Removed incident file", extra={'file': old_filename})
        except OSError as e:
            logger.error("Failed to remove incident file", extra={'file': old_filename, 'error': str(e)})

    @staticmethod
    def _get_firing_alerts_labels(alert_state):
        return [a.get('labels') for a in alert_state['alerts'] if a['status'] == 'firing']

    @staticmethod
    def _datetime_serialize(datetime_: Optional[datetime]) -> str:
        if datetime_ is None:
            return ''
        return datetime_.strftime('%Y_%m_%d__%H_%M_%S')


async def unfreeze_incident(incident: 'Incident', app: 'Application', queue: 'AsyncQueue'):
    await remove_freeze_source(incident, app, queue, source=FreezeSource.ALL, notify=True)


async def remove_freeze_source(
    incident: 'Incident',
    app: 'Application',
    queue: 'AsyncQueue',
    source: FreezeSource,
    parent: Optional[str] = None,
    notify: bool = False,
):
    if not incident.is_frozen() and source not in (FreezeSource.PARENT, FreezeSource.MAINTENANCE):
        logger.info(f'Incident {incident.uuid} is not frozen, skipping unfreeze')
        return

    incident_status = incident.status
    if source == FreezeSource.TIME:
        incident.clear_time_freeze()
    elif source == FreezeSource.PARENT:
        if parent:
            incident.remove_freeze_parent(parent)
        else:
            incident.dump()
    elif source == FreezeSource.MAINTENANCE:
        if incident.frozen_until_source == FreezeSource.MAINTENANCE.value:
            incident.frozen_until = None
            incident.frozen_until_source = None
        if MAINTENANCE_PARENT_SENTINEL in incident.parents:
            incident.remove_freeze_parent(MAINTENANCE_PARENT_SENTINEL)
        else:
            incident.dump()
    else:
        incident.unfreeze()

    await sync_after_freeze_change(incident, app, queue, incident_status, notify=notify)


async def sync_after_freeze_change(
    incident: 'Incident',
    app: 'Application',
    queue: 'AsyncQueue',
    incident_status: Optional[str] = None,
    notify: bool = False
):
    if incident.is_frozen():
        await queue.delete_by_id(incident.uniq_id, delete_steps=True, delete_status=False)
        return

    if notify:
        app.track_async_task(asyncio.create_task(app.post_unfreeze_notification(incident)))

    incident_status = incident_status or incident.status
    await queue.put_first(datetime.now(timezone.utc), QueueItemType.STATUS_CHECK, incident.uniq_id)
    await queue.recreate(incident.status, incident.uniq_id, incident.get_chain(), incident.chain_active_seconds)
    if incident_status != 'deleted':
        await queue.put(incident.status_update_datetime, QueueItemType.UPDATE_STATUS, incident.uniq_id)


async def restore_after_unfreeze(
    incident: 'Incident',
    app: 'Application',
    queue: 'AsyncQueue',
    incident_status: Optional[str] = None,
    notify: bool = False
):
    await sync_after_freeze_change(incident, app, queue, incident_status, notify)
