import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.im.application import Application
from app.im.interactions import apply_interaction
from app.im.users import ProfileUser, UserManager
from impulse_messenger_api import (
    Interaction, InteractionAction, InteractionCommand, MessageRef, ProviderDescriptor, ProviderResponse,
)


@pytest.mark.asyncio
@pytest.mark.parametrize('action, status, chain_enabled, assigns', [
    (InteractionAction.ASSIGN, 'resolved', False, True),
    (InteractionAction.RELEASE, 'firing', True, False),
    (InteractionAction.TOGGLE_ASSIGNMENT, 'resolved', False, False),
    (InteractionAction.TOGGLE_ASSIGNMENT, 'firing', True, True),
])
async def test_assignment_commands_preserve_explicit_intent(action, status, chain_enabled, assigns):
    app = Application.__new__(Application)
    app.provider = SimpleNamespace(descriptor=ProviderDescriptor('test'), respond_to_interaction=Mock(return_value=ProviderResponse()))
    app.users = UserManager()
    app.users.add_user('123', ProfileUser('Alice', id_='123', exists=True))
    app._async_tasks = set()
    app._get_user_timezone_str = Mock(return_value='UTC')
    app.post_assignment_notification = AsyncMock()
    app.post_unassignment_notification = AsyncMock()
    app.form_body_header_status_icons = Mock(return_value=('', '', ''))
    app._presentation = Mock()
    incident = SimpleNamespace(uniq_id='incident-1', channel_id='C1', status=status, chain_enabled=chain_enabled,
                               assigned_user_id='456', is_frozen=False, dump=Mock(), release=Mock())
    queue = SimpleNamespace(delete_by_id=AsyncMock())
    interaction = Interaction(MessageRef('C1', 'thread-1'), 123, (InteractionCommand(action),))

    await apply_interaction(app, interaction, Mock(get_by_ts=Mock(return_value=incident)), queue)
    await asyncio.gather(*app._async_tasks)
    assert incident.release.called is not assigns
    if assigns:
        assert incident.assigned_user_id == 123 and not incident.chain_enabled
        app.post_assignment_notification.assert_awaited_once_with(incident)
    else:
        app.post_unassignment_notification.assert_awaited_once_with(incident)
    queue.delete_by_id.assert_awaited_once()
