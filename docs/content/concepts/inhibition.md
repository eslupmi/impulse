# Inhibition

Inhibition is similar to [Alertmanager's](https://prometheus.io/docs/alerting/latest/configuration/#inhibition-related-settings) mechanism, which allows suppressing less important incidents based on rules.

[Inhibit rules](../config_file.md#inhibit_rules) allow establishing parent-child relationships between incidents. If two incidents match one of the inhibit rules and the source incident is in the **firing** status, the relationships will be established, and the child will be **frozen** until all its parent incidents are in the **resolved** status.

Incidents have `parents` and `childs` fields which contain lists of corresponding incident `uniq_id` values. This fields can be used in [templates](../config_file.md#messengertemplate_files). See `templates/slack_body.j2` for example.
