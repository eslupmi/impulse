"""Edition imports, configuration gates and the real static route contract."""
import os
import subprocess
import sys
from pathlib import Path
from textwrap import indent
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config.environment import EnvironmentConfig
from app.config.validation import ImpulseConfig
from app.edition import EDITION
from app.im.chain.conditions import matches_step
from app.im.chain.filter_steps import get_step_type_and_value
from app.im.chain.google_calendar_chain import GoogleCalendarChain
from impulse_messenger_api.schema import BaseApplicationConfig

ROOT = Path(__file__).resolve().parents[1]
CONDITION = "severity == 'critical'"


def run_python(source, edition=None):
    env = dict(os.environ)
    env.pop('DEV_EDITION', None)
    if edition is not None:
        env['DEV_EDITION'] = edition
    # Developer .env values must not override the environment under test.
    source = "from unittest.mock import patch\nwith patch('dotenv.load_dotenv'):\n" + indent(source, '    ')
    return subprocess.run([sys.executable, '-B', '-c', source], cwd=ROOT, env=env,
                          capture_output=True, text=True, check=False)


@pytest.mark.parametrize('edition', ['community', 'enterprise'])
def test_environment_edition_is_allowlisted(monkeypatch, edition):
    monkeypatch.setenv('DEV_EDITION', edition)
    assert EnvironmentConfig().dev_edition == edition


@pytest.mark.parametrize('edition', ['', 'Enterprise', '../enterprise', 'enterprise.app'])
def test_invalid_edition_is_rejected(monkeypatch, edition):
    monkeypatch.setenv('DEV_EDITION', edition)
    with pytest.raises(ValidationError, match='edition'):
        EnvironmentConfig()


def test_environment_defaults_to_community(monkeypatch):
    monkeypatch.delenv('DEV_EDITION', raising=False)
    assert EnvironmentConfig().dev_edition == 'community'
    assert 'edition' not in EnvironmentConfig.model_fields


def test_default_edition_and_process_lifetime_selection():
    result = run_python("""
import os
from app.edition import EDITION
from app.config.environment import get_environment_config
from app.im.chain.conditions import matches_step
assert get_environment_config().dev_edition == 'community'
assert EDITION == 'community'
os.environ['DEV_EDITION'] = 'enterprise'
assert matches_step({'user': 'alice'}, {}) is True
try:
    matches_step({'if': "severity == 'critical'", 'user': 'alice'}, {'severity': 'critical'})
except ValueError as exc:
    assert 'Enterprise' in str(exc)
else:
    raise AssertionError('Community silently executed a conditional step')
""")
    assert result.returncode == 0, result.stderr


def test_enterprise_is_selected_or_missing_without_fallback():
    result = run_python("""
from app.edition import EDITION
from app.im.chain.conditions import matches_step
assert EDITION == 'enterprise'
step = {'if': "severity == 'critical'", 'user': 'alice'}
assert matches_step(step, {'severity': 'critical'}) is True
assert matches_step(step, {'severity': 'warning'}) is False
""", 'enterprise')
    if (ROOT / 'enterprise').is_dir():
        assert result.returncode == 0, result.stderr
    else:
        assert result.returncode != 0
        assert "No module named 'enterprise'" in result.stderr


def test_invalid_edition_fails_during_import():
    result = run_python('import app.im.chain.conditions', 'invalid')
    assert result.returncode != 0
    assert 'ValidationError' in result.stderr


def test_public_schema_does_not_load_the_application():
    result = run_python("""
import sys
from impulse_messenger_api.schema import SimpleChainStep
step = SimpleChainStep(**{'if': "opaque edition-owned syntax", 'user': 'alice'})
assert step.condition == "opaque edition-owned syntax"
assert not any(name == 'app' or name.startswith('app.') for name in sys.modules)
""", 'invalid')
    assert result.returncode == 0, result.stderr



