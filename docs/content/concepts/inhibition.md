# Inhibition

Inhibition is similar to [Alertmanager's](https://prometheus.io/docs/alerting/latest/configuration/#inhibition-related-settings) mechanism, which allows suppressing less important incidents based on rules.

An incident in IMPulse is always created, regardless of [inhibit_rules](../config_file.md#inhibit_rules). However, if an incident is a [target](../config_file.md#ruletarget_matchers) (child), it transitions to the [frozen](incident.md#frozen) state until all [source](..//config_file.md#rulesource_matchers) (parent) incidents receive the [resolved](incident.md#firing-and-resolved) status.
