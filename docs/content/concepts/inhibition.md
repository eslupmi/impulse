# Inhibition

Inhibition is similar to [Alertmanager's mechanism](https://prometheus.io/docs/alerting/latest/configuration/#inhibition-related-settings), which allows suppressing less important alerts based on rules. In IMPulse we work with incidents instead of alerts, so there are differences in the mechanism.

An incident in IMPulse is always created, regardless of [inhibit_rules](../config_file.md#inhibit_rules). However, if an incident is a [target](../config_file.md#ruletarget_matchers) (child), it transitions to the [frozen](incident.md#frozen) state until all [source](..//config_file.md#rulesource_matchers) (parent) incidents receive the [resolved](incident.md#firing-and-resolved) status.
