# Buttons

Incidents in messengers have two mandatory buttons:

- Take It / Release
- Freeze

and one optional:

- Task

## Take It / Release

**Take It** behaviour (if `firing`):

- stops chain escalation
- assigns (or reassigns) the incident to the user who clicked the button

**Release** behaviour (if `resolved`):

- unassigns the incident
- resets the chain

## Freeze
This is a time selector for choosing until when the incident will be [frozen](incident.md#frozen). The day and time for unfreezing are determined based on the [general.week_start](../config_file.md#generalweek_start) and [general.workday_start](../config_file.md#generalworkday_start) parameters. Timezone is set for each user [if available](messengers.md), otherwise it uses [general.timezone](../config_file.md#generaltimezone).

**Freeze** behaviour:

- assigns the incident to the person who clicked the button (like [Take It](#take-it-release))
- stops activity on the incident (chain escalation, status updates)
- prevents creation of new incidents with the same identifier (like [silence](https://prometheus.io/docs/alerting/latest/alertmanager/#silences))
- displays the unfreeze datetime on the button instead of "Freeze"

**Unfreeze** behaviour:

- sets the actual incident status
- resumes activity on the incident (chain escalation, status updates)

## Task

Button without text, only pin icon: 📌. Appears only if the [Task Management](../config_file.md#task_management) integration is configured.

**Behaviour**:

- creates a task in your [Task Management](../config_file.md#task_management) software
- the button disappears
