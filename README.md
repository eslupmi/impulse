<h1><img alt="IMPulse" src="logo.svg" width="50"> IMPulse</h1>

 [![Website](https://img.shields.io/badge/website-impulse.bot-blue)](https://impulse.bot) [![Docs](https://img.shields.io/badge/docs-docs.impulse.bot-blue)](https://docs.impulse.bot)

[![Container](https://img.shields.io/badge/docker-ghcr.io%2Feslupmi%2Fimpulse-blue?logo=docker)](https://ghcr.io/eslupmi/impulse) [![Community Helm](https://img.shields.io/badge/community-artifacthub.io-blue?style=flat&logo=helm)](https://artifacthub.io/packages/helm/impulse/impulse)

<!-- [![Sonar](https://sonarcloud.io/api/project_badges/measure?project=eslupmi_impulse&metric=alert_status&branch=master&label=)](https://sonarcloud.io/dashboard?id=eslupmi_impulse&branch=master) -->

<div align="center"><img src="https://github.com/eslupmi/site/blob/main/static/preview.png?raw=true" width="700"></div>

## Quick Start

Run without messenger integration:

```bash
# Prepare "impulse" directory
git clone https://github.com/eslupmi/impulse.git impulse.bak
mkdir -p impulse/config impulse/data
cp impulse.bak/examples/docker-compose.yml impulse/docker-compose.yml
cp impulse.bak/examples/impulse.none.yml impulse/config/impulse.yml
rm -rf impulse.bak

# Replace "<release_tag>" with the latest stable Docker tag
tag=$(git ls-remote --tags https://github.com/eslupmi/impulse.git | awk -F/ '{print $NF}' | tail -n1)
sed -i "s|<release_tag>|$tag|" impulse/docker-compose.yml

# Run IMPulse without messenger integration
cd impulse
docker compose up
```

Now IMPulse is available at http://localhost:5000/.

You can try to send a test alert with:

```bash
curl -XPOST -H "Content-Type: application/json" http://localhost:5000/ -d '{"receiver":"webhook-alerts","status":"firing","alerts":[{"status":"firing","labels":{"alertname":"InstanceDown4","instance":"localhost:9100","job":"node","severity":"warning"},"annotations":{"summary":"Instanceunavailable"},"startsAt":"2024-07-28T19:26:43.604Z","endsAt":"0001-01-01T00:00:00Z","generatorURL":"http://eva:9090/graph?g0.expr=up+%3D%3D+0&g0.tab=1","fingerprint":"a7ddb1de342424cb"}],"groupLabels":{"alertname":"InstanceDown"},"commonLabels":{"alertname":"InstanceDown","instance":"localhost:9100","job":"node","severity":"warning"},"commonAnnotations":{"summary":"Instanceunavailable"},"externalURL":"http://eva:9093","version":"4","groupKey":"{}:{alertname=\"InstanceDown\"}","truncatedAlerts":0}'
```

See [documentation](https://docs.impulse.bot) and the Slack [example](https://github.com/eslupmi/impulse/blob/develop/examples/impulse.slack.yml) to configure IMPulse for your messenger.
