# How to use

When an alert occurs, a new incident is created. If the incident has a chain, the chain will start executing.

## Buttons

There are two buttons on all incidents: **Take It** / **Release** and **Status**.

- The **Take It** button is used to stop chain execution and assign the incident to the user who pressed the button. Another user can press it again to reassign the incident to themselves. If the incident is in the "resolved" status, you will see "Release" instead of "Take It". **Release** unassigns the incident and removes the previous chain. If a new firing alert appears, a new chain will be created based on the configuration.

- The **Status** button stops status update notifications. Sometimes an incident frequently switches between "firing" and "resolved" statuses, and this button helps suppress extra notifications. The **Status** button has an indicator: green means "enabled," and red means "disabled."
