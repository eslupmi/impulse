"""
Модуль для работы с Grafana Image Renderer.
Генерирует скриншоты панелей Grafana с правильными переменными из алертов.
"""

import asyncio
import aiohttp
import urllib.parse
import time
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timezone
import re
import jwt

from app.logging import logger
from config import jwt_auth_enabled, jwt_auth_kid, jwt_auth_issuer, jwt_auth_audience, jwt_auth_ttl_seconds
from config import jwt_auth_rotation_enabled, jwt_auth_rotation_interval_days, jwt_auth_grace_period_seconds, jwt_auth_max_keys, jwt_auth_keys_dir
from config import application, grafana_render_time_to_render
import os
import base64
from pathlib import Path
from datetime import timedelta
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend


class GrafanaRenderer:
    """Класс для работы с Grafana Image Renderer"""
    
    def __init__(self, renderer_url: str, grafana_url: str, render_key: str = None, time_to_render: int = None):
        """
        Инициализация рендерера
        
        Args:
            renderer_url: URL рендерера (например, http://renderer:8081)
            grafana_url: URL Grafana (например, http://grafana:3000)
            render_key: Ключ для рендеринга (используется и для X-Auth-Token, и для JWT секрета)
            time_to_render: Время в минутах для рендеринга (по умолчанию из конфига)
        """
        self.renderer_url = renderer_url.rstrip('/')
        self.grafana_url = grafana_url.rstrip('/')
        self.render_key = render_key
        self.time_to_render = time_to_render or grafana_render_time_to_render
    
        
    def _extract_panel_info(self, panel_url: str) -> Dict[str, Any]:
        """
        Извлекает информацию о панели из URL
        
        Args:
            panel_url: URL панели из алерта
            
        Returns:
            Словарь с информацией о панели
        """
        try:
            # Парсим URL
            parsed = urllib.parse.urlparse(panel_url)
            query_params = urllib.parse.parse_qs(parsed.query)
            
            # Извлекаем dashboard ID и panel ID
            dashboard_id = parsed.path.split('/d/')[-1].split('?')[0] if '/d/' in parsed.path else None
            panel_id = query_params.get('viewPanel', [None])[0]
            
            # Извлекаем временной диапазон
            from_time = query_params.get('from', [None])[0]
            to_time = query_params.get('to', [None])[0]
            
            return {
                'dashboard_id': dashboard_id,
                'panel_id': panel_id,
                'from_time': from_time,
                'to_time': to_time,
                'org_id': query_params.get('orgId', [None])[0]
            }
        except Exception as e:
            logger.error(f"Ошибка при парсинге URL панели {panel_url}: {e}")
            return {}
    
    def _build_correct_panel_url(self, panel_info: Dict[str, Any], alert_labels: Dict[str, str], alert_ts: int = None) -> str:
        """
        Строит корректную ссылку на панель с переменными из алерта
        
        Args:
            panel_info: Информация о панели
            alert_labels: Лейблы из алерта
            alert_ts: Время срабатывания алерта (timestamp)
            
        Returns:
            Корректная ссылка на панель
        """
        try:
            dashboard_id = panel_info.get('dashboard_id')
            panel_id = panel_info.get('panel_id')
            org_id = panel_info.get('org_id', '1')
            
            if not dashboard_id or not panel_id:
                logger.warning("Не удалось извлечь dashboard_id или panel_id")
                return ""
            
            # Базовые параметры
            params = {
                'orgId': org_id,
                'panelId': panel_id,
                'render': '1'
            }
            
            # Добавляем временной диапазон
            from_time = panel_info.get('from_time')
            to_time = panel_info.get('to_time')
            
            # Если есть время срабатывания алерта, пересчитываем временной диапазон
            if alert_ts:
                # Текущее время
                current_time = int(datetime.now(timezone.utc).timestamp() * 1000)  # в миллисекундах
                # Время начала: alert_ts - time_to_render минут
                from_time = alert_ts - (self.time_to_render * 60 * 1000)  # в миллисекундах
                # Время окончания: текущее время (не вычитаем time_to_render!)
                to_time = current_time  # в миллисекундах
                logger.debug(f"Пересчитан временной диапазон: from={from_time}, to={to_time}, alert_ts={alert_ts}, time_to_render={self.time_to_render} мин")
                logger.debug(f"Временной диапазон: {self.time_to_render} минут до срабатывания алерта до текущего времени")
            
            if from_time and to_time:
                params['from'] = from_time
                params['to'] = to_time
            
            # Добавляем переменные из лейблов алерта
            logger.debug(f"Лейблы алерта для подстановки: {alert_labels}")
            for key, value in alert_labels.items():
                if key in ['job', 'instance', 'hostname', 'interval', 'maxmount', 'total', 'Filters', 'de_job']:
                    # Экранируем значение для URL
                    encoded_value = urllib.parse.quote(str(value), safe='')
                    
                    # Специальная обработка для instance -> var-hostname
                    if key == 'instance':
                        params['var-hostname'] = encoded_value
                        logger.debug(f"Подстановка: {key}={value} -> var-hostname={encoded_value}")
                    else:
                        params[f'var-{key}'] = encoded_value
                        logger.debug(f"Подстановка: {key}={value} -> var-{key}={encoded_value}")
            
            # Дополнительные параметры для корректного отображения
            params.update({
                'timezone': 'browser',
                'refresh': '15s'
            })
            
            # Если включена JWT-авторизация Grafana, добавим auth_token в URL
            if jwt_auth_enabled:
                try:
                    auth_jwt = self._generate_grafana_auth_jwt()
                    if auth_jwt:
                        params['auth_token'] = auth_jwt
                except Exception as e:
                    logger.error(f"Не удалось сгенерировать auth_token JWT: {e}")

            # Строим URL
            query_string = urllib.parse.urlencode(params)
            panel_url = f"{self.grafana_url}/d-solo/{dashboard_id}?{query_string}"
            
            logger.info(f"Построена корректная ссылка на панель: {panel_url}")
            return panel_url
            
        except Exception as e:
            logger.error(f"Ошибка при построении ссылки на панель: {e}")
            return ""
    
    def _build_renderer_url(self, panel_url: str, width: int = 1000, height: int = 500) -> str:
        """
        Строит URL для рендерера
        
        Args:
            panel_url: URL панели Grafana (уже содержит auth_token)
            width: Ширина изображения
            height: Высота изображения
            
        Returns:
            URL для рендерера
        """
        try:
            # Параметры рендерера в правильном порядке (как в оригинальном запросе от Grafana)
            # НЕ кодируем URL панели отдельно - urlencode сделает это автоматически
            renderer_params = {
                'deviceScaleFactor': '1.000000',
                'domain': 'grafana',
                'encoding': 'png',
                'height': height,
                'timeout': '30',
                'timezone': '',
                'url': panel_url,  # Передаем URL панели без предварительного кодирования
                'width': width
            }
            
            # НЕ добавляем renderKey - он не нужен, так как auth_token уже в URL панели
            logger.debug("Используется auth_token из URL панели, renderKey не добавляется")
            
            # Строим URL рендерера - urlencode автоматически закодирует все параметры
            query_string = urllib.parse.urlencode(renderer_params)
            renderer_url = f"{self.renderer_url}/render?{query_string}"
            
            logger.debug(f"Построен URL рендерера: {renderer_url}")
            return renderer_url
            
        except Exception as e:
            logger.error(f"Ошибка при построении URL рендерера: {e}")
            return ""

    def _ensure_jwt_keys(self) -> Optional[Dict[str, Any]]:
        """Создает/читает ключи. Ротация по времени, хранение манифеста и нескольких ключей."""
        try:
            keys_dir = Path(jwt_auth_keys_dir)
            keys_dir.mkdir(parents=True, exist_ok=True)
            manifest_path = keys_dir / 'keys.json'

            import json, time
            now = int(time.time())

            # Загрузка манифеста
            manifest = {"current_kid": None, "keys": []}
            if manifest_path.exists():
                try:
                    manifest = json.loads(manifest_path.read_text())
                except Exception:
                    pass

            def write_manifest():
                manifest_path.write_text(json.dumps(manifest, ensure_ascii=False))

            # Проверка наличия текущего ключа
            current_kid = manifest.get("current_kid")
            current_entry = None
            for entry in manifest.get("keys", []):
                if entry.get("kid") == current_kid:
                    current_entry = entry
                    break

            def generate_new_key(kid_value: str) -> Dict[str, Any]:
                private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048, backend=default_backend())
                private_pem = private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption()
                )
                public_pem = private_key.public_key().public_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PublicFormat.SubjectPublicKeyInfo
                )
                (keys_dir / f"{kid_value}.private.pem").write_bytes(private_pem)
                (keys_dir / f"{kid_value}.public.pem").write_bytes(public_pem)
                return {"kid": kid_value, "created_at": now}

            # Если нет текущего ключа — создать
            if not current_entry:
                manifest["current_kid"] = jwt_auth_kid
                new_entry = generate_new_key(jwt_auth_kid)
                manifest["keys"].append(new_entry)
                write_manifest()
                current_entry = new_entry

            # Ротация по времени, если включена
            if jwt_auth_rotation_enabled:
                import datetime
                created_at = int(current_entry.get("created_at", now))
                age_days = (now - created_at) / 86400
                if age_days >= jwt_auth_rotation_interval_days:
                    # Сгенерировать новый kid на основе времени
                    new_kid = f"{jwt_auth_kid}-{now}"
                    new_entry = generate_new_key(new_kid)
                    manifest["current_kid"] = new_kid
                    manifest["keys"].append(new_entry)
                    # Обрезаем список до max_keys
                    if len(manifest["keys"]) > jwt_auth_max_keys:
                        manifest["keys"] = manifest["keys"][len(manifest["keys"]) - jwt_auth_max_keys:]
                    write_manifest()
                    current_entry = new_entry

            # Возвращаем пути к приватному ключу текущего и список публичных
            current_private = str(keys_dir / f"{manifest['current_kid']}.private.pem")
            pub_keys = []
            for entry in manifest.get("keys", []):
                pub_keys.append({
                    "kid": entry["kid"],
                    "public_path": str(keys_dir / f"{entry['kid']}.public.pem"),
                    "created_at": entry.get("created_at")
                })

            return {"private": current_private, "public_keys": pub_keys, "manifest": manifest}
        except Exception as e:
            logger.error(f"Ошибка при подготовке RSA ключей: {e}")
            return None

    def _generate_grafana_auth_jwt(self) -> Optional[str]:
        """Генерирует RS256 JWT для Grafana auth.jwt c kid и коротким TTL."""
        if not jwt_auth_enabled:
            return None
        try:
            key_paths = self._ensure_jwt_keys()
            if not key_paths:
                return None
            private_pem = Path(key_paths['private']).read_bytes()

            now = datetime.utcnow()
            payload = {
                'sub': 'impulse-user:system',
                'impulse': 'impulse',
                'iss': jwt_auth_issuer,
                'aud': jwt_auth_audience,
                'iat': int(now.timestamp()),
                'nbf': int(now.timestamp()),
                'exp': int((now + timedelta(seconds=jwt_auth_ttl_seconds)).timestamp()),
            }
            # Используем текущий kid из манифеста, если есть
            manifest = key_paths.get('manifest', {})
            current_kid = manifest.get('current_kid', jwt_auth_kid)
            headers = {'kid': current_kid}
            token = jwt.encode(payload, private_pem, algorithm='RS256', headers=headers)
            return token
        except Exception as e:
            logger.error(f"Ошибка генерации RS256 JWT: {e}")
            return None
    
    async def render_panel(self, panel_url: str, alert_labels: Dict[str, str], 
                          width: int = 1000, height: int = 500, alert_ts: int = None) -> Optional[bytes]:
        """
        Рендерит панель Grafana в изображение
        
        Args:
            panel_url: URL панели из алерта
            alert_labels: Лейблы из алерта
            width: Ширина изображения
            height: Высота изображения
            alert_ts: Время срабатывания алерта (timestamp)
            
        Returns:
            Байты изображения или None в случае ошибки
        """
        start_time = time.time()
        try:
            logger.info(f"Начало рендеринга панели: panel_url={panel_url}, alert_ts={alert_ts}, time_to_render={self.time_to_render} мин")
            
            # Извлекаем информацию о панели
            panel_info = self._extract_panel_info(panel_url)
            if not panel_info:
                logger.error("Не удалось извлечь информацию о панели")
                return None
            
            # Строим корректную ссылку на панель
            correct_panel_url = self._build_correct_panel_url(panel_info, alert_labels, alert_ts)
            if not correct_panel_url:
                logger.error("Не удалось построить корректную ссылку на панель")
                return None
            
            # Строим URL для рендерера
            renderer_url = self._build_renderer_url(correct_panel_url, width, height)
            if not renderer_url:
                logger.error("Не удалось построить URL рендерера")
                return None
            
            # Запрашиваем изображение у рендерера
            headers = {}
            if self.render_key:
                headers['X-Auth-Token'] = self.render_key
                logger.debug(f"Используется заголовок авторизации: X-Auth-Token")
            
            async with aiohttp.ClientSession() as session:
                async with session.get(renderer_url, headers=headers, timeout=aiohttp.ClientTimeout(total=60)) as response:
                    logger.debug(f"Ответ рендерера: HTTP {response.status}")
                    logger.debug(f"Заголовки ответа: {dict(response.headers)}")
                    
                    if response.status == 200:
                        # Проверяем Content-Type
                        content_type = response.headers.get('Content-Type', '')
                        logger.debug(f"Content-Type: {content_type}")
                        
                        # Проверяем Content-Length
                        content_length = response.headers.get('Content-Length')
                        if content_length:
                            logger.debug(f"Content-Length: {content_length}")
                        
                        # Читаем бинарные данные изображения
                        image_data = await response.read()
                        
                        # Проверяем, что получили данные
                        if not image_data:
                            logger.error("Получен пустой ответ от рендерера")
                            return None
                        
                        # Проверяем, что это действительно изображение
                        if not content_type.startswith('image/'):
                            logger.warning(f"Неожиданный Content-Type: {content_type}, но продолжаем обработку")
                        
                        # Проверяем магические байты изображения
                        if not self._is_valid_image_data(image_data):
                            logger.warning("Полученные данные не похожи на изображение (неверные магические байты)")
                        
                        logger.info(f"Успешно получено изображение панели, размер: {len(image_data)} байт, тип: {content_type}")
                        end_time = time.time()
                        logger.info(f"Рендеринг панели завершен за {end_time - start_time:.2f} секунд")
                        return image_data
                    else:
                        logger.error(f"Ошибка рендеринга панели: HTTP {response.status}")
                        
                        # Пытаемся прочитать текст ошибки
                        try:
                            content_type = response.headers.get('Content-Type', '')
                            if 'application/json' in content_type:
                                # Если это JSON ошибка, парсим её
                                error_json = await response.json()
                                logger.error(f"JSON ошибка от рендерера: {error_json}")
                            else:
                                # Обычный текст ошибки
                                error_text = await response.text()
                                logger.error(f"Текст ошибки от рендерера: {error_text}")
                        except Exception as e:
                            logger.error(f"Не удалось прочитать текст ошибки: {e}")
                        
                        return None
                        
        except asyncio.TimeoutError:
            logger.error("Таймаут при рендеринге панели")
            return None
        except Exception as e:
            logger.error(f"Ошибка при рендеринге панели: {e}")
            return None
    
    async def render_panel_from_alert(self, alert_data: Dict[str, Any], 
                                    width: int = 1000, height: int = 500) -> Optional[bytes]:
        """
        Рендерит панель на основе данных алерта
        
        Args:
            alert_data: JSON данные алерта
            width: Ширина изображения
            height: Высота изображения
            
        Returns:
            Байты изображения или None в случае ошибки
        """
        try:
            # Извлекаем URL панели из алерта
            panel_url = None
            
            # Ищем URL панели в разных местах структуры алерта
            if 'panelURL' in alert_data:
                panel_url = alert_data['panelURL']
            elif 'alerts' in alert_data and alert_data['alerts']:
                first_alert = alert_data['alerts'][0]
                if 'panelURL' in first_alert:
                    panel_url = first_alert['panelURL']
            
            if not panel_url:
                logger.warning("URL панели не найден в данных алерта")
                return None
            
            # Извлекаем лейблы
            labels = {}
            if 'groupLabels' in alert_data:
                labels.update(alert_data['groupLabels'])
            if 'commonLabels' in alert_data:
                labels.update(alert_data['commonLabels'])
            if 'alerts' in alert_data and alert_data['alerts']:
                first_alert = alert_data['alerts'][0]
                if 'labels' in first_alert:
                    labels.update(first_alert['labels'])
            
            # Извлекаем время срабатывания алерта
            alert_ts = None
            if 'alerts' in alert_data and alert_data['alerts']:
                first_alert = alert_data['alerts'][0]
                if 'startsAt' in first_alert:
                    # Парсим время в формате RFC3339
                    try:
                        from datetime import datetime
                        starts_at = first_alert['startsAt']
                        # Конвертируем в timestamp (миллисекунды)
                        dt = datetime.fromisoformat(starts_at.replace('Z', '+00:00'))
                        alert_ts = int(dt.timestamp() * 1000)
                        logger.debug(f"Извлечено время срабатывания алерта: {starts_at} -> {alert_ts}")
                    except Exception as e:
                        logger.warning(f"Не удалось распарсить время срабатывания алерта: {e}")
            
            logger.info(f"Рендеринг панели для алерта с лейблами: {labels}, alert_ts: {alert_ts}")
            
            return await self.render_panel(panel_url, labels, width, height, alert_ts)
            
        except Exception as e:
            logger.error(f"Ошибка при рендеринге панели из алерта: {e}")
            return None

    def _is_valid_image_data(self, data: bytes) -> bool:
        """Проверяет, что данные являются валидным изображением по магическим байтам"""
        if not data or len(data) < 4:
            return False
        
        # Проверяем магические байты для PNG
        if data.startswith(b'\x89PNG\r\n\x1a\n'):
            return True
        
        # Проверяем магические байты для JPEG
        if data.startswith(b'\xff\xd8\xff'):
            return True
        
        # Проверяем магические байты для GIF
        if data.startswith(b'GIF87a') or data.startswith(b'GIF89a'):
            return True
        
        # Проверяем магические байты для WebP
        if data.startswith(b'RIFF') and b'WEBP' in data[:12]:
            return True
        
        # Если не распознан формат, но данные есть - считаем валидным
        # (рендерер может использовать другие форматы)
        return True


def create_grafana_renderer(config: Dict[str, Any]) -> Optional[GrafanaRenderer]:
    """
    Создает экземпляр GrafanaRenderer из конфигурации
    
    Args:
        config: Конфигурация рендерера
        
    Returns:
        Экземпляр GrafanaRenderer или None
    """
    try:
        renderer_url = config.get('renderer_url')
        grafana_url = config.get('grafana_url')
        render_key = config.get('render_key')
        time_to_render = config.get('time_to_render')
        
        logger.info(f"Создание GrafanaRenderer: renderer_url={renderer_url}, grafana_url={grafana_url}, time_to_render={time_to_render}")
        
        if not renderer_url or not grafana_url:
            logger.warning("Не указаны обязательные параметры для Grafana Renderer")
            return None
        
        renderer = GrafanaRenderer(renderer_url, grafana_url, render_key, time_to_render)
        logger.info("GrafanaRenderer успешно создан")
        return renderer
        
    except Exception as e:
        logger.error(f"Ошибка при создании GrafanaRenderer: {e}")
        return None
