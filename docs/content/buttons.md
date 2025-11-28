# Buttons
Each incident has 2 mandatory buttons: **Take It/Release** and **Freeze**. There is also an optional **Task** (:pushpin:) button that appears only if the [Task Management](task_management.md) integration is [configured](config_file.md#task_management).

## Take It
Stops chain execution and assigns the incident to the user who clicked the button. Another user can click it again to reassign the incident to themselves. If the incident is in the **resolved** status, the button will display as **Release** instead of **Take It**. **Release** unassigns the incident and removes the associated chain. If a new firing alert arrives, a new chain will be created based on the configuration.

## Freeze
Disables further status update notifications. This is useful when an incident frequently switches between **firing** and **resolved**, helping to suppress noisy updates. The **Freeze** button includes an indicator: green — status notifications are enabled (default), red — status notifications are disabled.

## Task (optional)
Creates a task in your Jira. The task is created in the project specified in the [configuration](config_file.md#task_managementproject_key). If the task is created, the button disappears.