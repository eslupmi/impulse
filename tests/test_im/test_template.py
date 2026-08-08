"""Unit tests for thread template loader and Jinja context."""
from app.im import template
from app.jinja_template import JinjaTemplate


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

    def test_assignment_template_uses_incident(self):
        text = JinjaTemplate(template.incident_notifications_assignment['slack']).form_notification(
            incident={'assigned_user_id': 'U1', 'assigned_user': 'bob', 'assigned_fullname': 'Bob'},
            users={},
            ui_user=None,
        )
        assert 'U1' in text
        assert 'assigned' in text

        text = JinjaTemplate(template.incident_notifications_assignment['slack']).form_notification(
            incident={'assigned_user_id': ''},
            users={},
            ui_user=None,
        )
        assert 'unassigned' in text

    def test_chain_step_user_template_uses_step_and_users(self):
        class Unit:
            exists = True
            id = 'U1'

        text = JinjaTemplate(template.chain_step_user['slack']).form_notification(
            step={'name': 'user', 'value': 'alice'},
            incident={},
            users={'alice': Unit()},
            admins=[],
            user_groups={},
            groups={},
            webhooks={},
        )
        assert 'alice' in text
        assert '<@U1>' in text

    def test_chain_step_user_not_defined_when_missing(self):
        class Admin:
            id = 'A1'

        text = JinjaTemplate(template.chain_step_user['slack']).form_notification(
            step={'name': 'user', 'value': 'missing'},
            incident={},
            users={},
            admins=[Admin()],
            user_groups={},
            groups={},
            webhooks={},
        )
        assert 'NotDefined' in text
        assert '<@A1>' in text

    def test_status_update_template_uses_incident_status(self):
        text = JinjaTemplate(template.incident_notifications_status_update['slack']).form_notification(
            payload={},
            previous_payload={},
            incident={'status': 'firing'},
            users={},
            admins=[],
        )
        assert 'firing' in text

    def test_status_update_unknown_pings_admins(self):
        class Admin:
            id = 'A1'

        text = JinjaTemplate(template.incident_notifications_status_update['slack']).form_notification(
            payload={},
            previous_payload={},
            incident={'status': 'unknown'},
            users={},
            admins=[Admin()],
        )
        assert 'unknown' in text
        assert '<@A1>' in text

    def test_related_incidents_helper(self):
        class Incidents:
            def __init__(self):
                self.uniq_ids = {'a': object(), 'b': object()}

        JinjaTemplate.set_incidents(Incidents())
        related = JinjaTemplate.related_incidents(['a', 'missing', 'b'], skip=('maintenance',))
        assert set(related) == {'a', 'b'}
        JinjaTemplate.set_incidents(None)
