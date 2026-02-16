# zvonok.com

!!! info ""
    Integration work using [webhooks](../../config_file.md#webhooks)

## Call example

*To make this config works you should add theese custom [Environment Variables](../../envs.md)*:

- ZVONOK_CAMPAIGN_ID
- ZVONOK_PUBLIC_KEY

and add webhook to [impulse.yml](../../config_file.md):

```yaml
webhooks:
  Dmitry_call:
    url: "https://zvonok.com/manager/cabapi_external/api/v1/phones/call/"
    data:
      campaign_id: '{{ env["ZVONOK_CAMPAIGN_ID"] }}'
      phone: '+998xxxxxxxxx'
      public_key: '{{ env["ZVONOK_PUBLIC_KEY"] }}'
```
