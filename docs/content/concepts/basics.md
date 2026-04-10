# Basics

IMPulse is installed between <abbr title="see menu INTEGRATIONS/Alert Sources">**alert source**</abbr> and a <abbr title="see menu INTEGRATIONS/Messengers">**messenger**</abbr> to create [Incidents](incident.md) entity.

## Alertmanager example

![None](../media/impulse.excalidraw.svg)

In this example, IMPulse receives alerts from Alertmanager and sends them to your messenger channel based on `messenger` and `route` configuration (see [Configuration File](../config_file.md)).

Alertmanager sends alerts with one of two statuses: **firing** and **resolved**. Based on these statuses, IMPulse creates [Incidents](incident.md). The first Incident status is always **firing** when a problem occurs.

<p align="center"><img src="../../media/slack_firing.excalidraw.svg" alt="" width="400"/></p>
