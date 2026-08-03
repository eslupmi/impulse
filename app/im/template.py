"""Instant messaging templates for notifications and messages."""

_THREAD_TEMPLATES_DIR = './thread_templates/'
_MESSENGERS = ('slack', 'mattermost', 'telegram')


def _load_thread_template(messenger: str, name: str) -> str:
    with open(f'{_THREAD_TEMPLATES_DIR}{messenger}_{name}.j2') as f:
        return f.read()


def _load_messenger_templates(name: str) -> dict:
    return {messenger: _load_thread_template(messenger, name) for messenger in _MESSENGERS}


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