@pytest.mark.parametrize('condition', [True, 1, [], {}, 'invalid'])
def test_application_rejects_invalid_conditions_even_in_ui_only_configuration(condition):
    with pytest.raises(ValidationError):
        ImpulseConfig(messenger={
            'type': 'none',
            'chains': {'oncall': [{'user': 'alice', 'if': condition}]},
        })


@pytest.mark.skipif(EDITION != 'community', reason='Community availability policy')
@pytest.mark.parametrize('kind', ['simple', 'schedule', 'cloud'])
@pytest.mark.parametrize('prevalidated', [False, True])
def test_community_rejects_configuration_conditions(kind, prevalidated):
    steps = [{'user': 'alice', 'if': CONDITION}]
    definitions = {
        'simple': steps,
        'schedule': {'type': 'schedule', 'schedule': [{'steps': steps}]},
        'cloud': {'type': 'cloud', 'provider': 'google', 'calendar_id': 'test', 'default_steps': steps},
    }
    config = {'type': 'none', 'admin_users': [], 'chains': {'oncall': definitions[kind]}}
    if prevalidated:
        config = BaseApplicationConfig(**config)
    with pytest.raises(ValidationError, match='require the Enterprise edition'):
        ImpulseConfig(messenger=config)


@pytest.mark.skipif(EDITION != 'community', reason='Community availability policy')
def test_community_rejects_calendar_conditions_before_schedule_publication():
    chain = GoogleCalendarChain.__new__(GoogleCalendarChain)
    chain.name = 'oncall'
    chain._registries = {'users': {'alice': {}}}
    with pytest.raises(ValueError, match='require the Enterprise edition'):
        chain._convert_event_to_matcher({
            'description': f'- user: alice\n  if: {CONDITION}',
            'start': {'dateTime': '2026-11-06T09:00:00+00:00'},
            'end': {'dateTime': '2026-11-06T10:00:00+00:00'},
        })


@pytest.mark.skipif(EDITION != 'community', reason='Community availability policy')
def test_unsupported_calendar_edit_invalidates_old_unconditional_schedule():
    chain = GoogleCalendarChain.__new__(GoogleCalendarChain)
    chain.name = 'oncall'
    chain.default_steps = []
    chain._registries = {'users': {'alice': {}}}
    event = {
        'description': '- user: alice',
        'start': {'dateTime': '2026-11-06T09:00:00+00:00'},
        'end': {'dateTime': '2026-11-06T10:00:00+00:00'},
    }
    chain._update_schedule([event])
    assert chain.schedule[0].steps[0].user == 'alice'

    event['description'] += f"\n  if: {CONDITION}"
    with pytest.raises(ValueError, match='require the Enterprise edition'):
        chain._update_schedule([event])
    assert chain.schedule == []


def test_null_condition_and_metadata_do_not_change_the_action():
    step = {'if': None, 'chain': None, 'user': 'alice'}
    assert matches_step(step, {}) is True
    assert get_step_type_and_value(step) == ('user', 'alice')


@pytest.mark.parametrize('prefix', ['', '/impulse'])
def test_selected_editor_assets_are_served_before_common_static(prefix):
    from app import routes
    app = FastAPI()
    with patch.object(routes, 'get_config', return_value=SimpleNamespace(ui_config=True)):
        app.include_router(routes.create_router(prefix, app))
    with TestClient(app) as client:
        response = client.get(f'{prefix}/static/edition/js/chain_conditions.js')
        assert response.status_code == 200
        assert 'mountCondition' in response.text
        assert ('step-condition' in response.text) == (EDITION == 'enterprise')
        common = client.get(f'{prefix}/static/js/chains.js')
        assert common.status_code == 200
        assert '../edition/js/chain_conditions.js' in common.text


def test_missing_edition_assets_fail_router_creation(tmp_path):
    from app import routes
    original = routes.resource_directory
    app = FastAPI()
    with patch.object(routes, 'get_config', return_value=SimpleNamespace(ui_config=True)), \
            patch.object(routes, 'resource_directory', side_effect=lambda name: tmp_path if name.endswith('/static') else original(name)), \
            pytest.raises(RuntimeError, match='Missing static assets'):
        routes.create_router('', app)
