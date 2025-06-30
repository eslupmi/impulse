# Alertmanager

> All code examples below are for [`alertmanager.yml`](https://prometheus.io/docs/alerting/latest/configuration/).

To ensure IMPulse works correctly, you need to configure Alertmanager.

1. Set correct repeat_interval

    Set the sum of `repeat_interval` and `group_interval` options less than [`incident.timeouts.firing`](https://github.com/DiTsi/impulse/blob/develop/examples/impulse.slack.minimal.yml) (default `6h`):
    ```yaml
    route:
      repeat_interval: 354m
      group_interval: 5m
    ```
    The explanation is [here](concepts.md#unknown).

2. Alerts routing

    IMPulse's [route](config_file.md#route) is similar to Alertmanager's, but simpler.

    If you used alert routing in Alertmanager, the routing rules need to be moved to IMPulse. For this, you can move the entire Alertmanager's [`route`](https://prometheus.io/docs/alerting/latest/configuration/#route) block from `alertmanager.yml` to `impulse.yml`. Don't forget to remove all unused fields and replace all `receiver` entries with `chain` and `channel`. Fill them in correctly.

    Details [here](config_file.md#route).

3. Modify receiver

    Set IMPulse as default receiver:

    ```yaml
    receivers:
      - name: 'impulse'
        webhook_configs:
          - url: 'http://<impulse_host>:<impulse_port>/'

    route:
      receiver: 'impulse'
    ```
