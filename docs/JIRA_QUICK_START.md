# Jira Integration - Quick Start Guide

Get up and running with Jira task creation in 5 minutes!

## Prerequisites

- ✅ Jira Cloud instance (e.g., `https://your-domain.atlassian.net`)
- ✅ Jira user account with "Create Issues" permission
- ✅ A Jira project (e.g., "OPS", "DTS", "INCIDENT")

---

## Step 1: Generate API Token

1. Visit: https://id.atlassian.com/manage-profile/security/api-tokens
2. Click **Create non-scoped API token**
3. Name it (e.g., "IMPulse Integration")
4. **Copy the token** (you won't see it again!)

⏱️ Time: 1 minute

---

## Step 2: Configure Environment Variables

Add these four variables to your `.env` file:

```bash
JIRA_BASE_URL=https://your-domain.atlassian.net
JIRA_USER_EMAIL=your-email@company.com
JIRA_API_TOKEN=paste_your_token_here
JIRA_PROJECT_KEY=OPS
```

### Example

```bash
JIRA_BASE_URL=https://acme-corp.atlassian.net
JIRA_USER_EMAIL=alerts@acme-corp.com
JIRA_API_TOKEN=ATATT3xFfGF0abcdefghijklmnopqrstuvwxyz1234567890
JIRA_PROJECT_KEY=OPS
```

⏱️ Time: 2 minutes

---

## Step 3: Start Application

```bash
python main.py
```

**Expected output:**

```
INFO: Initializing Jira integration with Basic Auth...
INFO: Jira integration initialized and ready.
INFO: IMPulse started!
```

⏱️ Time: 30 seconds

---

## Step 4: Test It!

1. Open an incident in your messaging platform
2. Look for the 📌 pin button
3. Click it to create a Jira task
4. Click again to open the task

⏱️ Time: 30 seconds

---

## Troubleshooting

### No 📌 button?

Check that all four environment variables are set:

```bash
echo $JIRA_BASE_URL
echo $JIRA_USER_EMAIL
echo $JIRA_API_TOKEN
echo $JIRA_PROJECT_KEY
```

### Task creation fails?

1. Verify your API token is valid
2. Check your email is correct
3. Ensure you have "Create Issues" permission
4. Verify the project key exists

---

## What Gets Created?

Each Jira task includes:

- **Summary**: Alert details (e.g., "Alert: service=api, env=prod")
- **Description**:
  - Incident status
  - Assigned user
  - Number of alerts
  - Link to IM thread
  - Group labels
- **Type**: Task
- **Project**: Your configured project

---

## Security Notes

- 🔒 API token = password - keep it secret!
- 🔒 Use environment variables or secrets manager
- 🔒 Consider a dedicated service account
- 🔒 Grant minimum required permissions

---

## Next Steps

- 📖 Read full documentation: [JIRA_INTEGRATION.md](./JIRA_INTEGRATION.md)
- 🔧 Customize issue type or fields
- 📊 Monitor task creation in logs
- 🔄 Set up automated token rotation

---

## Complete Example

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
```

### Kubernetes

```yaml
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
      name: jira-secrets
      key: api-token
```

---

## Support

Need help? Check:

1. [Full Documentation](./JIRA_INTEGRATION.md)
2. Application logs
3. [Jira API Documentation](https://developer.atlassian.com/cloud/jira/platform/rest/v3/)

---

**That's it! You're ready to create Jira tasks from incidents.** 🎉

