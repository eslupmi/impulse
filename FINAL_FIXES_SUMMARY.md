# Итоговые исправления для Telegram интеграции

## Проблемы, которые были решены

### 1. ❌ Проблема: Уведомления о статусе создавали новые сообщения
**Было:**
```
🔔 user_group devops (DmitryGuschin, AndreyMelchikhin, BagratAslamazov)

update: status unknown (https://docs.impulse.bot/latest/warnings/StatusUnknown/)  |  🔔 admins (DmitryGuschin,AndreyMelchikhin,BagratAslamazov)
```

**Стало:**
```
🔔 user_group devops (DmitryGuschin, AndreyMelchikhin, BagratAslamazov)
```
*При изменении статуса это сообщение обновляется на:*
```
update: status unknown (https://docs.impulse.bot/latest/warnings/StatusUnknown/)  |  🔔 admins (DmitryGuschin,AndreyMelchikhin,BagratAslamazov)
```

### 2. ❌ Проблема: Source отображался даже без ссылки
**Было:**
```
TEST
🔗 Source
```

**Стало:**
```
TEST
```
*Source отображается только если есть ссылка*


## Реализованные исправления

### 1. ✅ Исправлена логика уведомлений о статусе

**Изменения в `impulse/app/im/telegram/telegram_application.py`:**

- Переопределен метод `notify()` для отслеживания ID первого тегающего сообщения
- Переопределен метод `post_thread()` для возврата message_id
- Изменена логика `_handle_status_notification()` для обновления существующего сообщения
- Добавлено поле `status_notification_message_id` в класс Incident

**Логика работы:**
1. При создании алерта отправляется основное сообщение + первое тегающее сообщение (user_group)
2. ID первого тегающего сообщения сохраняется в `incident.status_notification_message_id`
3. При изменении статуса обновляется только это сообщение
4. При закрытии инцидента сообщение удаляется

### 2. ✅ Исправлено отображение Source

**Изменения в `impulse/templates/telegram_body.j2`:**

```jinja2
{%- if url or runbook %}
{% if url %}<a href="{{ url }}">🔗 Source</a>{% endif %}{% if runbook %}{% if url %}  |  {% endif %}<a href="{{ runbook }}">📖 Runbook</a>{% endif %}
{% endif -%}
```

**Логика:**
- Source отображается только если есть `generatorURL`
- Runbook отображается только если есть `runbook`
- Разделитель `|` добавляется только если есть оба


## Примеры работы

### Пример 1: Алерт с firing статусом
```
🔴 Container Down (ECHD) - Firing! 🏛️ MSR
----------------------------------------
Instance: fivegen-regs-1000-main-01 (MSR)
----------------------------------------
Контейнер platform-commander-1 упал
Проверьте контейнеры на машине
🔗 Source

🔔 user_group devops (DmitryGuschin, AndreyMelchikhin, BagratAslamazov)
```

### Пример 2: Изменение статуса на unknown
```
🔴 Container Down (ECHD) - Firing! 🏛️ MSR
----------------------------------------
Instance: fivegen-regs-1000-main-01 (MSR)
----------------------------------------
Контейнер platform-commander-1 упал
Проверьте контейнеры на машине
🔗 Source

update: status unknown (https://docs.impulse.bot/latest/warnings/StatusUnknown/)  |  🔔 admins (DmitryGuschin,AndreyMelchikhin,BagratAslamazov)
```
*Второе сообщение обновилось, первое осталось без изменений*

### Пример 3: Алерт без ссылки
```
🔴 Test Alert - Firing! 🧪 TEST
----------------------------------------
Instance: test-server
----------------------------------------
Тестовый алерт
Проверьте систему

🔔 user_group devops (DmitryGuschin, AndreyMelchikhin, BagratAslamazov)
```
*Source не отображается, так как нет ссылки*

## Файлы изменений

