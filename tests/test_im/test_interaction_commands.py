from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.im.interactions import apply_interaction
from impulse_messenger_api import (
    Interaction, InteractionAction, InteractionCommand, MessageRef, ProviderDescriptor, ProviderResponse,
)


@pytest.mark.asyncio
async def test_commands_keep_order_after_menu_unfreezes_incident():
    events = []
    provider = SimpleNamespace(descriptor=ProviderDescriptor('test'), after_interaction=AsyncMock(),
                               respond_to_interaction=Mock(return_value=ProviderResponse()))
    application = SimpleNamespace(
        provider=provider, _get_user_timezone_str=Mock(return_value='UTC'),
        _handle_freeze_action=AsyncMock(side_effect=lambda *args, **kwargs: events.append('freeze')),
        _handle_unfreeze_action=AsyncMock(side_effect=lambda *args: events.append('unfreeze')),
        _handle_task_action=Mock(side_effect=lambda *args: events.append('task')),
        form_body_header_status_icons=Mock(return_value=('', '', '')), _presentation=Mock(),
    )
    incident = SimpleNamespace(channel_id='C1', is_frozen=False, dump=Mock(),
                               can_manual_unfreeze=Mock(side_effect=(False, True)))
    commands = (InteractionCommand(InteractionAction.FREEZE, 'tomorrow'),
                InteractionCommand(InteractionAction.SHOW_FREEZE_OPTIONS),
                InteractionCommand(InteractionAction.CREATE_TASK))
    interaction = Interaction(MessageRef('C1', 'thread-1'), 'user-1', commands)

    await apply_interaction(application, interaction, Mock(get_by_ts=Mock(return_value=incident)), None)

    assert events == ['freeze', 'unfreeze', 'task']
    remaining = provider.after_interaction.await_args.args[1].commands
    assert remaining == (commands[0], commands[2])
    incident.dump.assert_called_once_with()
