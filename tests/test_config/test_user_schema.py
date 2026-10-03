"""Configured users require an ID in core and in every messaging provider."""

import pytest
from pydantic import ValidationError

from app.config.validation import ImpulseConfig
from app.im.plugin_config import BaseApplicationConfig
from app.im.providers.none import NullApplicationConfig
from tests.utils import create_mattermost_config_data, create_slack_config_data, create_telegram_config_data

CONFIG_FACTORIES = {
    'slack': create_slack_config_data,
    'mattermost': create_mattermost_config_data,
    'telegram': create_telegram_config_data,
}


@pytest.mark.parametrize('user', [{}, {'id': None}, {'id': ''}, {'id': '   '}, {'id': True}, {'id': False}, 'alice', []])
def test_shared_schema_rejects_invalid_user_entries(user):
    with pytest.raises(ValidationError) as error:
        BaseApplicationConfig(type='slack', admin_users=[], users={'alice': user})
    assert error.value.errors()[0]['loc'][:2] == ('users', 'alice')


@pytest.mark.parametrize('provider_id', ['slack', 'mattermost', 'telegram'])
@pytest.mark.parametrize('user', [{}, {'id': None}, {'id': ''}, {'id': '   '}, {'id': True}, 'alice'])
def test_core_config_validation_rejects_invalid_provider_users(provider_id, user):
    data = CONFIG_FACTORIES[provider_id](admin_users=[], users={'alice': user})
    with pytest.raises(ValidationError) as error:
        ImpulseConfig.model_validate(data)
    assert error.value.errors()[0]['loc'][:3] == ('messenger', 'users', 'alice')


@pytest.mark.parametrize('provider_id, raw_id, expected_id', [
    ('slack', 'U1', 'U1'), ('mattermost', 'user-1', 'user-1'),
    ('telegram', 123, 123), ('telegram', '123', 123),
])
def test_id_only_provider_users_round_trip_with_native_id_types(provider_id, raw_id, expected_id):
    data = CONFIG_FACTORIES[provider_id](
        admin_users=['alice'], users={'alice': {'id': raw_id, 'name': 'Old Name', 'username': 'old_handle'}},
    )
    config = ImpulseConfig.model_validate(data)
    serialized = config.model_dump()
    assert serialized['messenger']['users'] == {'alice': {'id': expected_id}}
    restored = ImpulseConfig.model_validate(serialized)
    assert restored.messenger.users['alice'].id == expected_id
    assert type(restored.messenger.users['alice'].id) is type(expected_id)


def test_shared_schema_valid_users_work_with_prebuilt_core_config():
    messenger = BaseApplicationConfig(
        type='slack', admin_users=[], users={'alice': {'id': 'U1'}},
        channels={'default': {'id': 'C1'}},
    )
    config = ImpulseConfig(messenger=messenger, route={'channel': 'default'})
    assert config.messenger.users['alice'].id == 'U1'


def test_none_keeps_unused_user_configuration_permissive():
    assert NullApplicationConfig(users={'unused': {}}).users == {'unused': {}}
