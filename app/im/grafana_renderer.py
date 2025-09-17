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
import json

from app.logging import logger
from config import jwt_auth_enabled, jwt_auth_kid, jwt_auth_issuer, jwt_auth_audience, jwt_auth_ttl_seconds
from config import jwt_auth_rotation_enabled, jwt_auth_rotation_interval_days, jwt_auth_grace_period_seconds, jwt_auth_max_keys, jwt_auth_keys_dir
from config import jwt_auth_mode
from config import external_jwt_env_var_name, external_jwt_http_url, external_jwt_http_method
from config import external_jwt_http_headers, external_jwt_http_body, external_jwt_http_token_json_path
from config import external_jwt_http_cache_ttl_seconds, external_jwt_http_timeout_seconds, external_jwt_http_retries, external_jwt_http_retry_backoff_ms
from config import external_jwt_clock_skew_seconds, external_jwt_allow_fallback_to_disabled
from config import panel_variables_max_values_per_var, panel_variables_max_url_length
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
        # cache for external token
        self._external_token: Optional[str] = None
        self._external_token_exp_ts: Optional[int] = None  # epoch seconds
        # panel variables configuration
        self._panel_variables_config = self._load_panel_variables_config()
    
    def _load_panel_variables_config(self) -> Dict[str, Any]:
        """Загружает конфигурацию переменных панели из настроек приложения"""
        try:
            grafana_config = application.get('grafana_renderer', {})
            panel_vars_config = grafana_config.get('panel_variables', {})
            
            # Default mapping для основных лейблов
            default_mapping = panel_vars_config.get('default_mapping', {
                'job': 'var-job',
                'instance': 'var-hostname',
                'env': 'var-env',
                'compose_service': 'var-service',
                'container_name': 'var-container',
                'maxmount': 'var-maxmount',
                'total': 'var-total',
                'interval': 'var-interval'
            })
            
            # Dashboard-specific mapping
            dashboard_specific = panel_vars_config.get('dashboard_specific', {})
            
            return {
                'default_mapping': default_mapping,
                'dashboard_specific': dashboard_specific,
                'max_values_per_var': panel_variables_max_values_per_var,
                'max_url_length': panel_variables_max_url_length
            }
        except Exception as e:
            logger.warning(f"Ошибка загрузки конфигурации переменных панели: {e}")
            return {
                'default_mapping': {},
                'dashboard_specific': {},
                'max_values_per_var': panel_variables_max_values_per_var,
                'max_url_length': panel_variables_max_url_length
            }
    
    def _collect_alert_labels(self, alert_data: Dict[str, Any]) -> Dict[str, set]:
        """
        Собирает все уникальные значения лейблов из алертов
        
        Args:
            alert_data: Данные алерта (может содержать alerts[])
            
        Returns:
            Словарь {label_name: set(unique_values)}
        """
        labels_collection = {}
        
        try:
            # Собираем лейблы из всех алертов в группе
            alerts = alert_data.get('alerts', [])
            if not alerts:
                # Если нет alerts[], берем из groupLabels/commonLabels
                group_labels = alert_data.get('groupLabels', {})
                common_labels = alert_data.get('commonLabels', {})
                all_labels = {**group_labels, **common_labels}
                for key, value in all_labels.items():
                    if value and str(value).strip():
                        if key not in labels_collection:
                            labels_collection[key] = set()
                        labels_collection[key].add(str(value).strip())
            else:
                # Обрабатываем каждый алерт в группе
                for alert in alerts:
                    alert_labels = alert.get('labels', {})
                    for key, value in alert_labels.items():
                        if value and str(value).strip():
                            if key not in labels_collection:
                                labels_collection[key] = set()
                            labels_collection[key].add(str(value).strip())
            
            logger.debug(f"Собрано лейблов из алертов: {list(labels_collection.keys())}")
            return labels_collection
            
        except Exception as e:
            logger.error(f"Ошибка сбора лейблов из алертов: {e}")
            return {}
    
    def _generate_panel_variables(self, panel_info: Dict[str, Any], alert_labels: Dict[str, set]) -> Dict[str, list]:
        """
        Генерирует переменные панели на основе лейблов алертов
        
        Args:
            panel_info: Информация о панели (dashboard_id, panel_id)
            alert_labels: Собранные лейблы {label_name: set(unique_values)}
            
        Returns:
            Словарь {var_name: [values]} для добавления в URL
        """
        try:
            dashboard_id = panel_info.get('dashboard_id')
            panel_id = panel_info.get('panel_id')
            
            # Выбираем конфигурацию: dashboard-specific или default
            mapping = self._panel_variables_config['default_mapping'].copy()
            if dashboard_id and dashboard_id in self._panel_variables_config['dashboard_specific']:
                mapping.update(self._panel_variables_config['dashboard_specific'][dashboard_id])
                logger.debug(f"Используется dashboard-specific mapping для {dashboard_id}")
            
            panel_vars = {}
            max_values = self._panel_variables_config['max_values_per_var']
            
            for label_name, values_set in alert_labels.items():
                if label_name in mapping:
                    var_name = mapping[label_name]
                    
                    # Конвертируем set в отсортированный список
                    values_list = sorted(list(values_set))
                    
                    # Ограничиваем количество значений
                    if len(values_list) > max_values:
                        logger.warning(f"Превышено максимальное количество значений для {var_name}: {len(values_list)} > {max_values}, обрезаем")
                        values_list = values_list[:max_values]
                    
                    # Фильтруем пустые и недопустимые значения
                    filtered_values = []
                    for value in values_list:
                        if value and str(value).strip() and len(str(value)) < 1000:  # разумное ограничение длины
                            filtered_values.append(str(value).strip())
                    
                    if filtered_values:
                        panel_vars[var_name] = filtered_values
                        logger.debug(f"Добавлена переменная {var_name} с {len(filtered_values)} значениями: {filtered_values[:3]}{'...' if len(filtered_values) > 3 else ''}")
            
            return panel_vars
            
        except Exception as e:
            logger.error(f"Ошибка генерации переменных панели: {e}")
            return {}
    
    def _build_multi_value_params(self, panel_vars: Dict[str, list]) -> str:
        """
        Строит строку параметров с множественными значениями
        
        Args:
            panel_vars: Словарь {var_name: [values]}
            
        Returns:
            Строка параметров для URL
        """
        try:
            params = []
            max_url_length = self._panel_variables_config['max_url_length']
            
            for var_name, values in panel_vars.items():
                for value in values:
                    # Кодируем каждый параметр отдельно
                    encoded_name = urllib.parse.quote(var_name, safe='')
                    encoded_value = urllib.parse.quote(str(value), safe='')
                    params.append(f"{encoded_name}={encoded_value}")
            
            result = '&'.join(params)
            
            # Проверяем длину URL
            if len(result) > max_url_length:
                logger.warning(f"URL параметры превышают максимальную длину: {len(result)} > {max_url_length}")
                # Обрезаем до максимальной длины, сохраняя целостность параметров
                truncated = result[:max_url_length]
                last_ampersand = truncated.rfind('&')
                if last_ampersand > 0:
                    result = truncated[:last_ampersand]
                else:
                    result = truncated
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка построения параметров с множественными значениями: {e}")
            return ""
        
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
    
    def _build_correct_panel_url(self, panel_info: Dict[str, Any], alert_data: Dict[str, Any], alert_ts: int = None, auth_token: Optional[str] = None) -> str:
        """
        Строит корректную ссылку на панель с переменными из алерта
        
        Args:
            panel_info: Информация о панели
            alert_data: Полные данные алерта (содержит alerts[], groupLabels, etc.)
            alert_ts: Время срабатывания алерта (timestamp)
            auth_token: JWT токен для авторизации (опционально)
            
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
            
            # Собираем лейблы из алертов и генерируем переменные панели
            alert_labels = self._collect_alert_labels(alert_data)
            panel_vars = self._generate_panel_variables(panel_info, alert_labels)
            
            # Добавляем переменные панели к базовым параметрам
            if panel_vars:
                multi_value_params = self._build_multi_value_params(panel_vars)
                if multi_value_params:
                    # Добавляем к существующим параметрам
                    existing_params = urllib.parse.urlencode(params)
                    if existing_params:
                        params_string = f"{existing_params}&{multi_value_params}"
                    else:
                        params_string = multi_value_params
                else:
                    params_string = urllib.parse.urlencode(params)
            else:
                params_string = urllib.parse.urlencode(params)
            
            # Дополнительные параметры для корректного отображения
            additional_params = {
                'timezone': 'browser',
                'refresh': '15s'
            }
            
            # Добавляем auth_token, если он предоставлен
            if auth_token:
                additional_params['auth_token'] = auth_token
            
            # Добавляем дополнительные параметры к строке параметров
            additional_params_string = urllib.parse.urlencode(additional_params)
            if params_string:
                final_params = f"{params_string}&{additional_params_string}"
            else:
                final_params = additional_params_string

            # Строим финальный URL
            panel_url = f"{self.grafana_url}/d-solo/{dashboard_id}?{final_params}"
            
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

    def _is_token_valid(self) -> bool:
        if not self._external_token or not self._external_token_exp_ts:
            return False
        now = int(time.time())
        return now + external_jwt_clock_skew_seconds < self._external_token_exp_ts

    def _cache_external_token(self, token: str) -> None:
        self._external_token = token
        exp_ts = None
        try:
            # Try to parse exp from JWT without verification
            parts = token.split('.')
            if len(parts) == 3:
                payload_b64 = parts[1] + '==='  # pad
                payload_json = json.loads(base64.urlsafe_b64decode(payload_b64).decode('utf-8'))
                if isinstance(payload_json, dict) and payload_json.get('exp'):
                    exp_ts = int(payload_json['exp'])
        except Exception:
            exp_ts = None
        if exp_ts is None:
            # fallback to fixed ttl from config
            exp_ts = int(time.time()) + int(external_jwt_http_cache_ttl_seconds)
        # apply clock skew margin when checking validity (handled in _is_token_valid)
        self._external_token_exp_ts = exp_ts

    async def _get_external_env_token(self) -> Optional[str]:
        token = os.getenv(external_jwt_env_var_name)
        if token:
            # do not cache env token forever; re-read each time to allow rotation
            self._cache_external_token(token)
            return token
        return None

    async def _get_external_http_token(self) -> Optional[str]:
        if self._is_token_valid():
            return self._external_token
        if not external_jwt_http_url:
            return None
        headers = {}
        data = None
        try:
            if external_jwt_http_headers:
                headers = json.loads(external_jwt_http_headers)
        except Exception:
            headers = {}
        try:
            if external_jwt_http_body:
                data = json.loads(external_jwt_http_body)
        except Exception:
            data = None

        attempts = max(1, int(external_jwt_http_retries) + 1)
        backoff = max(0, int(external_jwt_http_retry_backoff_ms)) / 1000.0
        timeout = aiohttp.ClientTimeout(total=max(1, int(external_jwt_http_timeout_seconds)))

        for attempt in range(attempts):
            try:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    method = (external_jwt_http_method or 'GET').upper()
                    if method == 'POST':
                        async with session.post(external_jwt_http_url, headers=headers, json=data) as resp:
                            resp_json = await resp.json()
                    else:
                        async with session.get(external_jwt_http_url, headers=headers, params=data if isinstance(data, dict) else None) as resp:
                            resp_json = await resp.json()
                # Extract token by simple dotted path
                token = resp_json
                for part in (external_jwt_http_token_json_path or 'access_token').split('.'):
                    if isinstance(token, dict):
                        token = token.get(part)
                if isinstance(token, str) and token:
                    self._cache_external_token(token)
                    return token
            except Exception as e:
                if attempt == attempts - 1:
                    logger.warning(f"Не удалось получить внешний JWT: {e}")
                await asyncio.sleep(backoff)
        return None
    
    async def render_panel(self, panel_url: str, alert_data: Dict[str, Any], 
                          width: int = 1000, height: int = 500, alert_ts: int = None) -> Optional[bytes]:
        """
        Рендерит панель Grafana в изображение
        
        Args:
            panel_url: URL панели из алерта
            alert_data: Полные данные алерта (содержит alerts[], groupLabels, etc.)
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
            
            # Получаем auth_token в зависимости от режима
            auth_token: Optional[str] = None
            try:
                mode = (jwt_auth_mode or 'internal').lower()
                if mode == 'disabled':
                    auth_token = None
                elif mode == 'internal':
                    if jwt_auth_enabled:
                        auth_token = self._generate_grafana_auth_jwt()
                elif mode == 'external_env':
                    auth_token = await self._get_external_env_token()
                elif mode == 'external_http':
                    auth_token = await self._get_external_http_token()
                else:
                    # unknown mode -> behave as disabled or fallback if allowed
                    auth_token = None
            except Exception as e:
                logger.warning(f"Ошибка получения auth_token для Grafana: {e}")
                if not external_jwt_allow_fallback_to_disabled:
                    # proceed without token anyway
                    pass

            # Строим корректную ссылку на панель
            correct_panel_url = self._build_correct_panel_url(panel_info, alert_data, alert_ts, auth_token=auth_token)
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
            
            return await self.render_panel(panel_url, alert_data, width, height, alert_ts)
            
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
