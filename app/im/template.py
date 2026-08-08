"""Instant messaging templates for notifications and messages."""
from typing import TYPE_CHECKING

from app.incident.freeze import MAINTENANCE_PARENT_SENTINEL
from app.jinja_template import JinjaTemplate

if TYPE_CHECKING:
    from app.incident.incident import Incident

_THREAD_TEMPLATES_DIR = './thread_templates/'
_MESSENGERS = ('slack', 'mattermost', 'telegram')


def _load_thread_template(messenger: str, name: str) -> str:
    with open(f'{_THREAD_TEMPLATES_DIR}{messenger}_{name}.j2') as f:
        return f.read()


def _load_messenger_templates(name: str) -> dict:
    return {messenger: _load_thread_template(messenger, name) for messenger in _MESSENGERS}


def template_users(messenger) -> dict:
    """Config-name → user map for templates. Missing lookups stay None (NotDefined)."""
    return {
        config_name: messenger.users.get(config_name)
        for config_name in (messenger._users_config or {})
    }


def template_admins(messenger) -> list:
    """Users from messenger.admin_users (config admin_users), not config roles."""
    return list(messenger.admin_users or [])


def chain_template_context(messenger, incident: 'Incident', step: dict) -> dict:
    return {
        'step': step,
        'incident': incident.serialize(),
        'users': template_users(messenger),
        'admins': template_admins(messenger),
        'user_groups': messenger.user_groups or {},
        'groups': messenger.groups or {},
        'webhooks': messenger.webhooks or {},
    }


def assignment_template_context(messenger, incident: 'Incident', ui_user=None) -> dict:
    return {
        'incident': incident.serialize(),
        'users': template_users(messenger),
        'ui_user': ui_user,
    }


def status_update_template_context(messenger, incident: 'Incident', payload, previous_payload) -> dict:
    return {
        'payload': payload,
        'previous_payload': previous_payload,
        'incident': incident.serialize(),
        'users': template_users(messenger),
        'admins': template_admins(messenger),
    }


def freeze_template_context(incident: 'Incident', ui_user=None) -> dict:
    return {
        'incident': incident.serialize(),
        'parents': JinjaTemplate.related_incidents(incident.parents, skip=(MAINTENANCE_PARENT_SENTINEL,)),
        'childs': JinjaTemplate.related_incidents(incident.childs),
        'ui_user': ui_user,
    }


chain_step_user = _load_messenger_templates('chain_step_user')
chain_step_user_group = _load_messenger_templates('chain_step_user_group')
chain_step_group = _load_messenger_templates('chain_step_group')
chain_step_webhook = _load_messenger_templates('chain_step_webhook')
incident_notifications_assignment = _load_messenger_templates('incident_notifications_assignment')
incident_notifications_status_update = _load_messenger_templates('incident_notifications_status_update')
incident_notifications_new_firing = _load_messenger_templates('incident_notifications_new_firing')
incident_notifications_partial_resolved = _load_messenger_templates('incident_notifications_partial_resolved')
incident_notifications_freeze = _load_messenger_templates('incident_notifications_freeze')
incident_notifications_unfreeze = _load_messenger_templates('incident_notifications_unfreeze')
