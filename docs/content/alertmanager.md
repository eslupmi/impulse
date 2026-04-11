# Alertmanager

## Group and repeat intervals

Set the sum of `route.repeat_interval`[↰](https://prometheus.io/docs/alerting/latest/configuration/#route) and `route.group_interval`[↰](https://prometheus.io/docs/alerting/latest/configuration/#route) Alertmanager's options less than `incident.timeouts.firing`[↰](config_file.md#incidenttimeoutsfiring) (the explanation is [here](concepts/incident.md#unknown)):

```yaml title="alertmanager.yml"
route:
  repeat_interval: 354m
  group_interval: 5m
```

## Inhibition

IMPulse's [inhibition](concepts/inhibition.md) is similar to Alertmanager's.

In order for IMPulse to work correctly, you need to move the [inhibit_rules](https://prometheus.io/docs/alerting/latest/configuration/#inhibition-related-settings) section from Alertmanager to [IMPulse config](config_file.md#inhibit_rules) as is. This will help avoid the appearance of unnecessary [unknown](concepts/incident.md#unknown) statuses.

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

If you used alert routing in Alertmanager, the routing rules need to be moved to IMPulse. For this, you can move the entire Alertmanager's `route`[↰](https://prometheus.io/docs/alerting/latest/configuration/#route) block from `alertmanager.yml`[↰](https://prometheus.io/docs/alerting/latest/configuration/) to `impulse.yml`[↰](config_file.md#route). Don't forget to remove all unused fields and replace all `receiver`[↰](https://prometheus.io/docs/alerting/latest/configuration/#route) entries with `chain`[↰](config_file.md#messengerchains) and `channel`[↰](config_file.md#messengerchannels). Fill them in correctly.
