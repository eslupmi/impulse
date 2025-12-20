# Buttons
Each incident has 2 mandatory buttons: **Take It/Release** and **Freeze**. There is also an optional **Task** (pin icon) button that appears only if the [Task Management](config_file.md#task_management) integration is configured.

## Take It
Stops chain execution and assigns the incident to the user who clicked the button. Another user can click it again to reassign the incident to themselves. If the incident is in the **resolved** status, the button will display as **Release** instead of **Take It**. **Release** unassigns the incident and removes the associated chain. If a new firing alert arrives, a new chain will be created based on the configuration.

## Freeze
This is a time selector that sets until when the incident will remain in the [frozen](concepts/incident.md#frozen) state. The day and time for unfreezing are determined based on the [general.week_start](config_file.md#generalweek_start) and [general.workday_start](config_file.md#generalworkday_start) parameters. Timezone is individual for each user (except Telegram).

When clicked:
- assigns the incident to the person who clicked the button (like Take It)
- stops activity on the incident (chain escallation, status updates)
- prevents creation of similar incidents

## Task (optional)
Creates a task in your Jira. The task is created in the project specified in the [configuration](config_file.md#task_managementproject_key). If the task is created, the button disappears.