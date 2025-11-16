# Jira Integration Environment Variables

## Jira Cloud Configuration (OAuth 2.0) ✅

Use this configuration for Jira Cloud instances:

```bash
# Jira type
JIRA_TYPE=cloud

# Common fields
JIRA_PROJECT_KEY=DTS
JIRA_REDIRECT_URI=https://yourapp.com/jira/callback

# OAuth 2.0 credentials from Atlassian Developer Console
JIRA_CLIENT_ID=your_client_id_here
JIRA_CLIENT_SECRET=your_client_secret_here
JIRA_CLOUD_ID=your_cloud_id_here
```

### How to Get These Values

1. **Create OAuth App**: https://developer.atlassian.com/console/myapps/
2. **Get Client ID & Secret**: From your OAuth app settings
3. **Get Cloud ID**: From accessible resources API after authorization
4. **Set Redirect URI**: Add `https://yourapp.com/jira/callback` to allowed URIs

---

## Jira Server Configuration (OAuth 1.0a) ⚠️

Use this configuration for Jira Server/Data Center instances:

> **Note**: OAuth 1.0a requires additional implementation. See [JIRA_OAUTH_SETUP.md](./JIRA_OAUTH_SETUP.md) for details.

```bash
# Jira type
JIRA_TYPE=server

# Common fields
JIRA_PROJECT_KEY=DTS
JIRA_REDIRECT_URI=https://yourapp.com/jira/callback

# Jira Server base URL
JIRA_BASE_URL=https://jira.company.com

# OAuth 1.0a credentials from Application Links
JIRA_CONSUMER_KEY=your_consumer_key
JIRA_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----
MIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQC...
... your PKCS8 private key here ...
-----END PRIVATE KEY-----"
```

### How to Get These Values

1. **Generate RSA Key Pair**: Use OpenSSL (see setup guide)
2. **Create Application Link**: In Jira Settings → Applications → Application links
3. **Configure Consumer Key**: Set in Application Link configuration
4. **Add Public Key**: Paste your RSA public key

---

## Quick Start

1. **Choose your Jira type** (cloud or server)
2. **Copy the appropriate configuration** to your `.env` file
3. **Replace placeholder values** with your actual credentials
4. **Start the application**: `python main.py`
5. **Authorize**: Visit `https://yourapp.com/jira/auth`
6. **Create tasks**: Click the 📌 button in incident threads

---

## Verification

Check if Jira is properly configured:

```bash
curl https://yourapp.com/jira/status
```

Expected response:
```json
{
  "enabled": true,
  "authenticated": true
}
```

---

## Troubleshooting

### Configuration Not Loading

- Ensure all required environment variables are set
- Check for typos in variable names
- Restart the application after changing `.env`

### Authentication Fails

- Verify OAuth credentials are correct
- Check redirect URI matches exactly (including HTTPS)
- Ensure proper scopes/permissions are configured

### Server OAuth Not Working

- OAuth 1.0a requires additional implementation
- See implementation status in [JIRA_OAUTH_SETUP.md](./JIRA_OAUTH_SETUP.md)
- Consider using Jira Cloud if Server is not yet supported

---

For detailed setup instructions, see [JIRA_OAUTH_SETUP.md](./JIRA_OAUTH_SETUP.md)

