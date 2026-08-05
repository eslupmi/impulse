"""Unit tests for thread template loader."""
from app.im import template


class TestThreadTemplates:
    def test_thread_templates_load_from_files(self):
        names = [
            'chain_step_user',
            'chain_step_user_group',
            'chain_step_group',
            'chain_step_webhook',
            'incident_notifications_assignment',
            'incident_notifications_status_update',
            'incident_notifications_new_firing',
            'incident_notifications_partial_resolved',
            'incident_notifications_freeze',
            'incident_notifications_unfreeze',
        ]
        for name in names:
            by_messenger = getattr(template, name)
            assert isinstance(by_messenger, dict)
            for messenger in ('slack', 'mattermost', 'telegram'):
                content = by_messenger[messenger]
                assert isinstance(content, str)
                assert content.strip()
