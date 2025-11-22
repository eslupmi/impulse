# Task Management [↰](config_file.md#task_management)

IMPulse supports integration with task management systems.

!!! info ""
    Currently, only **Jira** is supported.

## Jira

To set up Jira integration, you need to configure the [config](config_file.md#task_management) and set the [environment variables](envs.md) `JIRA_BASE_URL`, `JIRA_USER_EMAIL`, and `JIRA_API_TOKEN`.

You can customize the **Summary** and **Description** format using custom [template_files](config_file.md#task_managementtemplate_files).

### Create and get token

1. Go to https://id.atlassian.com/manage-profile/security/api-tokens
2. Click **Create API token**
3. Name it (e.g., "impulse"), set "Expires on", press **Create**
4. Press **Copy** and use as `JIRA_API_TOKEN` [env](envs.md)
