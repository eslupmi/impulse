from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
import yaml

from app.im.channel_manager import ChannelManager
from app.im.helpers import get_application
from app.incident.incident import Incident
from app.incident.incidents import Incidents
from app.queue.handlers.alert_handler import AlertHandler
from impulse_messenger_api import Interaction, InteractionAction, InteractionCommand, InteractionRequest, MessageRef, ProviderResponse
from tests.test_im.test_provider_seam import config_for
from tests.test_im.test_provider_seam import runtime as runtime

pytestmark = pytest.mark.usefixtures('runtime')


@pytest.mark.asyncio
@pytest.mark.parametrize('channel_id', ['C2', 0])
async def test_same_thread_in_two_channels_routes_to_the_correct_incident(channel_id):
    first = SimpleNamespace(channel_id='C1', ts='10/20', uniq_id='i1', uuid='u1', status='firing', is_frozen=False)
    second = SimpleNamespace(channel_id=channel_id, ts='10/20', uniq_id='i2', uuid='u2', status='firing', is_frozen=False, dump=Mock())
    incidents = Incidents([first, second])
    assert incidents.get_by_ts('10/20') is first
    assert incidents.get_by_ts('10/20', channel_id=str(channel_id)) is second
    assert incidents.get_by_ts('10/20', channel_id='missing') is None
    app = get_application(config_for('mattermost'), {'default': {'id': 'C1'}}, 'default')
    app.provider.parse_interaction = AsyncMock(return_value=Interaction(
        MessageRef(channel_id, '10/20'), 'user-1', (InteractionCommand(InteractionAction.NOOP),),
    ))
    app.provider.respond_to_interaction = Mock(return_value=ProviderResponse(b'handled'))
    app.form_body_header_status_icons = Mock(return_value=('', '', ''))
    app._presentation = Mock()

    response = await app.buttons_handler(InteractionRequest('POST', (), (), b''), incidents, None)
    assert response.body == b'handled'
    assert app._presentation.call_args.args[0] is second
    second.dump.assert_called_once()


@pytest.mark.asyncio
async def test_canonical_message_reference_and_channel_name_survive_restart(monkeypatch, sample_incident, tmp_path):
    monkeypatch.setattr(ChannelManager, '_instance', None)
    manager = ChannelManager()
    manager.initialize(['default'], {'default': {'id': '#alias'}}, 'default')
    app = get_application(config_for('mattermost'), {'default': {'id': '#alias'}}, 'default')
    app.public_url = 'https://chat.example.test'
    app.provider.create_incident = AsyncMock(return_value=MessageRef('!canonical:host', 'thread-1'))
    app.form_body_header_status_icons = Mock(return_value=('', '', ''))
    incident = sample_incident
    incident.channel_id = '#alias'
    handler = AlertHandler.__new__(AlertHandler)
    handler.app = app

    assert await handler._create_thread(incident) == 'thread-1'
    assert incident.channel_id == '!canonical:host' and incident.channel_name == 'default'
    manager.initialize(['default'], {'default': {'id': '#alias'}}, 'default')
    assert incident.channel_name == 'default'
    dump = tmp_path / 'incident.yml'
    dump.write_text(yaml.safe_dump(incident.serialize()))
    monkeypatch.setattr(ChannelManager, '_instance', None)
    ChannelManager().initialize(['default'], {'default': {'id': '#alias'}}, 'default')
    restored = Incident.load(str(dump), incident.config)
    assert restored.channel_id == '!canonical:host' and restored.ts == 'thread-1'
    assert restored.channel_name == 'default'
    restored.dump = Mock()
    app.provider.parse_interaction = AsyncMock(return_value=Interaction(
        MessageRef('!canonical:host', 'thread-1'), 'user-1', (InteractionCommand(InteractionAction.NOOP),),
    ))
    app.provider.respond_to_interaction = Mock(return_value=ProviderResponse(b'handled'))
    response = await app.buttons_handler(InteractionRequest('POST', (), (), b''), Incidents([restored]), None)
    assert response.body == b'handled'
