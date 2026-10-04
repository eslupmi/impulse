"""Instant messaging templates for notifications and messages."""
from pathlib import Path
from typing import TYPE_CHECKING

from app.incident.freeze import MAINTENANCE_PARENT_SENTINEL
from app.jinja_template import JinjaTemplate

if TYPE_CHECKING:
    from app.incident.incident import Incident

class ProviderTemplates(dict):
    def __init__(self, name):
        super().__init__()
        self.name = name

    def __missing__(self, messenger):
        from app.im.registry import get_provider_registry
        registration = get_provider_registry().resolve(messenger)
        if registration.template_source is None:
            raise KeyError(f'{messenger} has no notification templates')
        try:
            source = Path('thread_templates', f'{messenger}_{self.name}.j2').read_text(encoding='utf-8')
        except FileNotFoundError:
            source = registration.template_source(self.name)
        self[messenger] = source
        return source


def template_users(messenger) -> dict:
    return {
        config_name: messenger.users.get(config_name)
        for config_name in messenger._users_config
    }


def chain_template_context(messenger, incident: 'Incident', step: dict) -> dict:
    return {
        'step': step,
        'incident': incident.serialize(),
        'users': template_users(messenger),
        'user_groups': messenger.user_groups,
        'groups': messenger.groups,
        'webhooks': messenger.webhooks,
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
    }


def freeze_template_context(incident: 'Incident', ui_user=None) -> dict:
    return {
        'incident': incident.serialize(),
        'parents': JinjaTemplate.related_incidents(incident.parents, skip=(MAINTENANCE_PARENT_SENTINEL,)),
        'childs': JinjaTemplate.related_incidents(incident.childs),
        'ui_user': ui_user,
    }


chain_step_user = ProviderTemplates('chain_step_user')
chain_step_user_group = ProviderTemplates('chain_step_user_group')
chain_step_group = ProviderTemplates('chain_step_group')
chain_step_webhook = ProviderTemplates('chain_step_webhook')
incident_notifications_assignment = ProviderTemplates('incident_notifications_assignment')
incident_notifications_status_update = ProviderTemplates('incident_notifications_status_update')
incident_notifications_new_firing = ProviderTemplates('incident_notifications_new_firing')
incident_notifications_partial_resolved = ProviderTemplates('incident_notifications_partial_resolved')
incident_notifications_freeze = ProviderTemplates('incident_notifications_freeze')
incident_notifications_unfreeze = ProviderTemplates('incident_notifications_unfreeze')
