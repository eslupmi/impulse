from typing import Optional, TYPE_CHECKING
from urllib.parse import quote

from jinja2 import Environment


def _urlencode_filter(value):
    return quote(str(value), safe=":/?#[]@!$&'()*+,;=.-_~%")


# Messenger templates emit Slack mrkdwn, Mattermost markdown, and Telegram HTML — not
# web-page HTML. Jinja HTML autoescape breaks that markup (see v3.5.1 regression).
# Templates are operator-configured; dynamic values come from the alerting pipeline.
_jinja_env = Environment(autoescape=False)  # NOSONAR python:S5439 - not HTML output
_jinja_env.filters["urlencode"] = _urlencode_filter

if TYPE_CHECKING:
    from app.incident.incident import Incident
    from app.incident.incidents import Incidents


class JinjaTemplate:
    _incidents: Optional['Incidents'] = None

    def __init__(self, template: str):
        self.template = template

    def form_message(self, alert_state, incident: Optional['Incident'] = None):
        """Render a message template with alert state and incident data."""
        template = _jinja_env.from_string(self.template)
        incident_data = incident.serialize() if incident else {}
        return template.render(payload=alert_state, incident=incident_data, incidents=self._incidents)

    def form_notification(self, fields):
        """Render a notification template with provided fields."""
        template = _jinja_env.from_string(self.template)
        return template.render(fields=fields)

    def render(self, **kwargs):
        """Generic render method for any template with provided kwargs."""
        template = _jinja_env.from_string(self.template)
        return template.render(**kwargs)

    @classmethod
    def set_incidents(cls, incidents: Optional['Incidents']):
        """Set incidents storage used to resolve parent/child incident objects in templates."""
        cls._incidents = incidents
