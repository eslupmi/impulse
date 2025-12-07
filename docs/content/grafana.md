# Grafana

## Group and repeat intervals

!!! warning ""
    Configure group and repeat intervals correctly to ensure IMPulse works properly (the explanation is [here](concepts/incident.md#unknown))

1. Go to menu **Alerting** > **Notification Policies** and modify your notification policy by pressing **More** > **Edit**

2. Expand **Timing options** and set the sum of "Group interval" and "Repeat interval" options to be less than [`incident.timeouts.firing`](https://github.com/DiTsi/impulse/blob/develop/examples/impulse.slack.yml) (default is `6h`).

## Contact point

Create contact point for IMPulse and use it in Grafana alerts

1. Go to menu **Alerting** > **Contact points** and add IMPulse as contact point by pressing **Create contact point**:

    - set **Name** to "IMPulse"
    - set **Integration** to "Webhook"
    - set appropriate **URL** to connect to IMPulse (like "http://localhost:5000/")
