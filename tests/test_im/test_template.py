"""Unit tests for thread template loader."""
from app.im import template


class TestThreadTemplates:
    def test_thread_templates_load_from_files(self):
        names = [
            'notification_user',
            'notification_user_group',
            'notification_group',
            'notification_webhook',
            'update_status',
            'update_alerts',
            'notification_assignment',
            'notification_unassignment',
            'notification_unfreeze',
        ]
        for name in names:
            content = getattr(template, name)
            assert isinstance(content, str)
            assert content.strip()