### Основные изменения
1. **`impulse/app/im/telegram/telegram_application.py`**
   - Переопределен метод `notify()` для отслеживания первого сообщения
   - Переопределен метод `post_thread()` для возврата message_id
   - Изменена логика обработки уведомлений о статусе

2. **`impulse/app/incident/incident.py`**
   - Добавлено поле `status_notification_message_id`

3. **`impulse/templates/telegram_header.j2`**
   - Добавлены эмодзи для TEST, DEMO, PILOT

4. **`impulse/templates/telegram_body.j2`**
   - Исправлено отображение Source (только при наличии ссылки)

### Тестовые файлы
- **`test_telegram_template.py`** - обновлен для тестирования новых функций
- **`example_telegram_message.md`** - обновлен с новыми примерами

## Результат

✅ **Уведомления о статусе больше не создают спам** - обновляется только одно сообщение
✅ **Source отображается только при наличии ссылки** - чище интерфейс



---

## Дополнения и улучшения (финальный пакет правок)

### 3. 🔕 Кнопка Mute: URL или API, только для админов
- Если в payload есть `silenceURL` (Grafana) → показываем URL‑кнопку, которая сразу открывает страницу создания silence у пользователя.
- Если настроен Alertmanager/Grafana API → работаем через callback и создаем silence с бэкенда.
- Кнопка доступна только администраторам; остальным показывается вежливая заглушка.

**Пример (URL‑кнопка):**
```json
{"text": "Mute", "url": "https://grafana.example.com/alerting/silence/new?..."}
```

### 4. 🧷 Надежные идентификаторы тем/сообщений
- Унифицирован парсинг `channel_id` и `thread_id` (поддержка `chat_id/topic_id` и обычных сообщений без `/`).
- Исправлена ошибка разбора идентификатора: «not enough values to unpack». 
- Добавлено подробное логирование ответов Telegram API на создание темы/сообщения.

### 5. ⌨️ Чистая клавиатура без `None`
- Убрана передача `None` в inline‑кнопки (фильтрация отсутствующей кнопки Mute).
- Исправлена ошибка Telegram: «InlineKeyboardButton must be an Object».

### 6. 🧵 Reply‑теги: хранение и удаление
- Тегающие сообщения теперь отправляются как reply на основное сообщение алерта.
- Сохраняются все их `message_id` в поле инцидента `tagging_message_ids`.
- При `resolved` удаляются все такие сообщения и список очищается.

**Было:** тегающие сообщения могли оставаться после резолва.

**Стало:** при `resolved` теги удаляются, при повторном `firing` создаются новые.

### 7. ♻️ Повторный firing после resolved
- Перед регенерацией цепочки удаляются старые элементы очереди шагов инцидента.
- Цепочка очищается и пересобирается, `chain_enabled` включается автоматически.
- Добавлено логирование перехода статусов и регенерации цепи.

**Логи:**
```text
Handling update: resolved -> firing
Deleting old chain steps...
Generating chain... (enabled=True)
Queue recreated
```

### 8. 🙅 Убрано лишнее сообщение «assigned to …»
- Сообщение о назначении при нажатии Take It больше не отправляется отдельно.
- Назначение видно в основном сообщении инцидента.

### 9. 🔔 Notifications ON/OFF — понятнее
- Переименованы подписи кнопок на «🟢 Notifications ON» / «🔴 Notifications OFF».
- Кнопка управляет только дополнительными статус‑уведомлениями; основное сообщение обновляется всегда.

### 10. 🪵 Расширенное debug‑логирование
- Добавлены подробные логи для: создания тем/сообщений, обработки кнопок, генерации цепочек, обновления очереди, удаления reply‑тегов, вычисления кнопки Mute.

---

## Наглядные примеры

### ▶️ Firing (первый раз)
```
🔴 Test Alert - Firing! 🧪 TEST
...
🔗 Source

🔔 user_group devops (@user1, @user2)
```

### ✅ Resolved (теги удалены)
```
✅ Test Alert - Resolved! 🧪 TEST
```

