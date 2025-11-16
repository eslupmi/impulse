# Jira OAuth Integration Setup

This document describes how to set up and use the Jira OAuth integration for creating tasks from incidents.

## Overview

The Jira integration supports both **Jira Cloud** and **Jira Server/Data Center**:

- **Jira Cloud**: Uses OAuth 2.0 (✅ Fully implemented)
- **Jira Server/Data Center**: Uses OAuth 1.0a (⚠️ Requires additional implementation)

## Choosing Your Jira Type

Set the `JIRA_TYPE` environment variable to specify your Jira deployment:

```bash
JIRA_TYPE=cloud    # For Jira Cloud (default)
# or
JIRA_TYPE=server   # For Jira Server/Data Center
```

---

## Jira Cloud Setup (OAuth 2.0) ✅

### Environment Variables

```bash
# Jira type
JIRA_TYPE=cloud

# Common fields
JIRA_PROJECT_KEY=YOUR_PROJECT_KEY      # e.g., "DTS", "ECS"
JIRA_REDIRECT_URI=https://yourapp.com/jira/callback

# Jira Cloud OAuth 2.0 fields
JIRA_CLIENT_ID=your_client_id          # From Jira OAuth app
JIRA_CLIENT_SECRET=your_client_secret  # From Jira OAuth app
JIRA_CLOUD_ID=your_cloud_id           # Jira cloud instance ID
```

### How to Get Cloud Credentials

#### 1. Create OAuth App in Jira

1. Go to https://developer.atlassian.com/console/myapps/
2. Click "Create" → "OAuth 2.0 integration"
3. Configure your app:
   - **App name**: Your application name
   - **Authorization URL**: Add `https://yourapp.com/jira/callback` to allowed redirect URLs
   - **Permissions**: Select the following scopes:
     - `read:jira-work`
     - `write:jira-work`
     - `read:jira-user`
4. Save and note the **Client ID** and **Client Secret**

#### 2. Get Cloud ID

After creating the OAuth app and authorizing it:

1. Make a request to: `https://api.atlassian.com/oauth/token/accessible-resources`
2. Use your access token to authenticate
3. Extract the `id` field (this is your `cloud_id`)

Alternatively, you can get it from your Jira URL:
- URL format: `https://your-domain.atlassian.net/`
- The cloud ID can be obtained via the accessible resources API after initial authorization

#### 3. Get Project Key

In your Jira project, the key is visible in the URL:
- Example: `https://your-domain.atlassian.net/browse/DTS-123`
- The project key is **DTS**

### OAuth 2.0 Flow

```
1. User visits: https://yourapp.com/jira/auth
   ↓
2. Redirected to Jira's authorization page
   ↓
3. User clicks "Allow" to grant permissions
   ↓
4. Jira redirects to: https://yourapp.com/jira/callback?code=...&state=...
   ↓
5. Application exchanges code for access_token & refresh_token
   ↓
6. Tokens stored in memory (not persisted)
   ↓
7. User can now create Jira tasks by clicking the 📌 button
```

### Setup Instructions

1. **Configure Environment Variables**

   Create or update your `.env` file with the values above.

2. **Start the Application**

   ```bash
   python main.py
   ```

   You'll see: `Jira cloud integration initialized. OAuth authorization required.`

3. **Authorize the Application**

   Visit in your browser:
   ```
   https://yourapp.com/jira/auth
   ```

   - Click "Allow" on Jira's authorization page
   - You'll be redirected back with a success message

4. **Verify Authentication**

   ```bash
   curl https://yourapp.com/jira/status
   ```

   Response:
   ```json
   {
     "enabled": true,
     "authenticated": true
   }
   ```

5. **Create Tasks from Incidents**

   - Open any incident thread
   - Click the 📌 button to create a Jira task
   - Click again to open the existing task

---

## Jira Server/Data Center Setup (OAuth 1.0a) ⚠️

### Status: Requires Additional Implementation

OAuth 1.0a for Jira Server requires **RSA-SHA1 signature generation**, which needs additional implementation. The framework is in place, but the following components need to be completed:

#### What's Needed

1. **RSA Key Pair Generation** (OpenSSL)
2. **OAuth 1.0a Signature Generation** with RSA-SHA1
3. **3-Legged OAuth Flow** Implementation
4. **Request Token → Access Token Exchange**

### Environment Variables (When Implemented)

```bash
# Jira type
JIRA_TYPE=server

# Common fields
JIRA_PROJECT_KEY=YOUR_PROJECT_KEY
JIRA_REDIRECT_URI=https://yourapp.com/jira/callback

# Jira Server OAuth 1.0a fields
JIRA_BASE_URL=https://jira.company.com
JIRA_CONSUMER_KEY=your_consumer_key
JIRA_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\nYour PKCS8 private key here\n-----END PRIVATE KEY-----"
```

### OAuth 1.0a Flow (To Be Implemented)

