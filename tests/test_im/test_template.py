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
            user_groups={},
            groups={},
            webhooks={},
        )
        assert 'alice' in text
        assert '<@U1>' in text

    def test_chain_step_user_not_found_when_missing(self):
        class Admin:
            id = 'A1'
            roles = ['admin']

        text = JinjaTemplate(template.chain_step_user['slack']).form_notification(
            step={'name': 'user', 'value': 'missing'},
            incident={},
            users={'admin': Admin()},
            user_groups={},
            groups={},
            webhooks={},
        )
        assert 'NotFound' in text
        assert '<@A1>' in text

    def test_chain_context_matches_declared_vars(self):
        class Incident:
            def serialize(self):
                return {'uniq_id': 'inc-1'}

        class Users:
            def get(self, name):
                return None

        class Messenger:
            _users_config = {'alice': object()}
            users = Users()
            user_groups = {'ops': object()}
            groups = {'g': object()}
            webhooks = {'w': object()}
            admin_users = [object()]

        ctx = template.chain_template_context(
            Messenger(), Incident(), {'name': 'user', 'value': 'alice'},
        )
        assert set(ctx) == {'step', 'incident', 'users', 'user_groups', 'groups', 'webhooks'}
        assert 'admins' not in ctx

    def test_assignment_context_matches_declared_vars(self):
        class Incident:
            def serialize(self):
                return {'assigned_user_id': 'U1'}

        class Users:
            def get(self, name):
                return None

        class Messenger:
            _users_config = {}
            users = Users()

        ctx = template.assignment_template_context(Messenger(), Incident(), ui_user=None)
        assert set(ctx) == {'incident', 'users', 'ui_user'}

    def test_status_update_template_uses_incident_status(self):
        text = JinjaTemplate(template.incident_notifications_status_update['slack']).form_notification(
            payload={},
            previous_payload={},
            incident={'status': 'firing'},
            users={},
        )
        assert 'firing' in text

    def test_status_update_unknown_pings_admins(self):
        class Admin:
            id = 'A1'
            name = 'Admin'
            roles = ['admin']

        text = JinjaTemplate(template.incident_notifications_status_update['slack']).form_notification(
            payload={},
            previous_payload={},
            incident={'status': 'unknown'},
            users={'admin': Admin()},
        )
        assert 'unknown' in text
        assert '<@A1>' in text

    def test_status_update_context_includes_users(self):
        class Incident:
            def serialize(self):
                return {'status': 'unknown'}

        class Users:
            def get(self, name):
                return None

        class Messenger:
            _users_config = {}
            users = Users()

        ctx = template.status_update_template_context(Messenger(), Incident(), {}, {})
        assert set(ctx) == {'payload', 'previous_payload', 'incident', 'users'}
        assert 'admins' not in ctx

    def test_related_incidents_helper(self):
        class Incidents:
            def __init__(self):
                self.uniq_ids = {'a': object(), 'b': object()}

        JinjaTemplate.set_incidents(Incidents())
        related = JinjaTemplate.related_incidents(['a', 'missing', 'b'], skip=('maintenance',))
        assert set(related) == {'a', 'b'}
        JinjaTemplate.set_incidents(None)
