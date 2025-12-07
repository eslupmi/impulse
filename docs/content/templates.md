# Templates [↰](config_file.md/#messengertemplate_files)

IMPulse uses Jinja2-based templates. Templates allow you to modify certain messages.

Currently, you can write your own templates for thread messages and for tasks in task management.

## Messages

There are 3 templates that users can customize as needed (see [messages structure](concepts/incident.md#messages-structure)). These are:

- `status icons`
- `header`
- `body`

### Default template

The default `body` template supports 3 links:

- source - link points to Prometheus query
- runbook - link for [runbook](#runbook)
- task - link points to a task in the task management application if a [task was created](buttons.md) for the incident

#### runbook

To resolve incidents faster, you can add documentation links to your alerts. To attach a documentation link to an alert, use the special annotation field called `runbook`:

```yaml
- alert: InstanceDown
  expr: up == 0
  annotations:
    runbook: https://yourdomain.confluence.com/alerts/InstanceDown
```

IMPulse will display the runbook link in the incident view (see [body](concepts/incident.md#messages-structure)). You can change the format to a convenient one and [redefine](config_file.md#messengertemplate_files) template files.

## Task Management

You can customize the Summary and Description [templates](config_file.md#task_managementtemplate_files) used when creating tasks in the task management application.
