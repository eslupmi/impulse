# Overview

## What is IMPulse?

IMPulse - an Incident Management Platform that processes [Alertmanager](https://prometheus.io/docs/alerting/latest/alertmanager/) alerts and creates incidents in messengers.

![None](https://github.com/eslupmi/site/blob/main/static/ui.png?raw=true)

If you want to understand how IMPulse works see [Concepts](concepts.md).

## Features

- Mattermost, Slack, Telegram integrations
- Twilio and another integrations using [webhooks](https://docs.impulse.bot/latest/config_file/#webhooks-examples)
- [Incident lifecycle](https://docs.impulse.bot/latest/concepts/#lifecycle) reduces incidents chaos
- Scheduling using providers like Google Calendar via [cloud chains](https://docs.impulse.bot/latest/config_file/#cloud-chain)
- Support for [nested chains](https://docs.impulse.bot/latest/config_file/#nested-chain) with unlimited depth
- Flexible [message structure](https://docs.impulse.bot/latest/concepts/#structure) you can modify
- Customizable [UI](features/ui.md) with multi-level sorting and advanced filtering capabilities
