from unittest.mock import patch

import pytest
from pydantic import ValidationError

from app.im.chain.chain import Chain
from app.im.chain.google_calendar_chain import GoogleCalendarChain
from impulse_messenger_api.schema import SimpleChainStep


@pytest.mark.parametrize('kind', ['user', 'user_group', 'group', 'webhook', 'chain', 'wait'])
def test_step_preserves_condition(kind):
    step = SimpleChainStep(**{'if': "severity == 'critical'", kind: '5m' if kind == 'wait' else 'target'})
    assert step.model_dump(by_alias=True)['if'] == "severity == 'critical'"
    assert step.get_type() == kind



@pytest.mark.parametrize('condition', [True, 1, [], {}])
def test_schema_rejects_non_string_condition_metadata(condition):
    with pytest.raises(ValidationError):
        SimpleChainStep(**{'if': condition, 'user': 'Dmitry'})



@pytest.mark.parametrize('condition', ['', 'invalid', "__import__('os').system('id')"])
def test_schema_preserves_condition_without_interpreting_it(condition):
    step = SimpleChainStep(**{'if': condition, 'user': 'Dmitry'})
    assert step.condition == condition
    assert step.model_dump(by_alias=True)['if'] == condition



def test_non_chain_step_with_null_chain(sample_incident):
    chains = {'main': Chain('main', [{'user': 'Dmitry', 'chain': None}])}
    with patch.object(sample_incident, 'dump'):
        sample_incident.generate_chain(chains, 'main')
    assert [(s['name'], s['value']) for s in sample_incident.chain_steps] == [('user', 'Dmitry')]



@pytest.mark.parametrize('description', [
    "<p>- if: severity == 'critical'</p><p>  user: Dmitry</p>",
    "<p>- if: severity == 'critical'</p><p>&nbsp;&nbsp;user: Dmitry</p>",
    "- user: Dmitry\n  if: severity == 'critical'",
    "  - user: Dmitry\n    if: severity == 'critical'",
    "- user: Dmitry\n# comment\n  if: severity == 'critical'",
])
def test_calendar_preserves_multifield_steps(description):
    assert GoogleCalendarChain._parse_steps_from_description(description) == [
        {'if': "severity == 'critical'", 'user': 'Dmitry'},
    ]



def test_calendar_rejects_malformed_yaml():
    assert GoogleCalendarChain._parse_steps_from_description("- if: [\n  user: Dmitry") == []
