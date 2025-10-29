# instatus.com

!!! info ""
    Integration work using [webhooks](config_file.md/#webhooks)

## Status page example

1. Add Prometheus application in Instatus
2. Add webhook to [impulse.yml](config_file.md) and use Prometheus webhook address as `url`:

```yaml
webhooks:
  instatus:
    url: 'https://api.instatus.com/v3/integrations/prometheus/clh2p9grm00k3t47ifz8nqsd1'
    json: '{{ incident["payload"] }}'
```
