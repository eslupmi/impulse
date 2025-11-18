# Jira Cloud Integration

This document describes how to set up and use the Jira Cloud integration for creating tasks from incidents using Basic Authentication with API tokens.

## Overview

The Jira integration allows you to automatically create Jira tasks from incidents in your messaging platform (Slack, Mattermost, or Telegram). It uses Jira Cloud REST API v3 with Basic Authentication for secure server-to-server communication.

### Features

- ✅ Create Jira tasks directly from incident threads
- ✅ 📌 Pin button in thread starter message
- ✅ Automatic task details (status, assignee, alerts, labels)
- ✅ Direct link to task after creation
- ✅ Infrastructure-as-code ready (all config via environment variables)
- ✅ No interactive authentication required

---

## Prerequisites

### 1. Jira Cloud Instance

You need access to a Jira Cloud instance (e.g., `https://your-domain.atlassian.net`).

### 2. Jira API Token

Generate an API token for your Jira user:

1. Log in to https://id.atlassian.com/manage-profile/security/api-tokens
2. Click **Create API token**
Recommended scopes: write:issue:jira, read:issue:jira, read:project:jira, write:comment:jira, read:comment:jira
3. Give it a name (e.g., "IMPulse Integration")
4. Copy the generated token (you won't see it again!)

### 3. Jira Project

You need a Jira project where tasks will be created:

- Example project key: **DTS**, **OPS**, **INCIDENT**, etc.
- Your user must have permission to create issues in this project

---

## Configuration

### Environment Variables

Add these environment variables to your `.env` file or deployment configuration:

```bash
# Jira Cloud instance URL
JIRA_BASE_URL=https://your-domain.atlassian.net

# User email for authentication
JIRA_USER_EMAIL=your-email@company.com

# API token (generated from Atlassian account)
JIRA_API_TOKEN=your_api_token_here

# Project key where tasks will be created
JIRA_PROJECT_KEY=DTS
```

### Example Configuration

```bash
JIRA_BASE_URL=https://acme-corp.atlassian.net
JIRA_USER_EMAIL=alerts@acme-corp.com
JIRA_API_TOKEN=ATATT3xFfGF0abcdefghijklmnopqrstuvwxyz1234567890
JIRA_PROJECT_KEY=OPS
```

---

## Setup Instructions

### Step 1: Create Jira API Token

1. Go to https://id.atlassian.com/manage-profile/security/api-tokens
2. Click **Create API token**
3. Name it (e.g., "IMPulse Incident Automation")
4. **Copy the token immediately** (store it securely)

### Step 2: Get Your Jira Base URL

Your Jira base URL is the domain you use to access Jira:

- Format: `https://<your-domain>.atlassian.net`
- Example: `https://acme-corp.atlassian.net`

Do **not** include any path after the domain (no `/browse/`, `/rest/api/`, etc.).

### Step 3: Get Your Project Key

In Jira, navigate to your project. The project key is visible:

- In the URL: `https://your-domain.atlassian.net/browse/DTS-123` → Key is **DTS**
- In the project name: "Data Team Support (DTS)" → Key is **DTS**
- In the sidebar or project settings

### Step 4: Configure Environment Variables

Add the four required environment variables to your configuration:

```bash
JIRA_BASE_URL=https://your-domain.atlassian.net
JIRA_USER_EMAIL=your-email@company.com
JIRA_API_TOKEN=your_api_token_here
JIRA_PROJECT_KEY=YOUR_PROJECT_KEY
```

### Step 5: Start the Application

```bash
python main.py
```

You should see in the logs:

```
INFO: Initializing Jira integration with Basic Auth...
INFO: Jira integration initialized and ready.
INFO: IMPulse started!
```

### Step 6: Test the Integration

1. Trigger an incident (or find an existing one)
2. Look for the 📌 pin button in the incident thread
3. Click the pin button
4. A Jira task will be created automatically
5. Click the button again to open the task in Jira

---

## How It Works

### Authentication

The integration uses **Basic Authentication** with Jira Cloud REST API:

1. Credentials (`email:token`) are base64-encoded
2. Sent in the `Authorization` header: `Basic <encoded_credentials>`
3. Every API request includes authentication

### Task Creation Flow

```
1. User clicks 📌 button in incident thread
   ↓
2. Application formats incident details
   ↓
3. POST request to /rest/api/3/issue with Basic Auth
   ↓
4. Jira creates task and returns issue key
   ↓
5. Task link stored in incident.task_link
   ↓
6. Thread updated with task link
   ↓
7. Subsequent clicks open the task in browser
```

### Task Details

When a Jira task is created, it includes:

**Summary (Title)**:
- Built from alert group labels or alert name
- Example: "Alert: service=api, env=prod"

**Description**:
- Incident status
- Assigned user
- Number of alerts
- Link to IM thread
- Group labels and annotations

**Issue Type**: Task (default)

---

## API Details

### Jira Cloud REST API v3

The integration uses Jira Cloud REST API v3:

- **Endpoint**: `POST /rest/api/3/issue`
- **Auth**: Basic Authentication (email:token)
- **Content-Type**: `application/json`
- **Accept**: `application/json`

### Request Format

```json
{
  "fields": {
    "project": {
      "key": "DTS"
    },
    "summary": "Alert: service=api, env=prod",
    "description": {
      "type": "doc",
      "version": 1,
      "content": [
        {
          "type": "paragraph",
          "content": [
            {
              "type": "text",
              "text": "Incident Status: firing\nAssigned to: John Doe\n..."
            }
          ]
        }
      ]
    },
    "issuetype": {
      "name": "Task"
    }
  }
}
```

### Response

```json
{
  "id": "10001",
  "key": "DTS-123",
  "self": "https://your-domain.atlassian.net/rest/api/3/issue/10001"
}
```

The application builds a browse URL: `https://your-domain.atlassian.net/browse/DTS-123`

---

## Button Behavior

### 📌 Pin Button

The pin button appears in the thread starter message (along with assign, silence, etc.):

| State | Behavior |
|-------|----------|
| **No task created** | Button is clickable, creates new Jira task |
| **Task exists** | Button becomes a link to open the task |

### Visual Indication

- Button shows 📌 icon
- Platform-specific styling:
  - **Slack**: `:pushpin:` emoji
  - **Mattermost**: 📌 emoji
  - **Telegram**: 📌 emoji

---

## Troubleshooting

### Integration Not Enabled

**Symptom**: No 📌 button appears in incident threads

**Solution**: Verify all four environment variables are set:

```bash
echo $JIRA_BASE_URL
echo $JIRA_USER_EMAIL
echo $JIRA_API_TOKEN
echo $JIRA_PROJECT_KEY
```

All four must have values for the integration to be enabled.

---

### "Failed to create Jira issue: 401"

**Symptom**: Error in logs when clicking button

**Cause**: Invalid credentials

**Solution**:
1. Verify your email is correct
2. Regenerate your API token
3. Update `JIRA_API_TOKEN` environment variable
4. Restart the application

---

### "Failed to create Jira issue: 404"

**Symptom**: Error in logs when clicking button

**Cause**: Invalid project key or base URL

**Solution**:
1. Verify your `JIRA_BASE_URL` is correct (no trailing path)
2. Verify your `JIRA_PROJECT_KEY` exists
3. Ensure your user has access to the project
4. Restart the application

---

### "Failed to create Jira issue: 400"

**Symptom**: Error in logs when clicking button

**Cause**: Invalid request data (field configuration issue)

**Solution**:
1. Check if the project requires additional fields
2. Verify "Task" issue type exists in your project
3. Check Jira project settings for required fields
4. Review the error details in the logs

---

### Button Pressed But No Task Created

**Symptom**: Button clicked, no error, but no task appears

**Solution**:
1. Check application logs for errors
2. Verify network connectivity to Jira
3. Check if your API token has expired
4. Verify user has "Create Issues" permission in project

---

## Security Considerations

### API Token Security

- ✅ API tokens are stored as environment variables only
- ✅ Tokens are base64-encoded but **not encrypted** in transit (HTTPS handles encryption)
- ✅ Tokens are never logged or exposed in API responses
- ⚠️ Treat API tokens like passwords - keep them secret!

### Best Practices

1. **Use a dedicated service account**: Create a Jira user specifically for automation (e.g., `impulse-bot@company.com`)
2. **Principle of least privilege**: Only grant "Create Issues" permission in required projects
3. **Rotate tokens regularly**: Regenerate API tokens periodically
4. **Monitor usage**: Review Jira audit logs for unexpected activity
5. **Secure environment variables**: Use secrets management (Vault, AWS Secrets Manager, etc.) in production

---

## Infrastructure as Code

### Docker Compose

```yaml
services:
  impulse:
    image: impulse:latest
    environment:
      - JIRA_BASE_URL=https://your-domain.atlassian.net
      - JIRA_USER_EMAIL=impulse-bot@company.com
      - JIRA_API_TOKEN=${JIRA_API_TOKEN}
      - JIRA_PROJECT_KEY=OPS
    env_file:
      - .env.secret
```

### Kubernetes

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: impulse-jira-secrets
type: Opaque
stringData:
  api-token: "your_api_token_here"
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: impulse
spec:
  template:
    spec:
      containers:
      - name: impulse
        image: impulse:latest
        env:
        - name: JIRA_BASE_URL
          value: "https://your-domain.atlassian.net"
        - name: JIRA_USER_EMAIL
          value: "impulse-bot@company.com"
        - name: JIRA_PROJECT_KEY
          value: "OPS"
        - name: JIRA_API_TOKEN
          valueFrom:
            secretKeyRef:
              name: impulse-jira-secrets
              key: api-token
```

### Terraform (AWS ECS)

```hcl
resource "aws_ecs_task_definition" "impulse" {
  family = "impulse"
  container_definitions = jsonencode([
    {
      name  = "impulse"
      image = "impulse:latest"
      environment = [
        { name = "JIRA_BASE_URL", value = "https://your-domain.atlassian.net" },
        { name = "JIRA_USER_EMAIL", value = "impulse-bot@company.com" },
        { name = "JIRA_PROJECT_KEY", value = "OPS" }
      ]
      secrets = [
        {
          name      = "JIRA_API_TOKEN"
          valueFrom = aws_secretsmanager_secret.jira_token.arn
        }
      ]
    }
  ])
}
```

---

## Performance

### Rate Limiting

The integration uses `RateLimitedClient` with:
- **Retry attempts**: 3
- **Timeout**: 30 seconds
- **Rate limit**: None (Jira Cloud handles rate limiting)

### Async Operation

Task creation is **non-blocking**:
- Button click response is immediate
- Task creation happens in the background
- Thread is updated when task is created

---

## Monitoring

### Logs

Key log messages to monitor:

```
INFO: Jira integration initialized and ready.
INFO: Creating Jira task for incident abc-123
INFO: Successfully created Jira issue: DTS-456
ERROR: Failed to create Jira issue: 401 - Unauthorized
```

### Health Checks

Monitor for:
- ✅ Successful task creation rate
- ⚠️ 401 errors (credential issues)
- ⚠️ 404 errors (configuration issues)
- ⚠️ Timeout errors (network issues)

---

## Customization

### Issue Type

To use a different issue type (e.g., "Bug", "Incident"):

Modify `app/integrations/jira.py`:

```python
"issuetype": {"name": "Incident"}  # Changed from "Task"
```

### Additional Fields

To add custom fields to created issues, modify the payload in `JiraClient.create_issue()`:

```python
payload = {
    "fields": {
        "project": {"key": project_key},
        "summary": summary,
        "description": description,
        "issuetype": {"name": "Task"},
        "customfield_10001": "custom_value"  # Add custom fields
    }
}
```

---

## References

- [Jira Cloud REST API v3 Documentation](https://developer.atlassian.com/cloud/jira/platform/rest/v3/)
- [Jira Basic Authentication](https://developer.atlassian.com/cloud/jira/platform/basic-auth-for-rest-apis/)
- [Managing API Tokens](https://support.atlassian.com/atlassian-account/docs/manage-api-tokens-for-your-atlassian-account/)
- [Jira Issue Fields](https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issues/#api-rest-api-3-issue-post)

---

## Support

If you encounter issues:

1. Check the logs for error messages
2. Verify all environment variables are set correctly
3. Test API token manually with curl:

```bash
curl -u your-email@company.com:your_api_token \
  -X GET \
  -H "Content-Type: application/json" \
  https://your-domain.atlassian.net/rest/api/3/myself
```

4. Check Jira project permissions
5. Review this documentation for troubleshooting steps

---

## Summary

The Jira integration provides seamless task creation from incidents with:

- ✅ Simple Basic Authentication (no OAuth complexity)
- ✅ Infrastructure-as-code ready
- ✅ No interactive steps required
- ✅ Secure server-to-server communication
- ✅ Automatic incident details in tasks
- ✅ Direct task links in incident threads

Configure four environment variables, restart the application, and you're ready to create Jira tasks from incidents! 🎉

