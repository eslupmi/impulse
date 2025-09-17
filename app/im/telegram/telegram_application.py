import asyncio
import time

import aiohttp
from fastapi.responses import JSONResponse

from app.im.application import Application
from app.im.telegram.config import buttons
from app.im.telegram.user import User
from app.im.template import JinjaTemplate, update_status, update_alerts, notification_user, notification_user_group
from app.im.grafana_renderer import create_grafana_renderer
from app.logging import logger
from config import telegram_bot_token, application, grafana_renderer_url, grafana_url, grafana_render_key, grafana_render_enabled, grafana_render_rate_limit, grafana_render_max_size, grafana_render_time_to_render


class TelegramApplication(Application):
    icon_map = { #!
        '5312241539987020022': '🔥', # firing
        '5379748062124056162': '❗️', # unknown
        '5237699328843200968': '✅', # resolved
        '5408906741125490282': '🏁' # closed
    }

    def __init__(self, app_config, channels, users):
        super().__init__(app_config, channels, users)
        # Инициализируем Grafana Renderer
        self.grafana_renderer = None
        self.render_enabled = grafana_render_enabled
        self.render_rate_limit = grafana_render_rate_limit
        self.render_max_size = grafana_render_max_size
        self._last_render_times = {}  # Для rate limiting
        self._rendering_in_progress = set()  # UUID инцидентов, для которых идет рендеринг
        self._init_grafana_renderer()

    def _init_grafana_renderer(self):
        """Инициализирует Grafana Renderer из конфигурации"""
        logger.info(f"Инициализация Grafana Renderer: render_enabled={self.render_enabled}")
        if not self.render_enabled:
            logger.info("Grafana Renderer отключен в конфигурации (GRAFANA_RENDER_ENABLED=false)")
            return
            
        try:
            config = {
                'renderer_url': grafana_renderer_url,
                'grafana_url': grafana_url,
                'render_key': grafana_render_key,
                'time_to_render': grafana_render_time_to_render
            }
            logger.info(f"Конфигурация рендерера: {config}")
            self.grafana_renderer = create_grafana_renderer(config)
            if self.grafana_renderer:
                logger.info(f"Grafana Renderer успешно инициализирован (rate limit: {self.render_rate_limit}s, time_to_render: {grafana_render_time_to_render} мин)")
            else:
                logger.warning("Grafana Renderer не инициализирован - проверьте конфигурацию")
                self.render_enabled = False
        except Exception as e:
            logger.error(f"Ошибка при инициализации Grafana Renderer: {e}")
            self.grafana_renderer = None
            self.render_enabled = False

    def _can_render_panel(self, incident_uuid):
        """Проверяет, можно ли рендерить панель (rate limiting)"""
        if not self.render_enabled or not self.grafana_renderer:
            return False, "Рендеринг отключен"
            
        # Проверяем, не идет ли уже рендеринг для этого инцидента
        if incident_uuid in self._rendering_in_progress:
            return False, "Рендеринг уже выполняется, подождите..."
            
        current_time = time.time()
        last_render_time = self._last_render_times.get(incident_uuid, 0)
        
        if current_time - last_render_time < self.render_rate_limit:
            remaining_time = int(self.render_rate_limit - (current_time - last_render_time))
            return False, f"Подождите {remaining_time} секунд перед следующим скриншотом"
            
        return True, "OK"

    def _update_render_time(self, incident_uuid):
        """Обновляет время последнего рендеринга для инцидента"""
        self._last_render_times[incident_uuid] = time.time()

    def _start_rendering(self, incident_uuid):
        """Отмечает начало рендеринга для инцидента"""
        self._rendering_in_progress.add(incident_uuid)
        logger.debug(f"Начат рендеринг для инцидента {incident_uuid}")

    def _finish_rendering(self, incident_uuid):
        """Отмечает окончание рендеринга для инцидента"""
        self._rendering_in_progress.discard(incident_uuid)
        logger.debug(f"Завершен рендеринг для инцидента {incident_uuid}")

    async def _update_screenshot_button_state(self, incident_):
        """Обновляет состояние кнопки скриншота в сообщении"""
        try:
            # Получаем данные для обновления сообщения
            body = self.body_template.form_message(incident_.last_state, incident_)
            header = self.header_template.form_message(incident_.last_state, incident_)
            status_icons = self.status_icons_template.form_message(incident_.last_state, incident_)
            
            # Устанавливаем контекст для клавиатуры
            self._current_incident_for_keyboard = incident_
            self._current_alert_state_for_keyboard = incident_.last_state
            self._current_status_for_keyboard = incident_.status
            
            # Обновляем сообщение
            await self.update_thread(
                incident_.channel_id, 
                incident_.thread_id if incident_.thread_id else incident_.ts, 
                incident_.status, 
                body, 
                header, 
                status_icons,
                incident_.chain_enabled, 
                incident_.status_enabled,
                incident_
            )
            
            # Очищаем контекст
            for attr in ['_current_incident_for_keyboard', '_current_alert_state_for_keyboard', '_current_status_for_keyboard']:
                if hasattr(self, attr):
                    delattr(self, attr)
                    
        except Exception as e:
            logger.error(f"Ошибка при обновлении состояния кнопки скриншота: {e}")

    def _initialize_specific_params(self):
        self.url += telegram_bot_token
        self.post_message_url = self.url + '/sendMessage'
        self.headers = {'Content-Type': 'application/json'}
        self.post_delay = 0.15
        self.thread_id_key = 'message_id'

    def _parse_channel_id(self, channel_id):
        """Parse channel_id to extract chat_id and optional topic_id.
        
        Supports formats:
        - "<chat_id>" (no topic)
        - "<chat_id>/<topic_id>" 
        - "<chat_id>_<topic_id>"
        
        Returns (chat_id, topic_id_or_None)
        """
        channel_str = str(channel_id)
        if '/' in channel_str:
            chat_id, topic_id = channel_str.split('/', 1)
        elif '_' in channel_str:
            chat_id, topic_id = channel_str.split('_', 1)
        else:
            chat_id = channel_str
            topic_id = None
        return chat_id, topic_id

    async def initialize_async(self):
        """Initialize async components after object creation"""
        await super().initialize_async()
        await self._setup_webhook()

    def _get_url(self, app_config):
        return 'https://api.telegram.org/bot'

    def _get_public_url(self, app_config):
        return 'https://api.telegram.org/bot'

    def _get_team_name(self, app_config):
        return None

    def get_notification_destinations(self):
        return self.admin_users

    def format_text_bold(self, text):
        return f'<b>{text}</b>'

    def _format_text_link(self, text, url):
        return f'<a href={url}>{text}</a>'

    def format_text_italic(self, text):
        return f'<i>{text}</i>'

    def _format_tg_icon(self, icon):
        return f'{self.icon_map.get(icon)}'

    def get_admins_text(self): #!
        return ', '.join([f'@{a.id}' for a in self.admin_users])

    def format_user_mention(self, user_id, display_name=None):
        """Format a user mention for Telegram using the tg://user link format."""
        return f'<a href="tg://user?id={user_id}">{display_name}</a>'

    async def send_message(self, channel_id, text, attachment):
        params = {
            'chat_id': channel_id,
            'text': text,
            'parse_mode': 'HTML'
        }
        async with self.http.post(self.post_message_url, params=params) as response:
            await asyncio.sleep(self.post_delay)
            response_json = await response.json()
            return response_json.get('result', {}).get('message_id')

    async def send_photo(self, channel_id, text, photo_data, filename="panel.png", reply_to_message_id=None):
        """
        Отправляет изображение в Telegram
        
        Args:
            channel_id: ID канала
            text: Текст сообщения
            photo_data: Байты изображения
            filename: Имя файла
            reply_to_message_id: ID сообщения для реплая
            
        Returns:
            ID сообщения или None
        """
        try:
            # Проверяем размер изображения
            if len(photo_data) > self.render_max_size:
                logger.warning(f"Изображение слишком большое: {len(photo_data)} байт (лимит: {self.render_max_size})")
                # Попробуем сжать изображение
                photo_data = await self._compress_image(photo_data)
                if not photo_data:
                    logger.error("Не удалось сжать изображение")
                    return None
            
            # Создаем multipart/form-data для отправки изображения
            data = aiohttp.FormData()
            data.add_field('chat_id', str(channel_id))
            data.add_field('text', text)
            data.add_field('parse_mode', 'HTML')
            data.add_field('photo', photo_data, filename=filename, content_type='image/png')
            
            if reply_to_message_id:
                data.add_field('reply_to_message_id', str(reply_to_message_id))
            
            async with self.http.post(f'{self.url}/sendPhoto', data=data) as response:
                await asyncio.sleep(self.post_delay)
                response_json = await response.json()
                if response_json.get('ok'):
                    return response_json.get('result', {}).get('message_id')
                else:
                    logger.error(f"Ошибка отправки фото: {response_json}")
                    return None
        except Exception as e:
            logger.error(f"Ошибка при отправке фото: {e}")
            return None

    async def _compress_image(self, image_data):
        """Сжимает изображение если оно слишком большое"""
        try:
            from PIL import Image
            import io
            
            # Открываем изображение
            image = Image.open(io.BytesIO(image_data))
            
            # Если размер уже меньше лимита, возвращаем как есть
            if len(image_data) <= self.render_max_size:
                return image_data
            
            # Вычисляем коэффициент сжатия
            compression_ratio = self.render_max_size / len(image_data)
            new_width = int(image.width * (compression_ratio ** 0.5))
            new_height = int(image.height * (compression_ratio ** 0.5))
            
            # Изменяем размер
            resized_image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # Сохраняем с сжатием
            output = io.BytesIO()
            resized_image.save(output, format='PNG', optimize=True, quality=85)
            compressed_data = output.getvalue()
            
            logger.info(f"Сжато изображение: {len(image_data)} -> {len(compressed_data)} байт")
            return compressed_data
            
        except ImportError:
            logger.warning("PIL не установлен, сжатие недоступно")
            return None
        except Exception as e:
            logger.error(f"Ошибка при сжатии изображения: {e}")
            return None

    async def render_and_send_panel(self, channel_id, alert_data, text="Скриншот панели", reply_to_message_id=None):
        """
        Рендерит панель Grafana и отправляет скриншот в Telegram
        
        Args:
            channel_id: ID канала
            alert_data: Данные алерта
            text: Текст сообщения
            reply_to_message_id: ID сообщения для реплая
            
        Returns:
            ID сообщения или None
        """
        if not self.grafana_renderer:
            logger.warning("Grafana Renderer не инициализирован")
            return None
            
        try:
            # Рендерим панель
            image_data = await self.grafana_renderer.render_panel_from_alert(alert_data)
            if not image_data:
                logger.warning("Не удалось получить изображение панели")
                return None
            
            # Отправляем изображение
            message_id = await self.send_photo(channel_id, text, image_data, reply_to_message_id=reply_to_message_id)
            if message_id:
                logger.info(f"Скриншот панели успешно отправлен, message_id: {message_id}")
            return message_id
            
        except Exception as e:
            logger.error(f"Ошибка при рендеринге и отправке панели: {e}")
            return None

    async def delete_message(self, channel_id, message_id):
        """
        Удаляет сообщение в Telegram
        
        Args:
            channel_id: ID канала
            message_id: ID сообщения
            
        Returns:
            True если успешно, False если ошибка
        """
        try:
            payload = {
                'chat_id': channel_id,
                'message_id': message_id
            }
            
            async with self.http.post(f'{self.url}/deleteMessage', json=payload, headers=self.headers) as response:
                await asyncio.sleep(self.post_delay)
                response_json = await response.json()
                if response_json.get('ok'):
                    logger.debug(f"Сообщение {message_id} успешно удалено")
                    return True
                else:
                    logger.warning(f"Не удалось удалить сообщение {message_id}: {response_json}")
                    return False
        except Exception as e:
            logger.error(f"Ошибка при удалении сообщения {message_id}: {e}")
            return False

    async def create_thread(self, channel_id, body, header, status_icons, status):
        # Parse channel_id to extract topic_id if present
        chat_id, topic_id = self._parse_channel_id(channel_id)
        
        logger.debug(f'Creating thread: chat_id={chat_id}, topic_id={topic_id}')
        
        # If topic_id is provided in channel_id, use it; otherwise create new topic
        if topic_id:
            # Use existing topic
            logger.debug(f'Using existing topic: {topic_id}')
            payload = self._create_thread_payload(chat_id, body, header, status_icons, status)
            payload['message_thread_id'] = topic_id
        else:
            # Create new topic
            logger.debug(f'Creating new topic for chat: {chat_id}')
            topic_id = await self._create_topic(chat_id, header, status_icons)
            logger.debug(f'Created topic_id: {topic_id}')
            payload = self._create_thread_payload(chat_id, body, header, status_icons, status)
            payload['message_thread_id'] = topic_id
        
        logger.debug(f'Sending message to topic: {topic_id}')
        message_id = await self._send_create_thread(payload)
        logger.debug(f'Got message_id: {message_id}')
        
        # Handle case where topic_id or message_id is None
        if topic_id is None:
            logger.error('Failed to create topic - topic_id is None')
            raise Exception('Failed to create topic')
            
        if message_id is None:
            logger.error('Failed to send message - message_id is None')
            raise Exception('Failed to send message to topic')
        
        result = f'{topic_id}/{message_id}'
        logger.debug(f'Final thread_id: {result}')
        return result

    async def _send_create_thread(self, payload):
        async with self.http.post(self.post_message_url, headers=self.headers, json=payload) as response:
            await asyncio.sleep(self.post_delay)
            response_json = await response.json()
            
            # Debug logging to understand the response structure
            logger.debug(f'Telegram API response: {response_json}')
            
            if not response_json.get('ok'):
                logger.error(f'Telegram API error: {response_json}')
                return None
                
            result = response_json.get('result', {})
            message_id = result.get(self.thread_id_key)
            
            if message_id is None:
                logger.error(f'No message_id in response. Result: {result}')
                
            return message_id

    async def buttons_handler(self, payload, incidents, queue_, route):
        if 'callback_query' not in payload:
            # Это обычное сообщение, не callback_query - просто возвращаем пустой ответ
            return JSONResponse({}, status_code=200)
        logger.debug(f'Button handler called with callback_query: {payload["callback_query"]}')
        callback = payload['callback_query']
        message_id = callback['message']['message_id']
        post_id = callback['message'].get('message_thread_id')
        
        # Handle both regular messages and forum topic messages
        if post_id is not None:
            thread_id = f'{post_id}/{message_id}'
        else:
            # For regular messages (not in forum topics), use just message_id
            thread_id = str(message_id)
        
        logger.debug(f'Looking for incident with thread_id: {thread_id}')
        
        # Debug: List all incidents and their thread_ids
        logger.debug(f'Available incidents:')
        for uuid, incident in incidents.by_uuid.items():
            logger.debug(f'  - {uuid}: thread_id="{incident.thread_id}", ts="{incident.ts}", app_type="{incident.config.application_type}"')
        
        incident_ = incidents.get_by_ts(ts=thread_id)
        # Extra fallback: try plain message_id if not found (for compatibility with legacy incidents)
        if incident_ is None:
            plain_id = str(message_id)
            logger.debug(f'Incident not found by full thread_id, trying plain message_id: {plain_id}')
            incident_ = incidents.get_by_ts(ts=plain_id)
        if incident_ is None:
            logger.warning(f'No incident found for thread_id: {thread_id}')
            async with self.http.post(
                f'{self.url}/answerCallbackQuery',
                json={'callback_query_id': callback['id']},
                headers=self.headers
            ) as response:
                pass
            return JSONResponse({}, status_code=200)
        action = callback['data']
        logger.debug(f'Button action: {action}, incident: {incident_.uuid}')

        user_id = callback['from']['id']
        user_from = callback.get('from', {})
        first_name = user_from.get('first_name', '').strip()
        last_name = user_from.get('last_name', '').strip()
        user_display_name = f"{first_name} {last_name}".strip() or user_from.get('username')
        incident_.assign_user(user_display_name)

        if action in ['start_chain', 'stop_chain']:
            logger.debug(f'Processing chain action: {action}')
            await queue_.delete_by_id(incident_.uuid, delete_steps=True, delete_status=False)
            if action == 'stop_chain':
                logger.info(f'Incident {incident_.uuid} -> button TAKE IT pressed')
                incident_.assign_user_id(user_id)
                asyncio.create_task(self.fetch_and_assign_user_name(incident_, user_id, incidents))
                asyncio.create_task(self.post_assignment_notification(incident_, user_id, user_display_name))
                
                # Check if this is a fixed topic
                _, fixed_topic_id = self._parse_channel_id(incident_.channel_id)
                is_fixed_topic = fixed_topic_id is not None
                
                if is_fixed_topic:
                    # For fixed topics, disable chain when taken
                    incident_.chain_enabled = False
                    logger.debug(f'Set chain_enabled=False for fixed topic incident {incident_.uuid}')
                else:
                    # For non-fixed topics, keep chain enabled to send tagging messages
                    # The chain will be disabled when incident is resolved
                    logger.debug(f'Keeping chain_enabled=True for non-fixed topic incident {incident_.uuid}')
            else:
                logger.info(f'Incident {incident_.uuid} -> button RELEASE pressed')
                incident_.release()
                logger.debug(f'Released incident {incident_.uuid}')
        elif action in ['start_status', 'stop_status', 'silence', 'panel_screenshot', 'panel_screenshot_disabled']:
            logger.debug(f'Processing status action: {action}')
            if action == 'stop_status':
                logger.info(f'Incident {incident_.uuid} -> button STATUS pressed (disabled)')
                incident_.status_enabled = False
                logger.debug(f'Set status_enabled=False for incident {incident_.uuid}')
            elif action == 'start_status':
                logger.info(f'Incident {incident_.uuid} -> button STATUS pressed (enabled)')
                incident_.status_enabled = True
                logger.debug(f'Set status_enabled=True for incident {incident_.uuid}')
            elif action == 'silence':
                logger.info(f'Incident {incident_.uuid} -> button Mute pressed (callback)')
                # Allow only admin users to trigger Mute
                admin_ids = {u.id for u in self.admin_users or []}
                if user_id not in admin_ids:
                    await self._answer_callback(callback['id'], 'You are not allowed to mute (admins only)')
                    return JSONResponse({}, status_code=200)
                # This should only happen if API is available (URL buttons don't send callbacks)
                can_api = self._is_silence_api_available()
                if not can_api:
                    await self._answer_callback(callback['id'], 'Mute is not configured')
                    return JSONResponse({}, status_code=200)
                await self._handle_silence_backend(incident_, callback['id'])
                # For silence action, we don't need to update the message or answer callback again
                return JSONResponse({}, status_code=200)
            elif action == 'panel_screenshot':
                logger.info(f'Incident {incident_.uuid} -> button Screenshot pressed')
                await self._handle_panel_screenshot(incident_, callback['id'])
                # For screenshot action, we don't need to update the message or answer callback again
                return JSONResponse({}, status_code=200)
            elif action == 'panel_screenshot_disabled':
                logger.info(f'Incident {incident_.uuid} -> button Screenshot pressed (disabled)')
                await self._answer_callback(callback['id'], 'Рендеринг уже выполняется, подождите...')
                return JSONResponse({}, status_code=200)
        else:
            logger.warning(f'Unknown action: {action}')
        incident_.dump()
        logger.debug(f'Incident {incident_.uuid} state after action: chain_enabled={incident_.chain_enabled}, status_enabled={incident_.status_enabled}')
        
        body = self.body_template.form_message(incident_.last_state, incident_)
        header = self.header_template.form_message(incident_.last_state, incident_)
        # provide incident, alert_state and status for keyboard builder within this update
        self._current_incident_for_keyboard = incident_
        self._current_alert_state_for_keyboard = incident_.last_state
        self._current_status_for_keyboard = incident_.status
        status_icons = self.status_icons_template.form_message(incident_.last_state, incident_)
        
        logger.debug(f'Updating thread for incident {incident_.uuid}: chain_enabled={incident_.chain_enabled}, status_enabled={incident_.status_enabled}')
        await self.update_thread(
            incident_.channel_id, incident_.ts, incident_.status, body, header, status_icons,
            incident_.chain_enabled, incident_.status_enabled
        )
        for attr in ['_current_incident_for_keyboard', '_current_alert_state_for_keyboard', '_current_status_for_keyboard', '_show_silence_for_keyboard']:
            if hasattr(self, attr):
                delattr(self, attr)

        await self._answer_callback(callback['id'])
        logger.debug(f'Button handler completed for incident {incident_.uuid}')
        return JSONResponse({}, status_code=200)

    async def _answer_callback(self, cb_id, text: str = None):
        payload = {'callback_query_id': cb_id}
        if text:
            payload['text'] = text
            payload['show_alert'] = False
        async with self.http.post(
            f'{self.url}/answerCallbackQuery',
            json=payload,
            headers=self.headers
        ) as response:
            pass

    async def _create_topic(self, channel_id, header, status_icons):
        payload = {
            'chat_id': channel_id,
            'name': header,
            'icon_custom_emoji_id': status_icons
        }
        try:
            logger.debug(f'Creating topic with payload: {payload}')
            async with self.http.post(
                f'{self.url}/createForumTopic',
                json=payload,
                headers=self.headers
            ) as response:
                response_json = await response.json()
                logger.debug(f'Create topic response: {response_json}')
                
                if not response_json.get('ok'):
                    logger.error(f'Failed to create topic: {response_json}')
                    return None
                    
                topic_id = response_json.get('result', {}).get('message_thread_id')
                logger.debug(f'Created topic_id: {topic_id}')
                return topic_id
        except aiohttp.ClientError as e:
            logger.error(f'Failed to create topic: {e}')
            raise e

    async def _handle_silence_backend(self, incident_, callback_id):
        """Create silence via backend-accessible API.
        Supported backend: Alertmanager API (application.alertmanager.api_url).
        If Alertmanager API is not configured, backend mute is not available (use silenceURL button instead).
        """
        try:
            am_cfg = application.get('alertmanager', {}) or {}
            api_url = am_cfg.get('api_url')
            duration = am_cfg.get('silence_duration', '2h')

            alert = incident_.last_state or {}
            labels = alert.get('groupLabels') or alert.get('commonLabels') or {}

            if api_url:
                matchers = []
                for key in ['alertname', 'instance', 'project']:
                    if key in labels:
                        matchers.append({'name': key, 'value': str(labels[key]), 'isRegex': False})
                if not matchers and labels:
                    k, v = next(iter(labels.items()))
                    matchers.append({'name': k, 'value': str(v), 'isRegex': False})

                payload = {
                    'matchers': matchers,
                    'startsAt': None,
                    'endsAt': None,
                    'duration': duration,
                    'createdBy': 'IMPulse',
                    'comment': f"Muted via IMPulse for incident {incident_.uuid}"
                }

                async with self.http.post(f"{api_url.rstrip('/')}/api/v2/silences", json=payload, headers={'Content-Type': 'application/json'}) as resp:
                    data = await resp.json()
                    if 200 <= resp.status < 300:
                        silence_id = data.get('silenceID') or data.get('silenceId') or data.get('id')
                        msg = f"✅ Silence created (duration {duration}){f' id={silence_id}' if silence_id else ''}"
                    else:
                        msg = f"❌ Failed to create silence: HTTP {resp.status} {data}"
            else:
                # No Alertmanager API configured → backend mute is unavailable
                msg = "❌ Cannot create silence: Alertmanager API is not configured"

            # Answer the callback and post result to thread
            await self._answer_callback(callback_id)
            thread_identifier = incident_.thread_id if incident_.thread_id else incident_.ts
            await self.post_thread_reply(incident_.channel_id, thread_identifier, msg)
        except Exception as e:
            logger.error(f"Failed to create silence: {e}")
            await self._answer_callback(callback_id)
            thread_identifier = incident_.thread_id if incident_.thread_id else incident_.ts
            await self.post_thread_reply(incident_.channel_id, thread_identifier, f"❌ Failed to create silence: {e}")

    async def _handle_panel_screenshot(self, incident_, callback_id):
        """Обрабатывает запрос на скриншот панели"""
        start_time = time.time()
        try:
            # Проверяем rate limiting
            can_render, message = self._can_render_panel(incident_.uuid)
            if not can_render:
                await self._answer_callback(callback_id, message)
                return
            
            # Получаем данные алерта
            alert_data = incident_.last_state or {}
            if not alert_data:
                await self._answer_callback(callback_id, 'Нет данных алерта для скриншота')
                return
            
            # Проверяем наличие URL панели
            panel_url = self._extract_panel_url(alert_data)
            if not panel_url:
                await self._answer_callback(callback_id, 'URL панели не найден в данных алерта')
                return
            
            # Отвечаем на callback
            await self._answer_callback(callback_id, 'Генерирую скриншот панели...')
            
            # Отмечаем начало рендеринга
            self._start_rendering(incident_.uuid)
            
            # Обновляем клавиатуру для отображения неактивной кнопки
            await self._update_screenshot_button_state(incident_)
            
            try:
                # Обновляем время последнего рендеринга
                self._update_render_time(incident_.uuid)
                
                # Получаем ID основного сообщения для реплая
                thread_identifier = incident_.thread_id if incident_.thread_id else incident_.ts
                main_message_id = self._get_main_message_id(thread_identifier)
                
                # Рендерим и отправляем скриншот
                render_start_time = time.time()
                message_id = await self.render_and_send_panel(
                    incident_.channel_id, 
                    alert_data, 
                    "📊 Скриншот панели Grafana",
                    reply_to_message_id=main_message_id
                )
                render_end_time = time.time()
                
                # Логируем время генерации
                total_time = render_end_time - start_time
                render_time = render_end_time - render_start_time
                logger.info(f"Скриншот панели для инцидента {incident_.uuid}: общее время={total_time:.2f}s, рендеринг={render_time:.2f}s")
                
                if message_id:
                    # Удаляем предыдущее сообщение с изображением только после успешного получения нового
                    await self._delete_previous_screenshot(incident_)
                    
                    # Сохраняем ID нового сообщения с изображением в инциденте
                    self._save_screenshot_message_id(incident_, message_id)
                    logger.info(f"Скриншот панели успешно отправлен для инцидента {incident_.uuid}")
                else:
                    # Отправляем сообщение об ошибке как реплай к основному сообщению
                    await self.post_thread_reply(incident_.channel_id, thread_identifier, "❌ Не удалось сгенерировать скриншот панели")
                    
            finally:
                # Всегда отмечаем окончание рендеринга
                self._finish_rendering(incident_.uuid)
                # Обновляем клавиатуру для отображения активной кнопки
                await self._update_screenshot_button_state(incident_)
                
        except Exception as e:
            logger.error(f"Ошибка при обработке скриншота панели: {e}")
            await self._answer_callback(callback_id, f"Ошибка: {e}")
            # Убеждаемся, что состояние рендеринга сброшено
            self._finish_rendering(incident_.uuid)
            # Обновляем клавиатуру для отображения активной кнопки
            await self._update_screenshot_button_state(incident_)

    def _extract_panel_url(self, alert_data):
        """Извлекает URL панели из данных алерта"""
        try:
            # Ищем URL панели в разных местах структуры алерта
            if 'panelURL' in alert_data:
                return alert_data['panelURL']
            elif 'alerts' in alert_data and alert_data['alerts']:
                first_alert = alert_data['alerts'][0]
                if 'panelURL' in first_alert:
                    return first_alert['panelURL']
            return None
        except Exception as e:
            logger.error(f"Ошибка при извлечении URL панели: {e}")
            return None

    def _get_main_message_id(self, thread_identifier):
        """Получает ID основного сообщения для реплая"""
        try:
            # Для форумов: thread_identifier = "topic_id/message_id"
            # Для обычных чатов: thread_identifier = "message_id"
            if '/' in str(thread_identifier):
                _, message_id = str(thread_identifier).split('/', 1)
                return int(message_id)
            else:
                return int(thread_identifier)
        except (ValueError, AttributeError):
            return None

    async def _delete_previous_screenshot(self, incident_):
        """Удаляет предыдущее сообщение с изображением"""
        try:
            screenshot_message_id = getattr(incident_, 'screenshot_message_id', None)
            if screenshot_message_id:
                await self.delete_message(incident_.channel_id, screenshot_message_id)
                incident_.screenshot_message_id = None
                incident_.dump()
        except Exception as e:
            logger.error(f"Ошибка при удалении предыдущего скриншота: {e}")

    def _save_screenshot_message_id(self, incident_, message_id):
        """Сохраняет ID сообщения с изображением в инциденте"""
        try:
            incident_.screenshot_message_id = message_id
            incident_.dump()
        except Exception as e:
            logger.error(f"Ошибка при сохранении ID сообщения с изображением: {e}")

    def _create_thread_payload(self, chat_id, body, header, status_icons, status):
        # Build silence button - prefer URL button if available; fallback to callback button to keep it visible
        silence_button = self._get_silence_button() or buttons['silence']['mute']
        
        # Build keyboard as 3 rows to avoid overflow on mobile Telegram
        # Row 1: Take/Release + Notifications; Row 2: Mute (if available) + Screenshot; Row 3: Screenshot (if Mute not available)
        row1 = [buttons['chain']['takeit'], buttons['status']['enabled']]
        keyboard = [row1]
        
        row2 = []
        if silence_button is not None:
            row2.append(silence_button)
        
        # Отладочная информация для кнопки скриншота
        logger.debug(f"Проверка кнопки скриншота: render_enabled={self.render_enabled}, grafana_renderer={self.grafana_renderer is not None}")
        if self.render_enabled and self.grafana_renderer:
            row2.append(buttons['panel']['screenshot'])
            logger.debug("Добавлена кнопка Screenshot в row2")
        
        if row2:
            keyboard.append(row2)
            logger.debug(f"Добавлена строка клавиатуры: {row2}")
        elif self.render_enabled and self.grafana_renderer:
            # Если нет кнопки Mute, но есть рендерер, добавляем Screenshot в отдельную строку
            keyboard.append([buttons['panel']['screenshot']])
            logger.debug("Добавлена отдельная строка с кнопкой Screenshot")
        
        payload = {
            'chat_id': chat_id,
            'text': f'{self._format_tg_icon(status_icons)} {header}\n{body}',
            'parse_mode': 'HTML',
            'reply_markup': {
                'inline_keyboard': keyboard
            }
        }
        
        logger.debug(f'Created thread payload: {payload}')
        return payload

    def _post_thread_payload(self, channel_id, id_, text):
        chat_id, _ = self._parse_channel_id(channel_id)
        
        # Handle both forum topic messages and regular messages
        if '/' in str(id_):
            topic_id, _ = id_.split('/', 1)
            return {
                'chat_id': chat_id,
                'text': text,
                'message_thread_id': topic_id,
                'parse_mode': 'HTML'
            }
        else:
            # For regular messages (not in forum topics)
            return {
                'chat_id': chat_id,
                'text': text,
                'parse_mode': 'HTML'
            }

    def _post_thread_reply_payload(self, channel_id, id_, text):
        chat_id, _ = self._parse_channel_id(channel_id)
        
        # Handle both forum topic messages and regular messages
        if '/' in str(id_):
            topic_id, message_id = id_.split('/', 1)
            return {
                'chat_id': chat_id,
                'text': text,
                'message_thread_id': topic_id,
                'reply_to_message_id': message_id,
                'parse_mode': 'HTML'
            }
        else:
            # For regular messages (not in forum topics)
            return {
                'chat_id': chat_id,
                'text': text,
                'reply_to_message_id': id_,
                'parse_mode': 'HTML'
            }

    async def update_thread(self, channel_id, id_, status, body, header, status_icons, chain_enabled=True,
                      status_enabled=True, incident=None):
        # Check if channel_id contains a fixed topic_id
        _, fixed_topic_id = self._parse_channel_id(channel_id)
        
        # Only update topic name if no fixed topic_id is specified in channel_id (нефиксированный топик)
        if not fixed_topic_id:
            # Always update topic with the correct status icon based on the current status
            await self._update_topic(channel_id, id_, header, status_icons, incident)
        
        # If incident is closed, remove inline keyboard before updating text
        if status == 'closed':
            await self._remove_reply_markup(channel_id, id_)

        payload = self.update_thread_payload(channel_id, id_, body, header, status_icons, status, chain_enabled,
                                             status_enabled)
        await self._update_thread(id_, payload)



    async def _update_topic(self, channel_id, id_, header, status_icons, incident=None):
        chat_id, fixed_topic_id = self._parse_channel_id(channel_id)
        
        # Extract topic_id from id_ (could be "topic_id/message_id" or just "message_id")
        topic_id = None
        if '/' in str(id_):
            topic_id, _ = id_.split('/', 1)
        else:
            # If id_ is just message_id, try to get topic_id from incident
            if incident and hasattr(incident, 'thread_id') and incident.thread_id and '/' in str(incident.thread_id):
                topic_id, _ = incident.thread_id.split('/', 1)
                logger.debug(f'Got topic_id from incident.thread_id: {topic_id}')
            elif fixed_topic_id:
                # If channel_id contains a fixed topic_id, use it
                topic_id = fixed_topic_id
                logger.debug(f'Using fixed topic_id from channel_id: {topic_id}')
            else:
                # Try to find topic by message_id (last resort)
                topic_id = await self._find_topic_by_message_id(chat_id, id_)
                if topic_id:
                    logger.debug(f'Found topic_id by message_id: {topic_id}')
                else:
                    logger.debug(f'Cannot update topic: id_ does not contain topic_id and no valid incident.thread_id: {id_}')
                    return
            
        if topic_id:
            payload = {
                'chat_id': chat_id,
                'name': header,
                'icon_custom_emoji_id': status_icons,
                'message_thread_id': topic_id
            }
            logger.debug(f'Updating topic {topic_id}: header="{header}", status_icons="{status_icons}"')
            try:
                async with self.http.post(
                    f'{self.url}/editForumTopic',
                    json=payload,
                    headers=self.headers
                ) as response:
                    response_json = await response.json()
                    if response_json.get('ok'):
                        logger.debug(f'Successfully updated topic {topic_id}')
                    else:
                        logger.warning(f'Failed to update topic {topic_id}: {response_json}')
            except aiohttp.ClientError as e:
                logger.error(f'Failed to update topic: {e}')

    async def _find_topic_by_message_id(self, chat_id, message_id):
        """
        Try to find topic_id by searching for a message in the chat.
        This is a fallback method when thread_id is not available.
        """
        try:
            # Get chat history to find the message and its topic
            payload = {
                'chat_id': chat_id,
                'limit': 100,  # Get last 100 messages
                'offset': 0
            }
            
            async with self.http.post(
                f'{self.url}/getUpdates',
                json=payload,
                headers=self.headers
            ) as response:
                response_json = await response.json()
                
                if not response_json.get('ok'):
                    logger.debug(f'Failed to get chat history: {response_json}')
                    return None
                
                # Look for the message in the history
                messages = response_json.get('result', [])
                for message in messages:
                    if message.get('message', {}).get('message_id') == int(message_id):
                        topic_id = message.get('message', {}).get('message_thread_id')
                        if topic_id:
                            logger.debug(f'Found topic_id {topic_id} for message_id {message_id}')
                            return str(topic_id)
                
                logger.debug(f'Message {message_id} not found in chat history')
                return None
                
        except Exception as e:
            logger.debug(f'Failed to find topic by message_id: {e}')
            return None

    def update_thread_payload(self, channel_id, id_, body, header, status_icons, status, chain_enabled,
                              status_enabled):
        chat_id, _ = self._parse_channel_id(channel_id)
        
        # Handle both forum topic messages and regular messages
        if '/' in str(id_):
            _, message_id = id_.split('/', 1)
        else:
            message_id = id_
        
        message_text = f'{self._format_tg_icon(status_icons)} {header}\n{body}'
        
        # Build silence button - prefer URL button if available; fallback to callback button to keep it visible
        silence_button = self._get_silence_button() or buttons['silence']['mute']
        
        # Build keyboard as 3 rows to avoid overflow on mobile Telegram
        # For chain button: show "Release" if incident is assigned to someone, otherwise show "Take IT" if chain is enabled
        current_incident = getattr(self, '_current_incident_for_keyboard', None)
        is_assigned = current_incident and current_incident.assigned_user_id and current_incident.assigned_user_id != ""
        
        chain_button = buttons['chain']['release'] if is_assigned else (buttons['chain']['takeit'] if chain_enabled else buttons['chain']['takeit'])
        
        row1 = [
            chain_button,
            buttons['status']['enabled'] if status_enabled else buttons['status']['disabled']
        ]
        keyboard = [row1]
        
        row2 = []
        if silence_button is not None:
            row2.append(silence_button)
        
        # Отладочная информация для кнопки скриншота
        logger.debug(f"Проверка кнопки скриншота: render_enabled={self.render_enabled}, grafana_renderer={self.grafana_renderer is not None}")
        if self.render_enabled and self.grafana_renderer:
            # Проверяем, не идет ли рендеринг для текущего инцидента
            current_incident = getattr(self, '_current_incident_for_keyboard', None)
            is_rendering = current_incident and current_incident.uuid in self._rendering_in_progress
            
            if is_rendering:
                # Создаем неактивную кнопку во время рендеринга
                disabled_screenshot_button = {
                    'text': '⏳ Рендеринг...',
                    'callback_data': 'panel_screenshot_disabled'
                }
                row2.append(disabled_screenshot_button)
                logger.debug("Добавлена неактивная кнопка Screenshot (рендеринг в процессе)")
            else:
                row2.append(buttons['panel']['screenshot'])
                logger.debug("Добавлена кнопка Screenshot в row2")
        
        if row2:
            keyboard.append(row2)
            logger.debug(f"Добавлена строка клавиатуры: {row2}")
        elif self.render_enabled and self.grafana_renderer:
            # Если нет кнопки Mute, но есть рендерер, добавляем Screenshot в отдельную строку
            current_incident = getattr(self, '_current_incident_for_keyboard', None)
            is_rendering = current_incident and current_incident.uuid in self._rendering_in_progress
            
            if is_rendering:
                disabled_screenshot_button = {
                    'text': '⏳ Рендеринг...',
                    'callback_data': 'panel_screenshot_disabled'
                }
                keyboard.append([disabled_screenshot_button])
                logger.debug("Добавлена отдельная строка с неактивной кнопкой Screenshot")
            else:
                keyboard.append([buttons['panel']['screenshot']])
                logger.debug("Добавлена отдельная строка с кнопкой Screenshot")
        
        payload = {
            'chat_id': chat_id,
            'message_id': message_id,
            'text': message_text,
            'parse_mode': 'HTML',
        }
        # Do not include buttons for closed incidents
        if status != 'closed':
            payload['reply_markup'] = {
                'inline_keyboard': keyboard
            }
        return payload

    def _extract_silence_url(self, incident=None, state=None):
        try:
            if state is None:
                state = incident.last_state if incident is not None else getattr(self, '_current_alert_state_for_keyboard', {}) or {}
            alerts = state.get('alerts') or []
            if alerts and alerts[0].get('silenceURL'):
                return alerts[0].get('silenceURL')
            # sometimes grafana payload may place silenceURL at top level
            return state.get('silenceURL')
        except Exception:
            return None

    def _is_silence_api_available(self):
        am_cfg = application.get('alertmanager', {}) or {}
        has_alertmanager_api = bool(am_cfg.get('api_url'))
        return has_alertmanager_api
                                                                                                                
    def _should_show_silence_button(self, incident=None, state=None):
        has_api = self._is_silence_api_available()
        if has_api:
            return True
        silence_url = self._extract_silence_url(incident=incident, state=state)
        return isinstance(silence_url, str) and silence_url.startswith(("http://", "https://"))

    def _get_silence_button(self):
        """
        Get the appropriate silence button:
        - If silence URL is available -> URL button that opens in browser
        - If API is available -> callback button for backend processing
        - Otherwise -> None (no button)
        """
        try:
            incident = getattr(self, '_current_incident_for_keyboard', None)
            state = getattr(self, '_current_alert_state_for_keyboard', None)
            
            logger.debug(f'Getting silence button: incident={incident is not None}, state={state is not None}')
            
            # Check if we have a silence URL available
            silence_url = self._extract_silence_url(incident=incident, state=state)
            logger.debug(f'Silence URL: {silence_url}')
            
            if silence_url and isinstance(silence_url, str) and silence_url.startswith(("http://", "https://")):
                # Use URL button that opens in browser
                logger.debug('Using URL button for silence')
                return {
                    'text': '🔇 Mute',
                    'url': silence_url
                }
            
            # Check if we have API available
            has_api = self._is_silence_api_available()
            logger.debug(f'Has API: {has_api}')
            
            if has_api:
                # Use callback button for backend processing
                logger.debug('Using callback button for silence')
                return buttons['silence']['mute']
            
            # No silence option available
            logger.debug('No silence options available')
            return None
        except Exception as e:
            logger.error(f'Error getting silence button: {e}')
            return None

    def _build_silence_button_from_state(self):
        """Build silence button:
        - If Alertmanager API or Grafana API configured -> callback button
        - Else if silenceURL present in payload -> callback button (backend will GET it)
        - Else -> None (hide button)
        """
        try:
            # We need current incident, find from context via closure: use latest built object if available
            # In this class, we don't carry incident object here, so try to access last built via attribute if set by callers
            incident = getattr(self, '_current_incident_for_keyboard', None)
            force_flag = getattr(self, '_show_silence_for_keyboard', None)
            if force_flag is None:
                decision = self._should_show_silence_button(incident=incident, state=getattr(self, '_current_alert_state_for_keyboard', None))
            else:
                decision = bool(force_flag)
            if decision:
                return buttons['silence']['mute']
            return None
        except Exception:
            return None

    async def _update_thread(self, id_, payload):
        try:
            async with self.http.post(
                f'{self.url}/editMessageText',
                json=payload,
                headers=self.headers
            ) as response:
                await asyncio.sleep(self.post_delay)
        except aiohttp.ClientError as e:
            logger.error(f'Failed to update thread: {e}')

    async def _remove_reply_markup(self, channel_id, id_):
        try:
            chat_id, _ = self._parse_channel_id(channel_id)
            # Handle both forum topic messages and regular messages
            if '/' in str(id_):
                _, message_id = id_.split('/', 1)
            else:
                message_id = id_
            payload = {
                'chat_id': chat_id,
                'message_id': message_id,
                'reply_markup': None
            }
            async with self.http.post(
                f'{self.url}/editMessageReplyMarkup',
                json=payload,
                headers=self.headers
            ) as response:
                await asyncio.sleep(self.post_delay)
        except aiohttp.ClientError as e:
            logger.error(f'Failed to remove reply markup: {e}')

    def _markdown_links_to_native_format(self, text):
        return text

    async def get_user_details(self, user_details):
        id_ = user_details.get('id')
        async with self.http.get(f'{self.url}/getChat?chat_id={id_}', headers=self.headers) as response:
            if response.status != 200:
                logger.debug(f'Failed to get user details for {id_}: HTTP {response.status}')
                return {'id': id_, 'exists': False, 'full_name': None, 'username': None}
            
            data = await response.json()
            if not data.get('ok'):
                logger.debug(f'Telegram API error for user {id_}: {data.get("description", "unknown error")}')
                return {'id': id_, 'exists': False, 'full_name': None, 'username': None}
            
            chat_data = data.get('result', {})
            first_name = chat_data.get('first_name', '').strip()
            last_name = chat_data.get('last_name', '').strip()
            full_name = f"{first_name} {last_name}".strip()
            return {'id': id_, 'exists': True, 'full_name': full_name, 'username': full_name}

    def create_user(self, name, user_details):
        return User(
            name=name,
            id_=user_details.get('id'),
            exists=user_details.get('exists', False)
        )

    async def update(self, uuid_, incident, incident_status, alert_state, updated_status, chain_enabled, status_enabled):
        """
        Override the base update method to handle status notifications properly.
        For all topics, we send a separate status notification message and update it.
        """
        body = self.body_template.form_message(alert_state, incident)
        header = self.header_template.form_message(alert_state, incident)
        # provide incident, alert_state and status for keyboard builder (scoped to this call only)
        self._current_incident_for_keyboard = incident
        self._current_alert_state_for_keyboard = alert_state
        self._current_status_for_keyboard = incident_status
        status_icons = self.status_icons_template.form_message(alert_state, incident)
        logger.debug(f'Update incident {uuid_}: status="{incident_status}", status_icons="{status_icons}"')
        
        # For Telegram we use thread_id (topic_id/message_id) for topic update
        # For other applications we use ts
        thread_identifier = incident.thread_id if incident.thread_id else incident.ts
        
        # If thread_id is missing but we have ts, try to restore thread_id
        if not incident.thread_id and incident.ts:
            logger.debug(f'Thread_id missing, attempting to restore from ts: {incident.ts}')
            chat_id, fixed_topic_id = self._parse_channel_id(incident.channel_id)
            if fixed_topic_id:
                # If channel_id contains a fixed topic_id, reconstruct thread_id
                incident.thread_id = f'{fixed_topic_id}/{incident.ts}'
                thread_identifier = incident.thread_id
                logger.debug(f'Restored thread_id from fixed topic: {incident.thread_id}')
                # Save the restored thread_id to prevent future lookups
                incident.dump()
            else:
                # Try to find topic_id by message_id
                topic_id = await self._find_topic_by_message_id(chat_id, incident.ts)
                if topic_id:
                    incident.thread_id = f'{topic_id}/{incident.ts}'
                    thread_identifier = incident.thread_id
                    logger.debug(f'Restored thread_id by message_id lookup: {incident.thread_id}')
                    # Save the restored thread_id to prevent future lookups
                    incident.dump()
                else:
                    logger.warning(f'Could not restore thread_id for message_id: {incident.ts}')
        
        # Update the main message
        await self.update_thread(
            incident.channel_id, thread_identifier, incident_status, body, header, status_icons, 
            chain_enabled, status_enabled, incident
        )
        # clear context
        for attr in ['_current_incident_for_keyboard', '_current_alert_state_for_keyboard', '_current_status_for_keyboard', '_show_silence_for_keyboard']:
            if hasattr(self, attr):
                delattr(self, attr)
        
        # Определяем тип топика (фиксированный или нефиксированный)
        _, fixed_topic_id = self._parse_channel_id(incident.channel_id)
        is_fixed_topic = fixed_topic_id is not None
        
        logger.info(f'Incident {uuid_} updated with status \'{incident_status}\' (updated_status={updated_status}, is_fixed_topic={is_fixed_topic})')
        
        if is_fixed_topic:
            # Фиксированный топик - ограниченная логика уведомлений
            if incident_status == 'resolved':
                # Remove tagging message when incident is resolved
                await self._remove_status_notification(incident, thread_identifier)
            elif incident_status == 'firing':
                # For firing status, we should tag people (let the chain handle this)
                # Don't send status notification for firing
                pass
            elif status_enabled and incident_status not in ['closed', 'firing', 'resolved']:
                # Handle other status notifications (unknown, etc.) - только при смене статуса
                if updated_status:
                    # In fixed topics, on transition to unknown, remove previous tagging messages
                    await self._remove_status_notification(incident, thread_identifier)
                    await self._handle_status_notification(incident, thread_identifier, incident_status)
            elif incident_status == 'closed':
                # Remove status notification when incident is closed
                await self._remove_status_notification(incident, thread_identifier)
        else:
            # Нефиксированный топик - полная логика уведомлений
            if incident_status == 'resolved':
                # Не удаляем сообщения в нефиксированном топике
                # Отправляем уведомление о резолве
                await self._handle_status_notification(incident, thread_identifier, incident_status)
                # Отключаем цепочку при резолве в нефиксированном топике
                incident.chain_enabled = False
                incident.dump()
                logger.debug(f'Disabled chain for non-fixed topic incident {incident.uuid} on resolved')
            elif incident_status == 'firing':
                # For firing status, we should tag people (let the chain handle this)
                # Don't send status notification for firing
                pass
            elif status_enabled and incident_status not in ['closed', 'firing', 'resolved']:
                # Handle other status notifications (unknown, etc.) - при каждом обновлении
                await self._handle_status_notification(incident, thread_identifier, incident_status)
            elif incident_status == 'closed':
                # Не удаляем сообщения в нефиксированном топике
                # Отправляем уведомление о закрытии
                await self._handle_status_notification(incident, thread_identifier, incident_status)

    async def _handle_status_notification(self, incident, thread_identifier, incident_status):
        """
        Handle status notification - update the first tagging message (user_group notification)
        """
        
        # For firing status, regular status notification is skipped; handled specially on transition
        if incident_status == 'firing':
            logger.debug(f'Incident {incident.uuid} firing - status notification handled on transition')
            return

        # Determine if this is a fixed topic
        _, fixed_topic_id = self._parse_channel_id(incident.channel_id)
        is_fixed_topic = fixed_topic_id is not None

        text_template = JinjaTemplate(update_status)
        admins = self.get_notification_destinations()
        fields = {'type': self.type, 'status': incident_status, 'admins': admins}
        status_notification = text_template.form_notification(fields)

        # In fixed topics, augment unknown status with group/user tagging derived from chain
        if is_fixed_topic and incident_status == 'unknown':
            tag_text = await self._compose_chain_tag_text(incident)
            if tag_text:
                status_notification = f"{status_notification}  |  {tag_text}"
        
        # Check if we already have a status notification message ID stored
        status_message_id = getattr(incident, 'status_notification_message_id', None)
        
        if is_fixed_topic:
            # In fixed topics we replace (edit) one status message
            if status_message_id:
                await self._update_status_notification(incident.channel_id, thread_identifier, status_message_id, status_notification)
            else:
                message_id = await self.post_thread_reply(incident.channel_id, thread_identifier, status_notification)
                if message_id:
                    incident.status_notification_message_id = message_id
                    incident.dump()
        else:
            # In non-fixed topics we always append a new status message (never edit or delete)
            message_id = await self.post_thread_reply(incident.channel_id, thread_identifier, status_notification)
            if message_id:
                # track as additional tagging message id
                if not hasattr(incident, 'tagging_message_ids'):
                    incident.tagging_message_ids = []
                if message_id not in incident.tagging_message_ids:
                    incident.tagging_message_ids.append(message_id)
                # Do not overwrite status_notification_message_id to avoid later edits
                incident.dump()

    async def _compose_chain_tag_text(self, incident):
        """Compose tagging text based on the first pending notify step in chain."""
        try:
            # Prefer first not-done user_group/user step
            pending_steps = [s for s in getattr(incident, 'chain', []) if not s.get('done')]
            target = None
            for s in pending_steps:
                if s.get('type') in ('user_group', 'user'):
                    target = s
                    break
            if not target:
                return None

            destinations = self.get_notification_destinations()
            if target['type'] == 'user_group':
                unit = self.user_groups.get(target['identifier'])
                text_template = JinjaTemplate(notification_user_group)
                fields = {'type': self.type, 'name': target['identifier'], 'unit': unit, 'admins': destinations}
                return text_template.form_notification(fields)
            else:
                unit = self.users.get(target['identifier'])
                text_template = JinjaTemplate(notification_user)
                fields = {'type': self.type, 'name': target['identifier'], 'unit': unit, 'admins': destinations}
                return text_template.form_notification(fields)
        except Exception as e:
            logger.warning(f'Failed to compose chain tag text for incident {incident.uuid}: {e}')
            return None

    async def post_status_firing_transition(self, incident):
        """Post or update a combined firing status message with chain tagging on transition to firing."""
        try:
            # Base status text with link handled by update_status template
            text_template = JinjaTemplate(update_status)
            admins = self.get_notification_destinations()
            fields = {'type': self.type, 'status': 'firing', 'admins': admins}
            status_text = text_template.form_notification(fields)

            tag_text = await self._compose_chain_tag_text(incident)
            if tag_text:
                message_text = f"{status_text}  |  {tag_text}"
            else:
                message_text = status_text

            thread_identifier = incident.thread_id if incident.thread_id else incident.ts
            _, fixed_topic_id = self._parse_channel_id(incident.channel_id)
            is_fixed_topic = fixed_topic_id is not None

            if is_fixed_topic:
                # Replace existing status message if present, otherwise create
                status_message_id = getattr(incident, 'status_notification_message_id', None)
                if status_message_id:
                    await self._update_status_notification(incident.channel_id, thread_identifier, status_message_id, message_text)
                else:
                    message_id = await self.post_thread_reply(incident.channel_id, thread_identifier, message_text)
                    if message_id:
                        incident.status_notification_message_id = message_id
                        incident.dump()
            else:
                # Append a new message for non-fixed topics
                message_id = await self.post_thread_reply(incident.channel_id, thread_identifier, message_text)
                if message_id:
                    if not hasattr(incident, 'tagging_message_ids'):
                        incident.tagging_message_ids = []
                    if message_id not in incident.tagging_message_ids:
                        incident.tagging_message_ids.append(message_id)
                    incident.dump()
        except Exception as e:
            logger.error(f'Failed to post firing transition message for incident {incident.uuid}: {e}')

    async def _update_status_notification(self, channel_id, thread_identifier, message_id, text):
        """
        Update existing status notification message
        """
        try:
            chat_id, _ = self._parse_channel_id(channel_id)
            payload = {
                'chat_id': chat_id,
                'message_id': message_id,
                'text': text,
                'parse_mode': 'HTML'
            }
            
            async with self.http.post(
                f'{self.url}/editMessageText',
                json=payload,
                headers=self.headers
            ) as response:
                await asyncio.sleep(self.post_delay)
                logger.debug(f'Updated status notification message {message_id}')
                
        except aiohttp.ClientError as e:
            logger.error(f'Failed to update status notification: {e}')

    async def _remove_status_notification(self, incident, thread_identifier):
        """
        Remove all tagging messages when incident is resolved
        """
        try:
            chat_id, _ = self._parse_channel_id(incident.channel_id)
            
            # Get all tagging message IDs
            tagging_message_ids = getattr(incident, 'tagging_message_ids', [])
            if not tagging_message_ids:
                logger.debug(f'No tagging messages to remove for incident {incident.uuid}')
                return
            
            logger.debug(f'Removing {len(tagging_message_ids)} tagging messages for incident {incident.uuid}')
            
            # Delete each tagging message with retry logic
            for message_id in tagging_message_ids:
                await self._delete_message_with_retry(chat_id, message_id)
            
            # Clear the stored message IDs
            incident.status_notification_message_id = None
            incident.tagging_message_ids = []
            incident.dump()
            logger.debug(f'Cleared all tagging message IDs for incident {incident.uuid}')
                    
        except Exception as e:
            logger.error(f'Failed to remove status notifications: {e}')

    async def _delete_message_with_retry(self, chat_id, message_id, max_retries=3, retry_delay=1):
        """
        Delete message with retry logic for handling temporary API errors
        """
        for attempt in range(max_retries):
            try:
                payload = {
                    'chat_id': chat_id,
                    'message_id': message_id
                }
                
                async with self.http.post(
                    f'{self.url}/deleteMessage',
                    json=payload,
                    headers=self.headers
                ) as response:
                    await asyncio.sleep(self.post_delay)
                    response_json = await response.json()
                    
                    if response_json.get('ok'):
                        logger.debug(f'Deleted tagging message {message_id}')
                        return True
                    else:
                        error_code = response_json.get('error_code', 0)
                        error_desc = response_json.get('description', 'Unknown error')
                        
                        # Check if it's a retryable error
                        if error_code in [502, 503, 504, 429] and attempt < max_retries - 1:
                            logger.warning(f'Failed to delete tagging message {message_id} (attempt {attempt + 1}/{max_retries}): {error_desc}. Retrying in {retry_delay}s...')
                            await asyncio.sleep(retry_delay)
                            retry_delay *= 2  # Exponential backoff
                            continue
                        else:
                            logger.warning(f'Failed to delete tagging message {message_id}: {response_json}')
                            return False
                            
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f'Failed to delete tagging message {message_id} (attempt {attempt + 1}/{max_retries}): {e}. Retrying in {retry_delay}s...')
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    logger.error(f'Failed to delete tagging message {message_id} after {max_retries} attempts: {e}')
                    return False
        
        return False

    async def _remove_screenshot_messages(self, incident):
        """Удаляет все сообщения с изображениями при закрытии инцидента"""
        try:
            screenshot_message_id = getattr(incident, 'screenshot_message_id', None)
            if screenshot_message_id:
                await self.delete_message(incident.channel_id, screenshot_message_id)
                incident.screenshot_message_id = None
                incident.dump()
                logger.info(f"Удалено сообщение с изображением для инцидента {incident.uuid}")
        except Exception as e:
            logger.error(f"Ошибка при удалении сообщений с изображениями: {e}")

    async def post_assignment_notification(self, incident_obj, user_id, user_display_name=None):
        """
        Post a notification message to the thread when a user is assigned to an incident.
        For fixed topics, we can optionally embed this in the main message.
        
        Args:
            incident_obj: The incident object
            user_id: The user ID that was assigned
        """
        if not user_id:
            return
            
        try:
            user_mention = self.format_user_mention(user_id, user_display_name)
            message = f"update: assigned to {user_mention}"
            
            # Check if this is a fixed topic
            _, fixed_topic_id = self._parse_channel_id(incident_obj.channel_id)
            
            if fixed_topic_id:
                # For fixed topics, we could update the main message to include assignment
                # This is optional and can be controlled by a config flag
                logger.debug(f'Fixed topic detected for incident {incident_obj.uuid}, assignment notification could be embedded')
                # For now, still send as separate message for fixed topics
                # TODO: Implement embedded assignment notifications if needed
            
            # For Telegram we use thread_id (topic_id/message_id) for sending messages
            thread_identifier = incident_obj.thread_id if incident_obj.thread_id else incident_obj.ts
            
            if fixed_topic_id:
                # В фиксированном топике не отправляем уведомления о назначении
                logger.debug(f'Assignment notification disabled for fixed topic incident {incident_obj.uuid}: {message}')
            else:
                # В нефиксированном топике отправляем уведомления о назначении
                message_id = await self.post_thread(incident_obj.channel_id, thread_identifier, message)
                logger.debug(f'Assignment notification sent for non-fixed topic incident {incident_obj.uuid}: {message}')
                
                # Store the message ID for tracking
                if message_id:
                    incident_obj.status_notification_message_id = message_id
                    # Add to tagging message IDs list for non-fixed topics
                    if not hasattr(incident_obj, 'tagging_message_ids'):
                        incident_obj.tagging_message_ids = []
                    if message_id not in incident_obj.tagging_message_ids:
                        incident_obj.tagging_message_ids.append(message_id)
                    incident_obj.dump()
            
        except Exception as e:
            logger.error(f'Failed to post assignment notification for incident {incident_obj.uuid}: {e}')

    async def notify(self, incident, notify_type, identifier):
        """
        Override the base notify method to track the first notification message ID
        for status updates and send as reply to main alert message
        """
        destinations = self.get_notification_destinations()
        if notify_type == 'user':
            unit = self.users.get(identifier)
            text_template = JinjaTemplate(notification_user)
        else:
            unit = self.user_groups.get(identifier)
            text_template = JinjaTemplate(notification_user_group)
        fields = {'type': self.type, 'name': identifier, 'unit': unit, 'admins': destinations}
        text = text_template.form_notification(fields)
        header = self.format_text_italic(self.header_template.form_message(incident.last_state, incident))
        if self.type == 'telegram':
            message = text
        else:
            message = header + '\n' + text
        
        # For Telegram we use thread_id (topic_id/message_id) for sending message
        thread_identifier = incident.thread_id if incident.thread_id else incident.ts
        
        # Suppress first chain tag after special firing transition in non-fixed topics
        if incident.status == 'firing':
            _, fixed_topic_id = self._parse_channel_id(incident.channel_id)
            is_fixed_topic = fixed_topic_id is not None
            if not is_fixed_topic and getattr(incident, 'skip_next_chain_tag', False):
                logger.debug(f"Incident {incident.uuid}: suppressing first chain tag for non-fixed firing transition")
                incident.skip_next_chain_tag = False
                incident.dump()
                return None

        # Send as reply to main alert message
        response_code = await self.post_thread_reply(incident.channel_id, thread_identifier, message)
        
        # Store the message ID of the notification for status updates
        # For firing status, always create a new tagging message (don't reuse old one)
        if incident.status == 'firing':
            # For firing, always store the new message ID (this will be a new tagging message)
            if response_code:
                incident.status_notification_message_id = response_code
                # Also add to tagging message IDs list
                if not hasattr(incident, 'tagging_message_ids'):
                    incident.tagging_message_ids = []
                if response_code not in incident.tagging_message_ids:
                    incident.tagging_message_ids.append(response_code)
                incident.dump()
        else:
            # For other statuses, always store the message ID for non-fixed topics
            # For fixed topics, only store if we don't have one yet
            _, fixed_topic_id = self._parse_channel_id(incident.channel_id)
            is_fixed_topic = fixed_topic_id is not None
            
            if not is_fixed_topic or not hasattr(incident, 'status_notification_message_id') or not incident.status_notification_message_id:
                if response_code:
                    incident.status_notification_message_id = response_code
                    # For non-fixed topics, also add to tagging message IDs list
                    if not is_fixed_topic:
                        if not hasattr(incident, 'tagging_message_ids'):
                            incident.tagging_message_ids = []
                        if response_code not in incident.tagging_message_ids:
                            incident.tagging_message_ids.append(response_code)
                    incident.dump()
        
        logger.info(f'Incident {incident.uuid} -> chain step {notify_type} \'{identifier}\'')
        return response_code

    async def post_thread(self, channel_id, id_, text):
        """
        Override the base post_thread method to return message_id for tracking
        """
        payload = self._post_thread_payload(channel_id, id_, text)
        async with self.http.post(self.post_message_url, headers=self.headers, json=payload) as response:
            await asyncio.sleep(self.post_delay)
            response_json = await response.json()
            # Return message_id for tracking
            message_id = response_json.get('result', {}).get('message_id')
            return message_id

    async def post_thread_reply(self, channel_id, id_, text):
        """
        Send message as reply to main alert message
        """
        payload = self._post_thread_reply_payload(channel_id, id_, text)
        async with self.http.post(self.post_message_url, headers=self.headers, json=payload) as response:
            await asyncio.sleep(self.post_delay)
            response_json = await response.json()
            # Return message_id for tracking
            message_id = response_json.get('result', {}).get('message_id')
            return message_id

    async def post_alert_update_notification(self, incident_obj, new_alerts_f, new_alerts_r, experimental_recreate):
        """
        Post a notification about new firing alerts or resolved alerts.
        For fixed topics, we can optionally embed this in the main message.
        
        Args:
            incident_obj: The incident object
            new_alerts_f: Whether new alerts are firing
            new_alerts_r: Whether some alerts are resolved
            experimental_recreate: Whether chain recreation is enabled
        """
        try:
            fields = {
                'type': self.type,
                'firing': new_alerts_f,
                'resolved': new_alerts_r,
                'recreate': experimental_recreate
            }
            text_template = JinjaTemplate(update_alerts)
            message = text_template.form_notification(fields)
            
            # Check if this is a fixed topic
            _, fixed_topic_id = self._parse_channel_id(incident_obj.channel_id)
            
            if fixed_topic_id:
                # For fixed topics, we could update the main message to include alert updates
                # This is optional and can be controlled by a config flag
                logger.debug(f'Fixed topic detected for incident {incident_obj.uuid}, alert update notification could be embedded')
                # For now, still send as separate message for fixed topics
                # TODO: Implement embedded alert update notifications if needed
            
            # For Telegram we use thread_id (topic_id/message_id) for sending messages
            thread_identifier = incident_obj.thread_id if incident_obj.thread_id else incident_obj.ts
            await self.post_thread(incident_obj.channel_id, thread_identifier, message)
            logger.debug(f'Posted alert update notification for incident {incident_obj.uuid}: {message}')
            
        except Exception as e:
            logger.error(f'Failed to post alert update notification for incident {incident_obj.uuid}: {e}')

    async def _setup_webhook(self):
        try:
            async with self.http.post(
                f'{self.url}/setWebhook',
                params={'url': f"{application.get('impulse_address')}/app"},
                headers=self.headers
            ) as response:
                await asyncio.sleep(self.post_delay)
        except aiohttp.ClientError as e:
            logger.error(f'Failed to set webhook: {e}')
            raise e
