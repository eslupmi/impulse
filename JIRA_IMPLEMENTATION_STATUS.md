# Jira Integration Implementation Status

## Overview

The Jira integration has been refactored to support both **Jira Cloud** (OAuth 2.0) and **Jira Server/Data Center** (OAuth 1.0a).

---

## Implementation Status

### ✅ Jira Cloud (OAuth 2.0) - FULLY IMPLEMENTED

| Feature | Status | Details |
|---------|--------|---------|
| OAuth 2.0 Authorization Flow | ✅ Complete | Authorization URL generation with CSRF protection |
| Token Exchange | ✅ Complete | Exchange authorization code for access token |
| Token Refresh | ✅ Complete | Automatic refresh when access token expires |
| API Authentication | ✅ Complete | Bearer token authentication |
| Task Creation | ✅ Complete | Create Jira issues via REST API |
| In-Memory Token Storage | ✅ Complete | Tokens stored securely in memory |
| OAuth Endpoints | ✅ Complete | `/jira/auth`, `/jira/callback`, `/jira/status` |

### ⚠️ Jira Server (OAuth 1.0a) - REQUIRES IMPLEMENTATION

| Feature | Status | Details |
|---------|--------|---------|
| OAuth 1.0a Framework | ✅ Complete | Base classes and structure in place |
| RSA Key Management | ❌ Not Implemented | Need to load and parse PKCS8 private keys |
| Request Token Generation | ❌ Not Implemented | First step of OAuth 1.0a flow |
| OAuth Signature (RSA-SHA1) | ❌ Not Implemented | Sign requests with RSA private key |
| Authorization URL | ⚠️ Placeholder | Returns placeholder URL |
| Token Exchange | ❌ Not Implemented | Exchange verifier for access token |
| API Authentication | ⚠️ Placeholder | Need to generate OAuth headers with signature |
| Task Creation | ⚠️ Framework Only | Will work once authentication is implemented |

---

## Architecture

### Class Hierarchy

```
JiraClientBase (Abstract Base Class)
│
├── JiraCloudClient (OAuth 2.0)
│   ├── get_authorization_url() ✅
│   ├── exchange_code_for_token() ✅
│   ├── is_authenticated() ✅
│   ├── _get_auth_headers() ✅
│   ├── _refresh_access_token() ✅
│   └── create_issue() ✅ (inherited)
│
└── JiraServerClient (OAuth 1.0a)
    ├── get_authorization_url() ⚠️ Placeholder
    ├── exchange_code_for_token() ❌ Not implemented
    ├── is_authenticated() ✅
    ├── _get_auth_headers() ⚠️ Placeholder
    └── create_issue() ✅ (inherited)

JiraIntegration (Business Logic)
├── format_incident_for_jira() ✅
└── handle_button_press() ✅
```

### Factory Pattern

```python
def create_jira_client(config) -> JiraClientBase:
    if config.jira_type == 'cloud':
        return JiraCloudClient(...)  # ✅ Works
    elif config.jira_type == 'server':
        return JiraServerClient(...)  # ⚠️ Framework only
```

---

## What Works Now

### Jira Cloud Users

1. ✅ Set `JIRA_TYPE=cloud` in environment
2. ✅ Configure OAuth 2.0 credentials
3. ✅ Visit `/jira/auth` to authorize
4. ✅ Create Jira tasks from incidents with 📌 button
5. ✅ Automatic token refresh
6. ✅ Full integration operational

### Jira Server Users

1. ⚠️ Can set `JIRA_TYPE=server` in environment
2. ⚠️ Can configure OAuth 1.0a credentials
3. ❌ **Cannot authorize** (OAuth 1.0a not implemented)
4. ❌ **Cannot create tasks** (requires authentication)
5. ⚠️ Framework is ready for implementation

---

## OAuth 1.0a Implementation Requirements

To complete Jira Server support, the following needs to be implemented in `JiraServerClient`:

### 1. RSA Key Loading

```python
def _load_private_key(self, private_key_str: str):
    """Load RSA private key from PKCS8 format string."""
    # Use cryptography library or similar
    # Parse PEM format private key
    # Store for signing operations
```

**Required Library**: `cryptography` or `pycryptodome`

### 2. Request Token Generation

```python
async def _get_request_token(self) -> tuple[str, str]:
    """
    Request temporary request token from Jira.
    
    Returns:
        Tuple of (request_token, request_token_secret)
    """
    # 1. Generate OAuth parameters (timestamp, nonce, callback)
    # 2. Create signature base string
    # 3. Sign with RSA-SHA1
    # 4. Make POST request to /plugins/servlet/oauth/request-token
    # 5. Parse response (request_token & token_secret)
```

### 3. OAuth Signature Generation

```python
def _generate_oauth_signature(
    self,
    method: str,
    url: str,
    params: Dict[str, str]
) -> str:
    """
    Generate OAuth 1.0a signature using RSA-SHA1.
    
    Args:
        method: HTTP method (GET, POST, etc.)
        url: Request URL
        params: OAuth parameters
    
    Returns:
        Base64-encoded signature
    """
    # 1. Create signature base string
    # 2. Sign with RSA private key using SHA1
    # 3. Base64 encode signature
```

