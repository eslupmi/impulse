"""Telegram provider contract regressions."""
import json
from dataclasses import FrozenInstanceError
from unittest.mock import AsyncMock, Mock

import pytest

from app.logging import DEFAULT_JSON_FORMAT, JSONFormatter
from impulse_messenger_api import IncidentPresentation, Interaction, InteractionAction, InteractionRequest, MessageRef, NotificationContent, ProviderContext, ProviderIdentity, ProviderResponse, UserProfile
from impulse_telegram import TelegramProvider, TEMPLATE_NAMES
from impulse_telegram.config import TelegramApplicationConfig
from tests.test_im.test_provider_seam import Response, Transport, config_for


def provider(secrets=None):
    return TelegramProvider(config_for('telegram'), secrets or {'TELEGRAM_BOT_TOKEN': 'test-token'})


def presentation(**changes):
    values = dict(channel_id=-100123, thread_id='10/20', status='firing', header='header', body='body',
                  status_icon='5312241539987020022', chain_enabled=True, frozen=False,
                  frozen_by_inhibition=False, frozen_by_maintenance=False, frozen_until=None,
                  can_unfreeze=False, task_link='', can_create_task=True)
    values.update(changes)
    return IncidentPresentation(**values)


def request(action, *, callback_id='ack-1'):
    body = {'callback_query': {'id': callback_id, 'data': action, 'from': {'id': 123},
                               'message': {'message_id': 20, 'message_thread_id': 10,
                                           'chat': {'id': -100123}}}}
    return InteractionRequest('POST', (), (), json.dumps(body).encode())


def test_config_secret_override_and_descriptor():
    assert TelegramApplicationConfig.model_validate(config_for('telegram').model_dump()).type == 'telegram'
    with pytest.raises(ValueError, match='TELEGRAM_BOT_TOKEN') as error:
        provider({'TELEGRAM_BOT_TOKEN': ''})
    assert 'secret-value' not in str(error.value)
    assert provider({'TELEGRAM_BOT_TOKEN': 'secret-value',
                     'DEV_MESSENGER_CUSTOM_ADDRESS': 'http://fake/bot/'}).url == 'http://fake/botsecret-value'
    assert TelegramProvider.descriptor.user_update_gap_seconds == 60
    assert not TelegramProvider.descriptor.notification_headers
    assert not TelegramProvider.descriptor.refresh_inhibition_source
    assert TelegramProvider.descriptor.html_autoescape
    assert TelegramProvider.descriptor.allow_inhibited_freeze_actions
    assert 'secret-value' not in provider({'TELEGRAM_BOT_TOKEN': 'secret-value',
                                           'DEV_MESSENGER_CUSTOM_ADDRESS': 'http://fake/bot/'}).redact_url('http://fake/botsecret-value')


@pytest.mark.asyncio
async def test_topic_message_update_notification_and_response_cleanup():
    tg = provider()
    http = Transport()
    await tg.initialize(ProviderContext(http, 'https://impulse.test/app'))
    await tg.activate()
    ref = await tg.create_incident(presentation(thread_id=None))
    assert ref == MessageRef(-100123, '10/20')
    create = next(call for call in http.calls if call[1].endswith('/sendMessage'))
    assert create[2]['json']['text'] == '🔥 header\nbody'
    assert create[2]['json']['reply_markup']['inline_keyboard'][0][0]['callback_data'] == 'stop_chain'
    await tg.update_incident(presentation(status='closed'))
    edit = next(call for call in http.calls if call[1].endswith('/editMessageText'))
    assert edit[2]['json']['reply_markup']['inline_keyboard'] == []
    result = await tg.post_notification(ref, NotificationContent(text='<b>notice</b>', header='ignored'))
    assert result.status_code == 200
    assert http.calls[-1][2]['json']['text'] == '<b>notice</b>'
    assert http.calls[-1][2]['json']['parse_mode'] == 'HTML'
    assert all(response.closed for response in http.responses)


