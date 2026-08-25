# Templates [↰](../config_file.md#messengertemplate_files)

!!! warning
    Optional paths for templates will be removed in `v4.0.0`

IMPulse uses Jinja2 templates. Templates allow you to modify incident [messages](#incident-messages) and [thread messages](#thread-messages).

Also you can modify templates for [task management](#task-management).

## Incident messages

There are 3 templates that users can customize as needed (see [messages structure](incident.md#messages-structure)). These are:

- **status icons**
- **header**
- **body**

**[special variables](special_variables.md):** `incident`, `payload`, `parents`, `childs`, `incidents` (deprecated)

#### runbook

To resolve incidents faster, you can add documentation links to your alerts. To attach a documentation link to an alert, use the special annotation field called `runbook`:

```yaml
- alert: InstanceDown
  expr: up == 0
  annotations:
    runbook: https://<company>.confluence.com/alerts/InstanceDown
```

IMPulse will display the runbook link in the incident view (see [body](incident.md#messages-structure)). You can change the format to a convenient one and [redefine](../config_file.md#messengertemplate_files) template files.

## Thread messages

Every message IMPulse posts into an incident thread is rendered from its own template file. Template files are located in `./thread_templates` and are named `<messenger.type>_<template>.j2`, so each messenger has its own version of every message.

Below is a list of available templates.

### chain_step_group

- **description:** posted when a [chain](../config_file.md#messengerchains) reaches a `group` step
- **enabled by:** always
- **[special variables](special_variables.md):** `step`, `incident`, `users`, `user_groups`, `groups`, `webhooks`

### chain_step_user

- **description:** posted when a [chain](../config_file.md#messengerchains) reaches a `user` step
- **enabled by:** always
- **[special variables](special_variables.md):** `step`, `incident`, `users`, `user_groups`, `groups`, `webhooks`

### chain_step_user_group

- **description:** posted when a [chain](../config_file.md#messengerchains) reaches a `user_group` step
- **enabled by:** always
- **[special variables](special_variables.md):** `step`, `incident`, `users`, `user_groups`, `groups`, `webhooks`

### chain_step_webhook

- **description:** posted when a [chain](../config_file.md#messengerchains) reaches a `webhook` step
- **enabled by:** always
- **[special variables](special_variables.md):** `step`, `incident`, `users`, `user_groups`, `groups`, `webhooks`

### incident_notifications_assignment

- **description:** posted when an incident is assigned or unassigned
- **enabled by:** [incident.notifications.assignment](../config_file.md#incidentnotificationsassignment)
- **[special variables](special_variables.md):** `incident`, `users`, `ui_user`

### incident_notifications_freeze

- **description:** posted when an incident becomes [**frozen**](incident.md#frozen)
- **enabled by:** [incident.notifications.freeze](../config_file.md#incidentnotificationsfreeze)
- **[special variables](special_variables.md):** `incident`, `parents`, `childs`, `ui_user`

### incident_notifications_new_firing

- **description:** posted when new **firing** alerts are added to the incident
- **enabled by:** [incident.notifications.new_firing](../config_file.md#incidentnotificationsnew_firing)
- **[special variables](special_variables.md):** `payload`, `previous_payload`, `incident`

### incident_notifications_partial_resolved

- **description:** posted when some alerts of the incident become **resolved**
- **enabled by:** [incident.notifications.partial_resolved](../config_file.md#incidentnotificationspartial_resolved)
- **[special variables](special_variables.md):** `payload`, `previous_payload`, `incident`

### incident_notifications_status_update

- **description:** posted when an incident [status](incident.md#statuses-and-their-colors) changes
- **enabled by:** [incident.notifications.status_update](../config_file.md#incidentnotificationsstatus_update)
- **[special variables](special_variables.md):** `payload`, `previous_payload`, `incident`

### incident_notifications_unfreeze

- **description:** posted when an incident is unfrozen
- **enabled by:** always
- **[special variables](special_variables.md):** `incident`, `parents`, `childs`, `ui_user`

## Task Management

You can customize the **Summary** and **Description** used when creating tasks in the task management application. Template files are located in the `templates` directory and are named `<task_management.type>_summary.j2` and `<task_management.type>_description.j2`.