### 4. Authorization Header Generation

```python
async def _get_auth_headers(self, method: str, url: str) -> Dict[str, str]:
    """Generate OAuth 1.0a Authorization header."""
    # 1. Generate OAuth parameters
    # 2. Create signature
    # 3. Build Authorization header
    # Example: Authorization: OAuth oauth_consumer_key="...", oauth_signature="..."
```

### 5. Authorization URL

```python
def get_authorization_url(self) -> str:
    """Generate OAuth 1.0a authorization URL."""
    # 1. Get request token
    # 2. Store request token and secret
    # 3. Return: {base_url}/plugins/servlet/oauth/authorize?oauth_token={token}&state={state}
```

### 6. Token Exchange

```python
async def exchange_code_for_token(self, verifier: str, state: str) -> bool:
    """Exchange OAuth verifier for access token."""
    # 1. Validate state (CSRF protection)
    # 2. Create signature with request token
    # 3. POST to /plugins/servlet/oauth/access-token
    # 4. Parse and store access token + token secret
```

---

## Implementation Guide

### Recommended Approach

1. **Add Dependencies**

   ```bash
   pip install cryptography requests-oauthlib
   ```

2. **Use Existing Libraries**

   Consider using `requests-oauthlib` which has built-in OAuth 1.0a support:

   ```python
   from requests_oauthlib import OAuth1Session
   
   # OAuth 1.0a with RSA-SHA1
   oauth = OAuth1Session(
       client_key=consumer_key,
       rsa_key=private_key,
       signature_method='RSA-SHA1',
       callback_uri=redirect_uri
   )
   ```

3. **Reference Implementation**

   Atlassian provides example code:
   ```bash
   git clone https://bitbucket.org/atlassian_tutorial/atlassian-oauth-examples.git
   cd atlassian-oauth-examples/python
   ```

4. **Testing**

   - Set up a local Jira Server instance or use a test environment
   - Generate RSA keys with OpenSSL
   - Create Application Link in Jira
   - Test the full OAuth flow

---

## Environment Configuration

### Jira Cloud (Working)

```bash
JIRA_TYPE=cloud
JIRA_PROJECT_KEY=DTS
JIRA_REDIRECT_URI=https://yourapp.com/jira/callback
JIRA_CLIENT_ID=...
JIRA_CLIENT_SECRET=...
JIRA_CLOUD_ID=...
```

### Jira Server (Framework Only)

```bash
JIRA_TYPE=server
JIRA_PROJECT_KEY=DTS
JIRA_REDIRECT_URI=https://yourapp.com/jira/callback
JIRA_BASE_URL=https://jira.company.com
JIRA_CONSUMER_KEY=...
JIRA_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----"
```

---

## Testing Checklist

### Jira Cloud
- [x] Authorization URL generation
- [x] OAuth callback handling
- [x] Token exchange
- [x] Token refresh
- [x] API authentication
- [x] Task creation
- [x] Button integration

### Jira Server
- [ ] RSA key loading
- [ ] Request token generation
- [ ] Authorization URL generation
- [ ] OAuth callback handling
- [ ] Token exchange
- [ ] Signature generation
- [ ] API authentication
- [ ] Task creation
- [ ] Button integration

---

## Migration Notes

### For Existing Users

If you were using the previous Cloud-only implementation:

**No action required** - The refactored code is fully backward compatible with Jira Cloud.

### For New Users

1. **Jira Cloud**: Full support, ready to use
2. **Jira Server**: Framework in place, OAuth 1.0a implementation needed

---

## Contributing

Want to implement OAuth 1.0a for Jira Server? Here's how:

1. **Fork the repository**
2. **Implement the methods** marked ❌ in `JiraServerClient`
3. **Add tests** for OAuth 1.0a flow
4. **Update documentation** with Server-specific setup steps
5. **Submit a pull request**

See detailed implementation requirements above.

---

## References

- [Atlassian OAuth 2.0 Documentation](https://developer.atlassian.com/cloud/jira/platform/oauth-2-3lo-apps/)
- [Atlassian OAuth 1.0a Documentation](https://developer.atlassian.com/server/jira/platform/oauth/)
- [OAuth 1.0a with RSA-SHA1 Tutorial](https://developer.atlassian.com/server/jira/platform/oauth/#step-1--configure-jira)
- [Atlassian OAuth Examples](https://bitbucket.org/atlassian_tutorial/atlassian-oauth-examples)

---

## Summary

| Aspect | Jira Cloud | Jira Server |
|--------|------------|-------------|
| **Status** | ✅ Production Ready | ⚠️ Framework Only |
| **OAuth Version** | OAuth 2.0 | OAuth 1.0a |
| **Implementation** | 100% Complete | ~30% Complete |
| **Can Authorize** | ✅ Yes | ❌ No |
| **Can Create Tasks** | ✅ Yes | ❌ No (needs auth) |
| **Recommended For** | All Cloud users | Future implementation |

**Recommendation**: Use **Jira Cloud** for immediate production use. Jira Server support requires OAuth 1.0a implementation.

