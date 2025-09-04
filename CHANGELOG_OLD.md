# Changelog

## v2.8.0
Changes:
- [Telegram] Улучшена обработка тем чатов и обычных сообщений:
  - Надежный парсинг `channel_id` и `thread_id` (поддержка `chat_id/topic_id` и обычных `message_id`).
  - Исправлена ошибка «not enough values to unpack» при отсутствии `/` в идентификаторе.
  - Добавлено логирование ответов Telegram API при создании темы и отправке сообщений, обработка `message_id=None`.
- [Telegram] Кнопка Mute:
  - Если доступен `silenceURL` из Grafana — показывается URL‑кнопка, которая открывает ссылку у пользователя.
  - Если настроен Alertmanager/Grafana API — используется callback‑кнопка с бэкенд‑созданием silence.
  - Кнопка доступна только для админов; для остальных — вежливая заглушка.
  - Устранено зацикливание ответов: корректные ответы через `answerCallbackQuery`, без лишних сообщений.
- [Telegram] Кнопка уведомлений: переименована в «🟢 Notifications ON» / «🔴 Notifications OFF» для понятности. Логика: влияет только на дополнительные статус‑уведомления, основное сообщение инцидента всегда обновляется.
- [Telegram] Тегающие сообщения (reply):
  - Тегающие сообщения теперь отправляются как reply к основному сообщению алерта.
  - Идентификаторы всех тегающих сообщений сохраняются в инциденте и удаляются при `resolved`.
  - При повторном `firing` того же алерта отправляется новое тегающее сообщение; при следующем `resolved` — удаляется.
- [Telegram] Назначение исполнителя: отключена отправка отдельного сообщения «assigned to …»; информация видна в основном сообщении алерта.
- [Chains/Queue] Повторный `firing` после `resolved`:
  - Цепочка регенерируется корректно, старые элементы очереди шагов удаляются.
  - `chain_enabled` устанавливается в `True` при генерации новой цепочки; старая цепь очищается перед пересборкой.
  - Добавлено детальное логирование генерации цепочки, пересоздания очереди и переходов статусов.
- [Telegram] Клавиатура: убрана передача `None` в inline‑кнопки (фильтрация отсутствующих кнопок), устранена ошибка «InlineKeyboardButton must be an Object».
- [Общее] Расширено debug‑логирование по критическим путям: создание/обновление тем, отправка сообщений, кнопка Mute, обновление статуса, генерация цепочек и работа очереди.

