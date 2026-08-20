# Templates [↰](../config_file.md#messengertemplate_files)

IMPulse uses Jinja2-based templates. Templates allow you to modify certain messages.

Currently, you can write your own templates for incident messages, for [thread messages](#thread-messages) and for tasks in task management.

## Messages

There are 3 templates that users can customize as needed (see [messages structure](incident.md#messages-structure)). These are:

- **status icons**
- **header**
- **body**

**[special variables](special_variables.md):** `incident`, `payload`, `parents`, `childs` (`incidents` is deprecated)

### Default template

The default **body** template supports 3 links:

- source - link points to Prometheus query
- runbook - link for [runbook](#runbook)
- task - link points to a task if [it was created](incident.md#task) for the incident

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

Every message IMPulse posts into an incident thread is rendered from its own template file. Template files are located in the `thread_templates` directory and are named `<messenger.type>_<template>.j2`, so each messenger has its own version of every message. Default files are [here](https://github.com/eslupmi/impulse/tree/develop/thread_templates).

To change a thread message, edit the corresponding file and restart IMPulse. In Docker, mount your own file over the default one:

```yaml
services:
  app:
    volumes:
    - ./slack_chain_step_user.j2:/app/thread_templates/slack_chain_step_user.j2
```

### Available templates

#### chain_step_user

- **description:** posted when a [chain](../config_file.md#messengerchains) reaches a `user` step
- **enabled by:** always
- **[special variables](special_variables.md):** `step`, `incident`, `users`, `user_groups`, `groups`, `webhooks`

#### chain_step_user_group

- **description:** posted when a chain reaches a `user_group` step
- **enabled by:** always
- **[special variables](special_variables.md):** `step`, `incident`, `users`, `user_groups`, `groups`, `webhooks`

#### chain_step_group

- **description:** posted when a chain reaches a `group` step
- **enabled by:** always
- **[special variables](special_variables.md):** `step`, `incident`, `users`, `user_groups`, `groups`, `webhooks`

#### chain_step_webhook

- **description:** posted when a chain reaches a `webhook` step
- **enabled by:** always
- **[special variables](special_variables.md):** `step`, `incident`, `users`, `user_groups`, `groups`, `webhooks`

#### incident_notifications_assignment

- **description:** posted when an incident is assigned or unassigned
- **enabled by:** [incident.notifications.assignment](../config_file.md#incidentnotificationsassignment)
- **[special variables](special_variables.md):** `incident`, `users`, `ui_user`

#### incident_notifications_status_update

- **description:** posted when an incident [status](incident.md#statuses-and-their-colors) changes
- **enabled by:** [incident.notifications.status_update](../config_file.md#incidentnotificationsstatus_update)
- **[special variables](special_variables.md):** `payload`, `previous_payload`, `incident`

#### incident_notifications_new_firing

- **description:** posted when new **firing** alerts are added to the incident
- **enabled by:** [incident.notifications.new_firing](../config_file.md#incidentnotificationsnew_firing)
- **[special variables](special_variables.md):** `payload`, `previous_payload`, `incident`

#### incident_notifications_partial_resolved

- **description:** posted when some alerts of the incident become **resolved**
- **enabled by:** [incident.notifications.partial_resolved](../config_file.md#incidentnotificationspartial_resolved)
- **[special variables](special_variables.md):** `payload`, `previous_payload`, `incident`

#### incident_notifications_freeze

- **description:** posted when an incident becomes [**frozen**](incident.md#frozen)
- **enabled by:** [incident.notifications.freeze](../config_file.md#incidentnotificationsfreeze)
- **[special variables](special_variables.md):** `incident`, `parents`, `childs`, `ui_user`

#### incident_notifications_unfreeze

- **description:** posted when an incident is unfrozen
- **enabled by:** always
- **[special variables](special_variables.md):** `incident`, `parents`, `childs`, `ui_user`

Default chain step templates use `users` to mention admins when a step cannot be delivered:

```jinja
{%- set user = users.get(step.value) -%}
:loudspeaker: user *{{ step.value -}}*
{%- if user.exists -%}
 (<@{{ user.id }}>)
{%- else -%}
 (NotFound)  |  :loudspeaker: admins ({%- for u in users.values() if u and 'admin' in u.roles %}<@{{ u.id }}>{% if not loop.last %},{% endif %}{% endfor -%})
{%- endif -%}
```

## Task Management

You can customize the Summary and Description [templates](../config_file.md#task_managementtemplate_files) used when creating tasks in the task management application.
