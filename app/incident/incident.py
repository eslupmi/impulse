from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Dict, Optional

import yaml

from app.im.colors import status_colors
from app.incident.helpers import gen_uuid
from app.time import unix_sleep_to_timedelta
from app.tools import NoAliasDumper
from app.ui.websocket import incident_ws
from app.utils import get_attr_by_key_chain, normalize_param, filter_dict_keys
from config import incidents_path, incident, INCIDENT_ACTUAL_VERSION
from app.logging import logger


@dataclass
class IncidentConfig:
    application_type: str
    application_url: str
    application_team: str


@dataclass
class Incident:
    last_state: Dict
    status: str
    channel_id: str
    config: IncidentConfig
    status_update_datetime: datetime
    assigned_user_id: str
    assigned_user: str
    created: datetime = None
    chain: List[Dict] = field(default_factory=list)
    chain_enabled: bool = False
    status_enabled: bool = False
    updated: datetime = field(default_factory=datetime.utcnow)
    created: datetime = field(default_factory=datetime.utcnow)
    version: str = INCIDENT_ACTUAL_VERSION
    uuid: str = field(init=False)
    ts: str = field(default='')
    link: str = field(default='')

    next_status = {
        'firing': 'unknown',
        'unknown': 'closed',
        'resolved': 'closed'
    }

    def __post_init__(self):
        self.uuid = gen_uuid(self.last_state.get('groupLabels'))
        if not self.created:
            self.created = datetime.now(timezone.utc)

    def set_thread(self, thread_id: str, public_url: str):
        self.ts = thread_id
        self.link = self.generate_link(public_url)

    def generate_link(self, public_url) -> str:
        if self.config.application_type == 'slack':
            return f'{public_url}' + f'archives/{self.channel_id}/p{self.ts.replace(".", "")}'
        elif self.config.application_type == 'mattermost':
            return f'{self.config.application_url}/{self.config.application_team.lower()}/pl/{self.ts}'
        elif self.config.application_type == 'telegram':
            return f'https://t.me/c/{str(self.channel_id)[4:]}/{self.ts}'
        return ''

    def generate_chain(self, chains, chain_name=None):
        if chain_name is None:
            return

        if chain_name not in chains.keys():
            logger.warning(f'Chain {chain_name} not found. Check impulse.yml')
            return

        chain = chains[chain_name]
        if chain is None:
            logger.warning(f'Chain {chain_name} is None (possibly invalid configuration). Check impulse.yml')
            return
            
        try:
            steps = chain.steps
        except AttributeError:
            logger.error(f'Chain {chain_name} does not have steps attribute')
            return
            
        if not steps:
            logger.debug(f'Chain {chain_name} has no steps for current time/conditions')
            return

        steps = self._unchain(chains, steps)

        dt = datetime.utcnow()
        for index, step in enumerate(steps):
            type_, value = next(iter(step.items()))
            if type_ == 'wait':
                dt += unix_sleep_to_timedelta(value)
            else:
                self.chain_put(index=index, datetime_=dt, type_=type_, identifier=value)
        self.dump()

    def _unchain(self, chains, steps):
        if not any('chain' in step for step in steps):
            return steps

        extended_steps = []
        for step in steps:
            type_, value = next(iter(step.items()))
            if type_ == 'chain':
                nested_chain = chains.get(value)
                if nested_chain is None:
                    logger.warning(f"Chain '{value}' not found. Check impulse.yml")
                    continue
                nested_steps = nested_chain.steps
                extended_steps.extend(self._unchain(chains, nested_steps))
            else:
                extended_steps.append({type_: value})
        return extended_steps

    def release(self):
        self.chain = []
        self.assign_user_id("")
        self.assign_user("")
        self.chain_enabled = True
        self.dump()

    def get_chain(self) -> List[Dict]:
        if not self.chain_enabled:
            return list()
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

    def set_next_status(self):
        new_status = Incident.next_status[self.status]
        return self.update_status(new_status)

    @classmethod
    def load(cls, dump_file: str, config: IncidentConfig):
        with open(dump_file, 'r') as f:
            content = yaml.load(f, Loader=yaml.CLoader)
        incident_ = cls(
            last_state=content.get('last_state'),
            status=content.get('status'),
            channel_id=content.get('channel_id'),
            config=config,
            chain=content.get('chain', []),
            chain_enabled=content.get('chain_enabled', False),
            status_enabled=content.get('status_enabled', False),
            status_update_datetime=content.get('status_update_datetime'),
            updated=content.get('updated'),
            created=content.get('created'),
            assigned_user_id=content.get('assigned_user_id', ''),
            assigned_user=content.get('assigned_user', ''),
            version=content.get('version', INCIDENT_ACTUAL_VERSION)
        )
        incident_.set_thread(content.get('ts'), config.application_url)
        return incident_

    def dump(self):
        data = {
            "chain_enabled": self.chain_enabled,
            "chain": self.chain,
            "channel_id": self.channel_id,
            "last_state": self.last_state,
            "status_enabled": self.status_enabled,
            "status_update_datetime": self.status_update_datetime,
            "status": self.status,
            "ts": self.ts,
            "updated": self.updated,
            "created": self.created,
            "assigned_user_id": self.assigned_user_id,
            "assigned_user": self.assigned_user,
            "version": self.version
        }
        with open(f'{incidents_path}/{self.uuid}.yml', 'w') as f:
            yaml.dump(data, f, NoAliasDumper, default_flow_style=False)
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
            "last_state": self.last_state,
            "status_enabled": self.status_enabled,
            "status_update_datetime": self.status_update_datetime,
            "status": self.status,
            "updated": self.updated,
            "created": self.created,
            "assigned_user_id": self.assigned_user_id,
            "assigned_user": self.assigned_user,
            "link": self.link,
            "ts": self.ts,
        }

    def get_table_data(self, params) -> Dict:
        alerts = self.last_state.get('alerts', [])
        if len(alerts) > 1:
            group_labels = self.last_state.get('groupLabels', {})
            common_labels = self.last_state.get('commonLabels', {})
            common_annotations = self.last_state.get('commonAnnotations', {})
            show_common_block = True
        else:
            group_labels = self.last_state.get('groupLabels', {})
            common_labels = group_labels
            common_annotations = {}
            show_common_block = False
        data = {
            'uuid': str(self.uuid),
            'indicator': status_colors.get(self.status),
            '_alerts_count': len(self.last_state.get('alerts', [])),
            '_responsive_data': {
                'group_labels': group_labels,
                'common_labels': filter_dict_keys(group_labels, common_labels),
                'common_annotations': common_annotations,
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
                ],
                'show_common_block': show_common_block
            }
        }
        data_object = {'incident': self, 'payload': self.last_state}
        for key, value in params.items():
            param = get_attr_by_key_chain(data_object, None, *value.split('.'))
            data[key] = normalize_param(param)
        return data

    def update_status(self, status: str) -> bool:
        now = datetime.utcnow()
        self.updated = now
        if status != 'closed':
            self.status_update_datetime = now + unix_sleep_to_timedelta(incident['timeouts'].get(status))
        if self.status != status:
            self.set_status(status)
            self.dump()
            return True
        self.dump()
        return False

    def update_state(self, alert_state: Dict) -> (bool, bool):
        update_status = self.update_status(alert_state['status'])
        update_state = self.last_state != alert_state
        if update_state:
            self.last_state = alert_state
        return update_status, update_state

    def set_status(self, status: str):
        self.status = status

    def assign_user_id(self, user_id: str):
        self.assigned_user_id = user_id

    def assign_user(self, user: str):
        self.assigned_user = user

    def is_new_firing_alerts_added(self, alert_state: Dict) -> bool:
        old_alerts_labels = self._get_firing_alerts_labels(self.last_state)
        new_alerts_labels = self._get_firing_alerts_labels(alert_state)
        return any(label not in old_alerts_labels for label in new_alerts_labels)

    def is_some_firing_alerts_removed(self, alert_state: Dict) -> bool:
        old_alerts_labels = self._get_firing_alerts_labels(self.last_state)
        new_alerts_labels = self._get_firing_alerts_labels(alert_state)
        return any(label not in new_alerts_labels for label in old_alerts_labels)

    @staticmethod
    def _get_firing_alerts_labels(alert_state):
        return [a.get('labels') for a in alert_state['alerts'] if a['status'] == 'firing']