## v2.7.0
Changes:
- Added online / offline status indicator in the UI
- Added `application.type: none` support for running IMPulse without messenger integration ([docs](https://docs.impulse.bot/latest/config_file/#applicationtype))
- Removed update check functionality

## v2.6.0
Changes:
- [UI](https://docs.impulse.bot/latest/ui/) with multi-column sorting and value-based [highlighting](https://docs.impulse.bot/latest/config_file/#uicolors)
- Switched to `asyncio` for asynchronous processing
- Updated documentation and added table of contents

## v2.5.3
Changes:
- Refactor matcher logic to simplify condition checks and avoid applying regex to `None`

## v2.5.2
Changes:
- Fixed issue with parsing HTML description in Google Calendar events

## v2.5.1
Changes:
- Fixed incorrect warning about chain `None`
- Fixed a bug related to scheduled chains

## v2.5.0
Changes:
- Support for nested chains
- Documentation updated

## v2.4.0
Changes:
- Added Google Calendar support ([docs](https://docs.impulse.bot/latest/google/))
- Updated logic for **Take It** / **Release** button ([docs](https://docs.impulse.bot/latest/howto/#buttons))
- Added logging for button events
- [Telegram] Fixed incident link

## v2.3.1
Changes:
- [Telegram] Disabled **update available** functionality

## v2.3.0
Changes:
- Added [Telegram](https://telegram.org) support

## v2.2.0
Changes:
- Documentation moved to this repository

## v2.1.0
Changes:
- Added support for scheduled chains ([docs](https://docs.impulse.bot/latest/config_file/#schedule-chain))

## v2.0.0
Upgrade instructions:
- Modify `application.users`. Define users by their IDs instead of names ([docs](https://docs.impulse.bot/latest/config_file/#users))
- Add `application.channels` and define channels explicitly ([docs](https://docs.impulse.bot/latest/config_file/#channels))
- Replace Docker image `ghcr.io/ditsi/impulse` with `ghcr.io/eslupmi/impulse`
- Move `timeouts` under `incident` ([docs](https://docs.impulse.bot/latest/config_file/#all-options))
- [Mattermost] Rename `application.url` to `application.address` ([docs](https://docs.impulse.bot/latest/config_file/#all-options))
- [Mattermost] Move `url` under `application` and rename it to `impulse_address` ([docs](https://docs.impulse.bot/latest/config_file/#all-options))

Changes:
- Replaced **Chain** button with **Take It** / **Release**
- New behavior. The **Release** button restarts the chain from scratch
- Added `assigned to` field in templates with the user currently working on the incident
- Users and channels now defined by IDs only
- New **Channel** button state indicator
- Updated configuration file format

## v1.5.0
Changes:
- Added webhook timeout handling
- Fixed all known bugs

## v1.4.0
Changes:
- Major notifications format update
- Added notifications for new `firing` and some `resolved` alerts in existing incidents
- Added documentation links in notification messages
- Python 3.9 support
- Minor bug fixes

## v1.3.1
Changes:
- Fixed **update available** notification

## v1.3.0
Changes:
- Added support for private channels
- Switched [status_icons](https://github.com/eslupmi/impulse/blob/develop/templates/slack_status_icons.j2) to use `incident.status` instead of `payload.status`
- Use specific Slack workspace in incident links

## v1.2.0
Changes:
- Enabled use of incident object attributes in [templates](https://docs.impulse.bot/latest/templates/) and [webhooks](https://docs.impulse.bot/latest/webhooks/)
- Template refactoring
- Added runbook link to message templates ([docs](https://docs.impulse.bot/latest/templates/#source-and-runbook-links))
- Fixed user notifications for undefined users

## v1.1.0
Changes:
- Added webhook notifications to instant messengers
- Major refactoring
- Switched to WSGI for running the app
- Fixed `user` and `user_group` notifications for non-existent and undefined users
- Logging improvements

## v1.0.4
Changes:
- [Mattermost] Fixed @mention formatting

## v1.0.3
Changes:
- [Mattermost] Increased pagination limit for API requests

## v1.0.2
Changes:
- [Mattermost] Increased API limit from 60 to 1000 for `/api/v4/teams/<team_id>/channels`

## v1.0.1
Changes:
- [Slack] Increased API limit from 100 to 1000 for `api/conversations.list`

## v1.0.0
Upgrade instructions:
- Remove the `check_updates` option from **impulse.yml**
- Remove `application.message_template`, use `application.template_files` instead
- Rename `webhook.user` to `webhook.auth`

Changes:
- New incident message structure with `status_icons`, `header`, and `body`
- Added template files for incident message components
- Updated **impulse.yml** format
- [Mattermost] Fixed update payload
- Introduced new notification format
- [Mattermost] Fixed button state
- [Mattermost] Updated button payload
- Fixed `user_group` notifications

## v0.6.0
Changes:
- Added release notes to the **update available** message
- [Mattermost] Fixed update message functionality
- [Mattermost] Fixed user notification for users without a first name
- [Mattermost] Fixed bug where a declared user did not exist in the messenger

## v0.5.0
Changes:
- [Mattermost] Replaced button icons
- [Mattermost] Config now uses the displayed team name
- [Mattermost] Fixed error in **user not found** logic for `user_groups`
- [Mattermost] Fixed case-sensitivity issue with the team name in incident links
- Made the `user` field optional for Webhook
