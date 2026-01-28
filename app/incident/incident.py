import json
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Dict, Optional

import yaml

from app.config.config import get_config
from app.config.environment import get_environment_config
from app.config.validation import MessengerType
from app.im.channel_manager import ChannelManager
from app.logging import logger
from app.time import unix_sleep_to_timedelta
from app.tools import NoAliasDumper
from app.ui.websocket import incident_ws
from app.utils import get_attr_by_key_chain, normalize_param, filter_dict_keys


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
    frozen_by_inhibition: bool = False
    childs: List[str] = field(default_factory=list)  # Target incident uniq_ids that this incident inhibits
    parents: List[str] = field(default_factory=list)  # Source incident uniq_ids that inhibit this incident

    next_status = {
        'firing': 'unknown',
        'unknown': 'closed',
        'resolved': 'closed',
        'closed': 'deleted'
    }

    @staticmethod
    def gen_uuid(group_labels: Dict) -> str:
        return str(uuid.uuid5(uuid.NAMESPACE_OID, json.dumps(group_labels)))

    @staticmethod
    def gen_uniq_id(group_labels: Dict, datetime_: datetime) -> str:
        return str(uuid.uuid5(
            uuid.NAMESPACE_OID,
            json.dumps({'group_labels': group_labels, 'datetime': datetime_.isoformat()})
        ))

    def __post_init__(self):
        if not self.created:
            self.created = datetime.now(timezone.utc)
        self.uuid = self.gen_uuid(self.payload.get('groupLabels'))
        if not self.uniq_id:
            self.uniq_id = self.gen_uniq_id(self.payload.get('groupLabels'), self.created)

    def set_thread(self, thread_id: str, public_url: str):
        self.ts = thread_id
        self.link = self.generate_link(public_url)

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

        if chain_name not in chains.keys():
            logger.warning("Chain not found", extra={'chain': chain_name})
            return

        chain = chains[chain_name]
        if chain is None:
            logger.warning("Chain is None. Check configuration", extra={'chain': chain_name})
            return
            
        try:
            steps = chain.steps
        except AttributeError:
            logger.error(f'Chain {chain_name} does not have steps attribute')
            return
            
        if not steps:
            logger.debug("Chain has no steps", extra={'chain': chain_name})
            return

        steps = self._unchain(chains, steps)

        dt = datetime.now(timezone.utc)
        for index, step in enumerate(steps):
            type_, value = self._get_step_type_and_value(step)
            if type_ == 'wait':
                dt += unix_sleep_to_timedelta(value)
            else:
                self.chain_put(index=index, datetime_=dt, type_=type_, identifier=value)
        self.dump()

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

    def _get_step_type_and_value(self, step):
        """Extract step type and value from either SimpleChainStep object or dictionary"""
        if hasattr(step, 'get_type_and_value'):
            return step.get_type_and_value()
        elif isinstance(step, dict):
            return next(iter(step.items()))
        else:
            raise ValueError(f"Unknown step format: {step}")

    def _step_has_chain(self, step):
        """Check if step has a chain reference"""
        if hasattr(step, 'has_chain'):
            return step.has_chain()
        elif isinstance(step, dict):
            return 'chain' in step
        return False

    def release(self):
        self.chain = []
        self.assign_user_id("")
        self.assign_user("")
        self.assign_fullname("")
        self.chain_enabled = True
        self.dump()

    def freeze(self, until: datetime, user_id: str, user_fullname: str = ''):
        """Freeze the incident until the specified datetime (preserves underlying status)
        Assigns the user who froze the incident and disables chains"""
        self.frozen_until = until
        self.assigned_user_id = user_id
        if user_fullname:
            self.assigned_fullname = user_fullname
        self.chain_enabled = False
        self.dump()
        logger.info("Incident frozen", extra={'uuid': self.uuid, 'frozen_until': until})

    def unfreeze(self):
        """Unfreeze the incident from all freeze types (time-based and inhibition)"""
        self.frozen_until = None
        self.frozen_by_inhibition = False
        self.chain_enabled = False
        logger.info("Incident unfrozen", extra={'uuid': self.uuid})
        self.dump()

    def freeze_by_inhibition(self):
        """Freeze the incident due to inhibition (no assignee, no expiration time)"""
        self.frozen_by_inhibition = True
        self.chain_enabled = False
        self.dump()
        logger.info("Incident frozen by inhibition", extra={'uuid': self.uuid})

    def is_frozen(self) -> bool:
        """Check if the incident is currently frozen (by time-based freeze or inhibition)"""
        return self.frozen_by_inhibition or self.frozen_until is not None

    def get_chain(self) -> List[Dict]:
        if not self.chain_enabled:
            return []
        return self.chain

    def chain_put(self, index: int, datetime_: datetime, type_: str, identifier: str):
        self.chain.insert(index, {
            'datetime': datetime_,
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
            frozen_by_inhibition=content.get('frozen_by_inhibition', False),
            childs=content.get('childs', []),
            parents=content.get('parents', []),
        )
        incident_.set_thread(content.get('ts'), incident_config.application_url)
        incident_.task_link = content.get('task_link', '')
        return incident_

    def get_current_filename(self) -> str:
        """Get the current filename based on incident state"""
        env_config = get_environment_config()
        if self.status == 'closed' or self.status == 'deleted':
            closed_str = self.datetime_serialize(self.closed)
            return f'{env_config.incidents_path}/{self.uuid}__{closed_str}.yml'
        else:
            return f'{env_config.incidents_path}/{self.uuid}.yml'

    def _remove_old_file(self, old_filename: str):
        """Remove old incident file"""
        try:
            if os.path.exists(old_filename):
                os.remove(old_filename)
                logger.debug("Removed incident file", extra={'file': old_filename})
        except OSError as e:
            logger.error("Failed to remove incident file", extra={'file': old_filename, 'error': str(e)})

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
            "frozen_by_inhibition": self.frozen_by_inhibition,
            "childs": self.childs,
            "parents": self.parents,
        }
        try:
            incident_filename = self.get_current_filename()
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
            "frozen_by_inhibition": self.frozen_by_inhibition,
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
            '_responsive_data': {
                'group_labels': group_labels,
                'common_labels': filter_dict_keys(common_labels, group_labels),
                'common_annotations': common_annotations,
                'incident_info': {
                    'status': self.status,
                    'frozen_until': normalize_param(self.frozen_until) if self.frozen_until else None,
                    'is_frozen': self.is_frozen(),
                    'created': normalize_param(self.created) if self.created else None,
                    'updated': normalize_param(self.updated) if self.updated else None,
                    'assigned_fullname': self.assigned_fullname if self.assigned_fullname else None,
                    'channel_name': ChannelManager().get_channel_name_by_id(self.channel_id),
                    'link': self.link,
                    'task_link': self.task_link,
                    'chain_enabled': self.chain_enabled,
                    'has_chain': len(self.chain) > 0 if self.chain else False
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
        self.updated = now
        if status != 'deleted':
            config = get_config()
            timeout_value = config.incident.timeouts.get(status)
            self.status_update_datetime = now + unix_sleep_to_timedelta(timeout_value)
        if self.status != status:
            old_filename = self.get_current_filename()
            self.set_status(status)
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

    def set_status(self, status: str):
        self.status = status
        logger.debug("Status updated", extra={'uuid': self.uuid, 'status': status})
        if status == 'closed' and not self.closed:
            self.closed = datetime.now(timezone.utc)

    def assign_user_id(self, user_id: str):
        self.assigned_user_id = user_id

    def assign_user(self, user: str):
        self.assigned_user = user

    def assign_fullname(self, fullname: str):
        self.assigned_fullname = fullname

    def is_new_firing_alerts_added(self, alert_state: Dict) -> bool:
        old_alerts_labels = self._get_firing_alerts_labels(self.payload)
        new_alerts_labels = self._get_firing_alerts_labels(alert_state)
        return any(label not in old_alerts_labels for label in new_alerts_labels)

    def is_some_firing_alerts_removed(self, alert_state: Dict) -> bool:
        old_alerts_labels = self._get_firing_alerts_labels(self.payload)
        new_alerts_labels = self._get_firing_alerts_labels(alert_state)
        return any(label not in new_alerts_labels for label in old_alerts_labels)

    @staticmethod
    def _get_firing_alerts_labels(alert_state):
        return [a.get('labels') for a in alert_state['alerts'] if a['status'] == 'firing']

    @staticmethod
    def datetime_serialize(datetime_: Optional[datetime]) -> str:
        if datetime_ is None:
            return ''
        return datetime_.strftime('%Y_%m_%d__%H_%M_%S')
