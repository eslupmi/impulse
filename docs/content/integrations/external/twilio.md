# twilio.com

!!! info ""
    Integration work using [webhooks](config_file.md/#webhooks)

## Call example

*To make this configs works you should add theese custom [Environment Variables](envs.md)*:

- TWILIO_ACCOUNT_SID
- TWILIO_AUTH_TOKEN
- TWILIO_NUMBER

and add webhook to [impulse.yml](config_file.md):

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
