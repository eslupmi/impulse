# Alertmanager

## Group and repeat intervals

!!! warning ""
    Configure group and repeat intervals correctly to ensure IMPulse works properly (the explanation is [here](concepts/incident.md#unknown))

Set the sum of `route.repeat_interval` and `route.group_interval` [Alertmanager's options](https://prometheus.io/docs/alerting/latest/configuration/) less than [`incident.timeouts.firing`](https://github.com/DiTsi/impulse/blob/develop/examples/impulse.slack.yml) (default `6h`):

```yaml title="alertmanager.yml"
route:
  repeat_interval: 354m
  group_interval: 5m
```

## Inhibition

IMPulse's [inhibition](concepts/inhibition.md) is similar to Alertmanager's.

In order for IMPulse to work correctly, you need to move the [inhibit_rules](config_file.md#inhibit_rules) section from Alertmanager to IMPulse config as is. This will help avoid the appearance of unnecessary [unknown](concepts/incident.md#unknown) statuses.

## Receiver

Set IMPulse as default receiver:

```yaml title="alertmanager.yml"
receivers:
  - name: 'impulse'
    webhook_configs:
      - url: 'http://<impulse_host>:<impulse_port>/'

route:
  receiver: 'impulse'
```

## Routing

IMPulse's [route](config_file.md#route) is similar to Alertmanager's, but simpler.

If you used alert routing in Alertmanager, the routing rules need to be moved to IMPulse. For this, you can move the entire Alertmanager's [`route`](https://prometheus.io/docs/alerting/latest/configuration/#route) block from `alertmanager.yml` to `impulse.yml`. Don't forget to remove all unused fields and replace all `receiver` entries with `chain` and `channel`. Fill them in correctly.

Details [here](config_file.md#route).