### ▶️ Firing (повторно)
```
🔴 Test Alert - Firing! 🧪 TEST
...
🔗 Source

🔔 user_group devops (@user1, @user2)
```

### 🔕 Mute (URL‑кнопка)
```
Mute → открывает страницу Grafana Silence в браузере
```

---

## Измененные файлы (ключевые)
- `impulse/app/im/telegram/telegram_application.py`
  - URL/Callback логика Mute; reply‑отправка; хранение/удаление тегающих сообщений; фильтрация кнопок; расширенное логирование.
- `impulse/app/incident/incident.py`
  - `tagging_message_ids`; включение `chain_enabled` при генерации; очистка и пересборка цепочки; сериализация/десериализация; расширенное логирование статуса/состояния.
- `impulse/app/queue/handlers/alert_handler.py`
  - Регенерация цепочки при `resolved → firing`, удаление старых шагов из очереди, логирование.
- `impulse/app/queue/queue.py`
  - Логирование операций удаления и пересоздания элементов.
- `impulse/templates/telegram_body.j2`
  - Отображение `Source`/`Runbook` только при наличии ссылок.

---

## Краткий итог
- Поведение стало предсказуемым: «firing + tag → resolved + удаление → firing + новый tag → resolved + удаление».
- Кнопка Mute работает нативно через URL или через API, доступна только админам.
- Больше спама нет: статус‑уведомления и теги ведут себя корректно, интерфейс чище, логи информативнее.


---

## Grafana JWT: внешние провайдеры, хранение ключей, кодирование URL

### 1) Режимы JWT‑авторизации для Grafana
В конфигурации добавлен переключатель режима JWT (auth.jwt) для ссылок рендеринга/панелей:

- disabled — не использовать JWT вовсе (auth_token в URL не добавляется)
- internal — генерировать токен локально (текущее поведение по умолчанию)
- external_env — брать готовый токен из ENV
- external_http — получать токен с внешнего HTTP‑провайдера

Ключевые переменные окружения:

```
GRAFANA_RENDERER_JWT_AUTH_MODE=internal|external_env|external_http|disabled
GRAFANA_RENDERER_JWT_AUTH_ENABLED=true|false               # для internal
```

### 2) Хранение ключей (internal) вне контейнера
Чтобы JWT‑ключи (internal) не терялись при пересоздании контейнера, используйте volume:

```yaml
services:
  impulse:
    image: your/impulse:latest
    environment:
      - GRAFANA_RENDERER_JWT_AUTH_MODE=internal
      - GRAFANA_RENDERER_JWT_AUTH_ENABLED=true
      - GRAFANA_RENDERER_JWT_AUTH_KEYS_DIR=/config/jwt_keys
      - GRAFANA_RENDERER_JWT_AUTH_ROTATION_ENABLED=true
      - GRAFANA_RENDERER_JWT_AUTH_ROTATION_INTERVAL_DAYS=30
      - GRAFANA_RENDERER_JWT_AUTH_MAX_KEYS=3
    volumes:
      - ./config:/config
```

Файлы, которые сохраняются:
- `<kid>.private.pem`, `<kid>.public.pem`
- `keys.json` (манифест)

### 3) Внешний JWT из ENV (external_env)
Используйте готовый токен провайдера:

```
GRAFANA_RENDERER_JWT_AUTH_MODE=external_env
GRAFANA_RENDERER_EXTERNAL_JWT_ENV_VAR_NAME=GRAFANA_JWT_TOKEN
GRAFANA_JWT_TOKEN=eyJhbGciOiJSUzI1NiIsImtpZCI6Ii4uLiJ9.eyJzdWIiOiIuLi4ifQ.SIGN
```

Поведение:
- Токен читается из ENV и подставляется в URL как `auth_token`.
- Токен не логируется, хранится в памяти процесса.

### 4) Внешний JWT по HTTP (external_http)
Получение токена с внешнего эндпоинта (OAuth2/IdP):