According to [Atlassian's OAuth 1.0a documentation](https://developer.atlassian.com/server/jira/platform/oauth/):

1. Generate RSA key pair (public/private keys)
2. Create Application Link in Jira with public key
3. Request token → User authorization → Access token exchange
4. Sign all API requests with RSA-SHA1 signature

### Implementation Recommendations

To implement OAuth 1.0a, consider using:

- **Python Library**: [`requests-oauthlib`](https://requests-oauthlib.readthedocs.io/) with RSA signature method
- **Manual Implementation**: Follow [Atlassian's OAuth tutorial](https://developer.atlassian.com/server/jira/platform/oauth/)

Reference implementation from Atlassian (Java):
```bash
git clone https://bitbucket.org/atlassian_tutorial/atlassian-oauth-examples.git
```

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/jira/auth` | GET | Initiate OAuth flow |
| `/jira/callback` | GET | OAuth callback endpoint |
| `/jira/status` | GET | Check authentication status |

## Using the Integration

### Creating Jira Tasks from Incidents

Once authenticated, a pin button (📌) will appear in incident threads.

- **First Click:** Creates a new Jira task
- **Subsequent Clicks:** Opens the existing Jira task

The Jira task will include:
- **Summary:** Incident title (from alert labels)
- **Description:**
  - Incident status
  - Assigned user
  - Number of alerts
  - Link to the incident thread
  - Group labels

## Token Management

### Jira Cloud (OAuth 2.0)

- **Access Tokens:** Stored in memory, expire after 1 hour
- **Refresh Tokens:** Automatically used to get new access tokens when expired
- **Persistence:** Tokens are not persisted to disk (in-memory only)
- **After Restart:** Re-authorization required

### Jira Server (OAuth 1.0a)

- **Access Tokens:** Valid until revoked
- **Token Secret:** Used for request signing
- **Persistence:** Tokens are not persisted to disk (in-memory only)
- **After Restart:** Re-authorization required

## Security Considerations

1. **CSRF Protection:** OAuth state parameter prevents CSRF attacks
2. **HTTPS Required:** OAuth redirect URI must use HTTPS in production
3. **Token Storage:** Tokens are kept in memory only, not written to disk
4. **Scopes:** Limited to read/write Jira work and read user info

## Troubleshooting

### "Jira is not authenticated"

If you see this message when clicking the pin button:
1. Visit `/jira/auth` to initiate authorization
2. Grant permissions in Jira
3. Try clicking the pin button again

### "OAuth state mismatch"

This indicates a potential CSRF attack or expired authorization session:
1. Clear browser cookies
2. Start a fresh authorization flow at `/jira/auth`

### Authentication Lost After Restart

This is expected behavior. Tokens are stored in memory only:
1. Visit `/jira/auth` to re-authorize after each restart
2. For persistent authentication, consider implementing token persistence

### Jira Server Not Working

OAuth 1.0a requires additional implementation:
1. Check the implementation status above
2. Consider using Jira Cloud if OAuth 1.0a is not yet implemented
3. Or contribute the OAuth 1.0a implementation!

## Architecture

### Class Hierarchy

```
JiraClientBase (Abstract)
├── JiraCloudClient (OAuth 2.0) ✅ Fully implemented
└── JiraServerClient (OAuth 1.0a) ⚠️ Requires RSA signing

JiraIntegration
└── Uses JiraClientBase (works with both Cloud and Server)
```

### Factory Pattern

The `create_jira_client()` factory function creates the appropriate client based on `JIRA_TYPE`:

```python
from app.integrations.jira import create_jira_client

# Returns JiraCloudClient or JiraServerClient
jira_client = create_jira_client(env_config)
```

## Development Notes

- OAuth 2.0 implementation follows [Atlassian's Cloud documentation](https://developer.atlassian.com/cloud/jira/platform/oauth-2-3lo-apps/)
- OAuth 1.0a implementation follows [Atlassian's Server documentation](https://developer.atlassian.com/server/jira/platform/oauth/)
- Uses `RateLimitedClient` for API requests
- Handles token refresh automatically on 401 responses (Cloud only)
- Non-blocking task creation with async queue processing

## Contributing

If you'd like to implement OAuth 1.0a for Jira Server:

1. Implement RSA-SHA1 signature generation in `JiraServerClient`
2. Complete the `get_authorization_url()` method with request token generation
3. Implement `exchange_code_for_token()` with access token exchange
4. Implement `_get_auth_headers()` with OAuth 1.0a signature
5. Test with a Jira Server/Data Center instance
6. Submit a pull request!

## References

- [Atlassian OAuth 2.0 Documentation (Cloud)](https://developer.atlassian.com/cloud/jira/platform/oauth-2-3lo-apps/)
- [Atlassian OAuth 1.0a Documentation (Server)](https://developer.atlassian.com/server/jira/platform/oauth/)
- [Jira Cloud REST API](https://developer.atlassian.com/cloud/jira/platform/rest/v2/)
- [Jira Server REST API](https://docs.atlassian.com/software/jira/docs/api/REST/latest/)