@pytest.mark.asyncio
async def test_callback_decodes_to_immutable_command_and_acknowledges_after_edit():
    tg = provider()
    http = Transport()
    await tg.initialize(ProviderContext(http, 'https://impulse.test/app'))
    interaction = await tg.parse_interaction(request('freeze_menu'))
    assert isinstance(interaction, Interaction)
    assert interaction.message == MessageRef(-100123, '10/20')
    assert interaction.actor_id == 123
    assert interaction.commands[0].action == InteractionAction.SHOW_FREEZE_OPTIONS
    with pytest.raises(FrozenInstanceError):
        interaction.actor_id = '456'
    await tg.after_interaction(presentation(), interaction)
    assert http.calls[-2][1].endswith('/editMessageText')
    assert http.calls[-2][2]['json']['reply_markup']['inline_keyboard'][-1][0]['callback_data'] == 'freeze_back'
    assert http.calls[-1][1].endswith('/answerCallbackQuery')
    assert all(response.closed for response in http.responses)
    for action, expected in [('stop_chain', InteractionAction.TOGGLE_ASSIGNMENT),
                             ('task', InteractionAction.CREATE_TASK),
                             ('freeze_month', InteractionAction.FREEZE)]:
        assert (await tg.parse_interaction(request(action))).commands[0].action == expected
    assert (await tg.parse_interaction(request('freeze_month'))).commands[0].freeze_option == 'month'
    await tg.after_interaction(presentation(), await tg.parse_interaction(request('stop_chain')))
    assert http.calls[-3][1].endswith('/editForumTopic')
    assert http.calls[-2][1].endswith('/editMessageText')
    assert http.calls[-1][1].endswith('/answerCallbackQuery')
    assert isinstance(await tg.parse_interaction(request('bad-action')), ProviderResponse)


@pytest.mark.asyncio
async def test_user_profile_and_links():
    tg = provider()
    http = Transport()
    await tg.initialize(ProviderContext(http, 'https://impulse.test/app'))
    user = await tg.fetch_user(123)
    assert user == UserProfile(123, True, 'Alice', 'alice')
    assert tg.mention_id(user) == 123
    assert tg.user_url(user, ProviderIdentity()) == 'https://t.me/alice'
    assert tg.incident_url(MessageRef(-100123, '10/20'), ProviderIdentity()) == 'https://t.me/c/123/10/20'
    assert await tg.fetch_groups() == ()
    assert all(response.closed for response in http.responses)


def test_all_default_resources_are_present():
    assert len(TEMPLATE_NAMES) == 13
    assert all(TelegramProvider.template_source(name).strip() for name in TEMPLATE_NAMES)


def test_headerless_notifications_and_html_autoescape():
    from app.im.helpers import get_application
    app = get_application(config_for('telegram'), {'default': {'id': -100123}}, 'default')
    app.header_template.form_message = Mock(side_effect=AssertionError('header should not render'))
    assert app.notification_header(Mock()) is None
    rendered = app.body_template.form_message({
        'commonAnnotations': {'summary': '<unsafe>'}, 'commonLabels': {},
        'groupLabels': {}, 'alerts': [{'generatorURL': '', 'labels': {}, 'annotations': {}}],
    }, Mock(serialize=lambda: {'task_link': '', 'assigned_user_id': ''}, parents=[], childs=[]))
    assert '&lt;unsafe&gt;' in rendered and '<unsafe>' not in rendered


def test_telegram_user_serialization_preserves_numeric_id_and_fields():
    from app.im.helpers import get_application
    app = get_application(config_for('telegram'), {'default': {'id': -100123}}, 'default')
    user = app.create_user('alice', {'id': '123', 'exists': True, 'full_name': 'Alice', 'username': 'alice'})
    assert user.get_notification_identifier() == 123
    assert user.serialize() == {'exists': True, 'full_name': 'Alice', 'id': 123, 'roles': [], 'username': 'alice'}


@pytest.mark.asyncio
async def test_api_error_logs_exclude_reflected_secrets(caplog):
    reflected = 'reflected-secret-value'
    tg = provider({'TELEGRAM_BOT_TOKEN': reflected})
    user_response = Response({'ok': False, 'description': reflected})
    create_response = Response({'ok': False, 'description': reflected}, status=400)
    tg.http = Mock(get=AsyncMock(return_value=user_response),
                   post=AsyncMock(return_value=create_response))
    with caplog.at_level('DEBUG', logger='main_logger'):
        assert not (await tg.fetch_user(123)).exists
        assert await tg.create_incident(presentation(thread_id=None)) is None
    formatted = '\n'.join(JSONFormatter(DEFAULT_JSON_FORMAT).format(record)
                          for record in caplog.records if record.name == 'main_logger')
    assert reflected not in formatted
    assert user_response.closed and create_response.closed
