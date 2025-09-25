# IMPulse Helm Chart

A Helm chart for deploying [IMPulse](https://github.com/your-org/impulse) - an Incident Management Program that integrates with Slack, Mattermost, and Telegram.

## Prerequisites

- Kubernetes 1.19+
- Helm 3.0+
- A container registry with the IMPulse image
- Appropriate messaging platform credentials (Slack, Mattermost, or Telegram)

## Quick Start

### 1. Add the Helm repository
<!-- ### Option 1: From Artifact Hub (Recommended)
```bash
# Add the repository
helm repo add impulse https://artifacthub.io/packages/helm/eslupmi/impulse
helm repo update

# Install with default values
helm install impulse impulse/impulse

# Install with Slack configuration
helm install impulse impulse/impulse -f values-slack.yaml
```

### Option 2: From Local Chart -->
### From Local Chart

```bash
# Clone the repository
git clone https://github.com/eslupmi/impulse
cd impulse
```

### 2. Install the chart

### Option 1: With default values
```bash
helm install impulse impulse/impulse
```

### Option 2: With custom values
```bash
helm install impulse impulse/impulse -f values-slack.yaml
```

## Configuration

### Basic Configuration

The chart supports configuration through the `values.yaml` file. Key configuration sections:

#### Image Configuration
Configure the container image:
```yaml
image:
  repository: ghcr.io/eslupmi/impulse
  pullPolicy: IfNotPresent
  tag: ""  # If empty, will use Chart.AppVersion
```

**Examples:**
- Use Chart.AppVersion: `tag: ""` (default)
- Use specific tag: `tag: "v3.0.0"`
- Use different repository: `repository: "ghcr.io/eslupmi/impulse"`

#### Custom Labels
Add custom labels to all resources:
```yaml
labels:
  environment: production
  team: platform
  cost-center: infra
  owner: devops
```

#### Persistence Configuration
Configure persistent storage:
```yaml
persistence:
  enabled: true
  storageClass: "fast-ssd"
  accessMode: ReadWriteOnce
  size: 10Gi
  name: "my-custom-pvc-name"  # Optional: custom PVC name
```

#### Application Type
Set the messaging platform type:
```yaml
impulseConfig:
  application:
    type: "slack"  # slack, mattermost, telegram, or none
```

#### Secrets Management
Configure API tokens and sensitive data. You can either use inline secrets or reference existing secrets:

**Option 1: Inline Secrets (Default)**
```yaml
secrets:
  inline:
    slack:
      botUserOauthToken: "xoxb-your-token"      # Required
      verificationToken: "your-verification-token"  # Required (used together)
    mattermost:
      accessToken: "your-access-token"
    telegram:
      botToken: "your-bot-token"
```

**Option 2: Existing Secrets (Recommended for Production)**
```yaml
secrets:
  existing:
    slack:
      secretName: "my-slack-secrets"
      botUserOauthTokenKey: "bot-token"
      verificationTokenKey: "verification-token"
    mattermost:
      secretName: "my-mattermost-secrets"
      accessTokenKey: "access-token"
    telegram:
      secretName: "my-telegram-secrets"
      botTokenKey: "bot-token"
```

### Platform-Specific Configuration

#### Slack Configuration
```yaml
impulseConfig:
  application:
    type: "slack"
    admin_users: ["admin_user"]
    users:
      admin_user:
        id: "U1234567890"
    channels:
      incidents_default:
        id: "C1234567890"
    chains:
      default:
        - user: "admin_user"
          wait: "10m"
```

#### Mattermost Configuration
```yaml
impulseConfig:
  application:
    type: "mattermost"
    admin_users: ["admin_user"]
    users:
      admin_user:
        id: "user_id_from_mattermost"
    channels:
      incidents_default:
        id: "channel_id_from_mattermost"
```

#### Telegram Configuration
```yaml
impulseConfig:
  application:
    type: "telegram"
    admin_users: ["admin_user"]
    users:
      admin_user:
        id: "telegram_user_id"
    channels:
      incidents_default:
        id: "telegram_chat_id"
```

### Advanced Configuration

#### Incident Management
```yaml
impulseConfig:
  incident:
    alerts_firing_notifications: false
    alerts_resolved_notifications: true
    timeouts:
      firing: "6h"
      unknown: "6h"
      resolved: "12h"
```

#### Routing Rules
```yaml
impulseConfig:
  route:
    channel: "incidents_default"
    routes:
      - matchers:
          - severity="critical"
        channel: "incidents_critical"
        chain: "critical_chain"
```

#### Webhooks
```yaml
impulseConfig:
  webhooks:
    pagerduty:
      url: "https://events.pagerduty.com/v2/enqueue"
      data:
        routing_key: "{{ env['PAGERDUTY_ROUTING_KEY'] }}"
        event_action: "trigger"
```

#### Template Customization
Customize message templates (works for all platforms):

```yaml
templates:
  header: |
    {%- set commonLabels = payload.get("commonLabels", {}) -%}
    🚨 *{{- commonLabels.alertname -}}* - {{ commonLabels.severity | default("unknown") | upper }}
  
  body: |
    {%- set commonAnnotations = payload.get("commonAnnotations", {}) -%}
    {%- if commonAnnotations.summary %}
    *Summary:* {{ commonAnnotations.summary }}
    {%- endif %}
    
    {%- if commonAnnotations.description %}
    *Description:* {{ commonAnnotations.description }}
    {%- endif %}
  
  status_icons: |
    {%- set status = incident.status -%}
    {%- set status_emoji = {"firing": "🔥", "unknown": "⚠️", "resolved": "✅", "closed": "❌"}[status] -%}
    {{- status_emoji -}}
```

#### UI Configuration
```yaml
impulseConfig:
  ui:
    columns:
      - name: status
        header: Status
        value: incident.status
      - name: alertname
        header: Alert Name
        value: payload.commonLabels.alertname
    sorting:
      - severity: desc
        order: ["info", "warning", "critical"]
    colors:
      severity:
        critical: "#FF0000"
        warning: "#FFA500"
        info: "#00FF00"
```

## Installation Examples

### Slack Setup
```bash
# Copy and modify the Slack example
cp values-slack.yaml my-slack-values.yaml
# Edit my-slack-values.yaml with your Slack configuration
helm install impulse impulse/impulse -f my-slack-values.yaml
```

### Mattermost Setup
```bash
# Copy and modify the Mattermost example
cp values-mattermost.yaml my-mattermost-values.yaml
# Edit my-mattermost-values.yaml with your Mattermost configuration
helm install impulse impulse/impulse -f my-mattermost-values.yaml
```

### Using Existing Secrets
```bash
# Use existing secrets (recommended for production)
cp values-existing-secrets.yaml my-existing-secrets-values.yaml
# Edit my-existing-secrets-values.yaml with your secret references
helm install impulse impulse/impulse -f my-existing-secrets-values.yaml
```



### Production Setup
```bash
# Use production-ready configuration
helm install impulse impulse/impulse -f values-production.yaml
```

## Security

### Secret Management
For production deployments, consider using external secret management solutions:

- [External Secrets Operator](https://external-secrets.io/)
- [Sealed Secrets](https://github.com/bitnami-labs/sealed-secrets)
- [HashiCorp Vault](https://www.vaultproject.io/)

### Network Policies
Enable network policies for production:
```yaml
networkPolicy:
  enabled: true
  ingressRules:
    - from:
        - namespaceSelector:
            matchLabels:
              name: monitoring
      ports:
        - protocol: TCP
          port: 5000
```

### Security Context
Use security contexts for production:
```yaml
securityContext:
  runAsNonRoot: true
  runAsUser: 1000
  capabilities:
    drop:
      - ALL
  readOnlyRootFilesystem: true
```

### Health Checks
The chart includes liveness and readiness probes:
- Liveness probe: HTTP GET on `/queue`
- Readiness probe: HTTP GET on `/queue`

## Support

- [Documentation](https://docs.impulse.bot)
- [GitHub Issues](https://github.com/eslupmi/impulse/issues)
- [Helm Chart Repository](https://artifacthub.io/packages/helm/eslupmi/impulse)