```yaml
# impulse.yml (фрагмент)
grafana_renderer:
  jwt_auth:
    mode: external_http
  external_jwt:
    http_url: https://idp.example.com/oauth/token
    http_method: POST
    http_headers: '{"Content-Type":"application/json","Authorization":"Basic ..."}'
    http_body: '{"grant_type":"client_credentials"}'
    http_token_json_path: access_token
    http_cache_ttl_seconds: 240   # fallback, если нет exp в токене
    http_timeout_seconds: 10
    http_retries: 2
    http_retry_backoff_ms: 300
    clock_skew_seconds: 15
    allow_fallback_to_disabled: false
```

Поведение:
- Токен кэшируется до `exp` (если это JWT) или по TTL.
- Раннее обновление с учётом `clock_skew_seconds`.
- При ошибке запроса используются ретраи, токен не логируется.

### 5) Mute: удалён Grafana API, оставлены Alertmanager API и silenceURL
- Убрана поддержка создания silence через Grafana API.
- Остались два пути:
  - Alertmanager API (`application.alertmanager.api_url` + опц. `silence_duration`)
  - Кнопка URL со ссылкой `silenceURL` из payload (Grafana UI)
- Если нет ни AM API, ни `silenceURL`, кнопка Mute не показывается.

### 6) Исправлено двойное кодирование URL переменных
Ранее значения подставлялись с предварительным `quote`, а затем снова кодировались `urlencode`, из‑за чего `%` → `%25` и, например, `var-job=localhost.admin%252Fnode_exporter`.

Теперь:
- Убрано ручное кодирование; `urlencode` делает единственное корректное кодирование.
- Пример до/после:

```
До:  var-job=localhost.admin%252Fnode_exporter
После: var-job=localhost.admin%2Fnode_exporter
```

### 7) Конфигурируемые переменные панели из лейблов алертов
Добавлена гибкая система подстановки переменных Grafana из лейблов алертов с поддержкой множественных значений.

**Конфигурация в `impulse.yml` (обязательна):**
```yaml
grafana_renderer:
  panel_variables:
    # Глобальные правила маппинга лейблов → переменные (настраивается под ваши нужды)
    default_mapping:
      job: var-job
      instance: var-hostname
      env: var-env
      compose_service: var-service
      container_name: var-container
      maxmount: var-maxmount
      total: var-total
      interval: var-interval
    
    # Специфичные правила для конкретных дашбордов
    dashboard_specific:
      "f58f09cc-87b2-470f-9154-f974fc9a2e47":  # dashboard_id
        job: var-job
        instance: var-hostname
        maxmount: var-maxmount
        total: var-total
        interval: var-interval
    
    # Ограничения
    max_values_per_var: 20        # максимум значений на переменную
    max_url_length: 8192          # максимальная длина URL
```

**Переменные окружения:**
```
GRAFANA_RENDERER_PANEL_VARIABLES_MAX_VALUES_PER_VAR=20
GRAFANA_RENDERER_PANEL_VARIABLES_MAX_URL_LENGTH=8192
```

**Логика работы:**
- Собирает все уникальные значения лейблов из `alerts[].labels` в группе алертов
- Применяет маппинг из конфигурации: `label_name` → `var-name` (например, `instance` → `var-hostname`)
- Если конфигурация не задана — переменные не подставляются (система не работает)
- Генерирует повторяющиеся параметры: `var-hostname=host1&var-hostname=host2&...`
- Поддерживает dashboard-specific конфигурацию для точного контроля
- Ограничивает количество значений и длину URL для стабильности

**Пример результата:**
```
https://grafana.example.com/d-solo/dashboard?var-job=node_exporter&var-hostname=host1&var-hostname=host2&var-hostname=host3&var-service=nginx&var-service=postgres
```

**Преимущества:**
- Работает со сгруппированными алертами (несколько инстансов в одном уведомлении)
- Контекстная фильтрация: для рестарта хоста не ищет `compose_service`
- Безопасность: фильтрация недопустимых символов, ограничения длины
- Гибкость: разные правила для разных дашбордов

