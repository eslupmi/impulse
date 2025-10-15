# Webhooks

## Examples

### Send alert payload

```yaml
webhooks:
  send_payload:
    url: 'http://another_host:5003/'
    json: '{{ incident["payload"] }}'
```

### Form JSON from some parameters

```yaml
webhooks:
  generate_json:
    url: 'http://another_host:5003/'
    json:
      channel:
        id: '{{ incident["channel_id"] }}'
      status: '{{ incident["status"] }}'
```

### twilio.com

*To make this configs works you should add theese custom [Environment Variables](envs.md)*:

- TWILIO_ACCOUNT_SID
- TWILIO_AUTH_TOKEN
- TWILIO_NUMBER

```yaml
webhooks:
  Dmitry_call:
    url: 'https://api.twilio.com/2010-04-01/Accounts/{{ env["TWILIO_ACCOUNT_SID"] }}/Calls.json'
    data:
      To: '+998xxxxxxxxx'
      From: '{{ env["TWILIO_NUMBER"] }}'
      Url: http://example.com/twiml.xml
    auth: '{{ env["TWILIO_ACCOUNT_SID"] }}:{{ env["TWILIO_AUTH_TOKEN"] }}'
```

### zvonok.com

*To make this config works you should add theese custom [Environment Variables](envs.md)*:

- ZVONOK_CAMPAIGN_ID
- ZVONOK_PUBLIC_KEY

```yaml
webhooks:
  Dmitry_call:
    url: "https://zvonok.com/manager/cabapi_external/api/v1/phones/call/"
    data:
      campaign_id: '{{ env["ZVONOK_CAMPAIGN_ID"] }}'
      phone: '+998xxxxxxxxx'
      public_key: '{{ env["ZVONOK_PUBLIC_KEY"] }}'
```