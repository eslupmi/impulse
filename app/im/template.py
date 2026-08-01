"""Instant messaging templates for notifications and messages."""

_THREAD_TEMPLATES_DIR = './thread_templates/'


def _load_thread_template(name: str) -> str:
    with open(f'{_THREAD_TEMPLATES_DIR}{name}.j2') as f:
        return f.read()


notification_user = _load_thread_template('notification_user')
notification_user_group = _load_thread_template('notification_user_group')
notification_group = _load_thread_template('notification_group')
update_status = _load_thread_template('update_status')
update_alerts = _load_thread_template('update_alerts')
notification_webhook = _load_thread_template('notification_webhook')
notification_assignment = _load_thread_template('notification_assignment')
notification_unassignment = _load_thread_template('notification_unassignment')
notification_unfreeze = _load_thread_template('notification_unfreeze')
