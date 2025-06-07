# How to Use

When an alert is received, IMPulse creates a new incident.
If the incident has an associated chain, the chain will start executing.

## Buttons

Each incident has two interactive buttons: **Take It/Release** and **Status**.

- **Take It** stops chain execution and assigns the incident to the user who clicked the button. Another user can click it again to reassign the incident to themselves. If the incident is in the **resolved** status, the button will display as **Release** instead of **Take It**. **Release** unassigns the incident and removes the associated chain. If a new firing alert arrives, a new chain will be created based on the configuration.

- **Status** disables further status update notifications. This is useful when an incident frequently switches between **firing** and **resolved**, helping to suppress noisy updates. The **Status** button includes an indicator: green — status notifications are enabled (default), red — status notifications are disabled.
