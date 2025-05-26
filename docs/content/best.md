# Best Practices

## Prometheus

To resolve incident faster, you should create documentation for your alerts.

To attach a documentation link to an alert, use the special annotation field called`runbook`. Add it with link to `alert.annotations`:

```yaml
- alert: InstanceDown
  expr: up == 0
  annotations:
    runbook: https://yourdomain.confluence.com/alerts/InstanceDown
```

IMPulse will display the runbook link in the incident view like this:

<p align="center"><img src="../media/slack_firing.excalidraw.svg" alt="" width="400"/></p>

