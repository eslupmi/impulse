# Alertmanager

All code examples below are for [`alertmanager.yml`](https://prometheus.io/docs/alerting/latest/configuration/).

## set repeat_interval

Set the sum of `repeat_interval` and `group_interval` options less than [`incident.timeouts.firing`](https://github.com/DiTsi/impulse/blob/develop/examples/impulse.slack.minimal.yml) (default `6h`):
```yaml
route:
  repeat_interval: 354m
  group_interval: 5m
```
The explanation is [here](concepts.md#unknown).

## move routing

IMPulse's [route](config_file.md#route) is similar to Alertmanager's, but simpler.

When using IMPulse as the only one incident manager, you can move full your Alertmanager's [`route`](https://prometheus.io/docs/alerting/latest/configuration/#route) block from `alertmanager.yml` to `impulse.yml`. Don't forget to remove all unused instructions and replcae all `receiver` instrustions with `chain` and `channel`. Fill it correctly.

Details [here](config_file.md#route).

## modify receiver

Set IMPulse as default receiver:

```yaml
receivers:
  - name: 'impulse'
    webhook_configs:
      - url: 'http://<impulse_host>:<impulse_port>/'

route:
  receiver: 'impulse'
```
