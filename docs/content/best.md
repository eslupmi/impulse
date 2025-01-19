# Best Practices

## Prometheus

To close issues quickly you should create documentation about your alerts. To append documentation link to alerts there is special word `runbook`. Add it with link to `alert.annotations`:

```yaml
- alert: InstanceDown
  expr: up == 0
  annotations:
    runbook: https://yourdomain.confluence.com/alerts/InstanceDown
```

IMPulse will show you runbook link like this:

<p align="center"><img src="../media/slack_firing.png" alt="" width="400"/></p>

