# telegram.org

!!! info ""
    Integration work using [webhooks](config_file.md/#webhooks)

If Telegram is not your main messenger but you want to use it for additional notifications, see this guide.

## Message example

*To make this configs works you should add theese custom [Environment Variables](envs.md)*:

- TELEGRAM_BOT_TOKEN
- TELEGRAM_CHAT_ID

and add webhook to [impulse.yml](config_file.md):

```yaml
webhooks:
  telegram_message:
    url: 'https://api.telegram.org/bot{{ env["TELEGRAM_BOT_TOKEN"] }}/sendMessage'
    data:
      chat_id: '{{ env["TELEGRAM_CHAT_ID"] }}'
      text: |
        New Incident created: <b>{{ incident.payload.commonLabels.alertname }}</b>
        
        {{ incident.payload.commonAnnotations.summary }}
        <i>{{ incident.payload.commonAnnotations.description }}</i>
      parse_mode: 'HTML'
```
