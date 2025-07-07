# Overview

## What is IMPulse?

IMPulse - an Incident Management Program that processes [Alertmanager](https://prometheus.io/docs/alerting/latest/alertmanager/) alerts and creates incidents in messengers.

![None](https://github.com/eslupmi/site/blob/main/static/ui.png?raw=true)

If you want to understand how IMPulse works see [Concepts](concepts.md).

## Features

- Mattermost, Slack, Telegram integrations
- Twilio and another integrations using [webhooks](config_file.md/#webhooks-examples)
- [Incident lifecycle](concepts.md/#lifecycle) reduces incidents chaos
- Scheduling using providers like Google Calendar via [cloud chains](config_file.md/#cloud-chain)
- Support for [nested chains](config_file.md/#nested-chain) with unlimited depth
- Flexible [message structure](concepts.md/#structure) you can modify
- Customizable [UI](ui.md) with multi-column sorting and advanced filtering capabilities
