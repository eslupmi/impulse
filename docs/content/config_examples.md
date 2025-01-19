# Examples

**minimal Slack configuration**

```yaml
route:
  channel: space

application:
  type: slack
  admin_users:
  - Dmitry_Tsybus
  channels:
    space: {id: C09NSUL269T}
  users:
    Dmitry_Tsybus: {full_name: "Dmitry Tsybus"}
```

**minimal Mattermost configuration**

```yaml


route:
  channel: space

application:
  impulse_address: https://impulse.yourdomain.com # IMPulse address where Mattermost will send button events
  address: https://mattermost.yourdomain.com # your Mattermost address
  type: mattermost
  admin_users:
  - Dmitry_Tsybus
  channels:
    space: {id: w8gvebq58fgo9civ8begs6renw}
  users:
    Dmitry_Tsybus: {username: "ditsi"}
```
