"""Template rendering utilities for IMPulse application."""
from jinja2 import Template

from app.incident.incident import Incident


class JinjaTemplate:
    """Jinja2 template wrapper for rendering messages and notifications."""
    
    def __init__(self, template: str):
        self.template = template

    def form_message(self, alert_state, incident: Incident = None):
        """Render a message template with alert state and incident data."""
        template = Template(self.template)
        incident_data = incident.serialize() if incident else {}
        return template.render(payload=alert_state, incident=incident_data)

    def form_notification(self, fields):
        """Render a notification template with provided fields."""
        template = Template(self.template)
        return template.render(fields=fields)
    
    def render(self, **kwargs):
        """Generic render method for any template with provided kwargs."""
        template = Template(self.template)
        return template.render(**kwargs)


# Jira issue templates
jira_summary_template = """
{%- set summary = "" -%}
{%- if incident.payload.groupLabels -%}
  {%- set label_parts = [] -%}
  {%- for key, value in incident.payload.groupLabels.items() -%}
    {%- set _ = label_parts.append(key ~ "=" ~ (value | string)) -%}
  {%- endfor -%}
  {%- set summary = "Alert: " ~ label_parts | join(", ") -%}
{%- endif -%}
{%- if not summary and incident.payload.alerts and incident.payload.alerts | length > 0 -%}
  {%- set first_alert = incident.payload.alerts[0] -%}
  {%- if first_alert.labels.alertname -%}
    {%- set summary = "Alert: " ~ first_alert.labels.alertname -%}
  {%- endif -%}
{%- endif -%}
{%- if not summary -%}
  {%- set summary = "Incident Alert" -%}
{%- endif -%}
{{- summary[:252] ~ "..." if summary | length > 255 else summary -}}
"""

jira_description_template = """
{%- set status_display = incident.status | capitalize -%}
Incident Status: {{ status_display }}
{%- if incident.assigned_fullname %}
Assigned to: {{ incident.assigned_fullname }}
{%- endif %}
Alerts Count: {{ incident.payload.alerts | length if incident.payload.alerts else 0 }}
{%- if incident.link %}
IM Thread: {{ incident.link }}
{%- endif %}

{%- if incident.payload.groupLabels %}

Group Labels:
{%- for key, value in incident.payload.groupLabels.items() %}
- {{ key }}: {{ (value | string)[:197] ~ "..." if (value | string) | length > 200 else value }}
{%- endfor %}
{%- endif %}

{%- if incident.payload.commonAnnotations %}

Annotations:
{%- for key, value in incident.payload.commonAnnotations.items() %}
- {{ key }}: {{ (value | string)[:197] ~ "..." if (value | string) | length > 200 else value }}
{%- endfor %}
{%- endif %}
"""

