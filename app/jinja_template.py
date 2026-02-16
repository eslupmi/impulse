"""Template rendering utilities for IMPulse application."""
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from jinja2 import Template

from app.incident.incident import Incident
from app.incident.incidents import Incidents

if TYPE_CHECKING:
    from app.incident.incidents import Incidents


class JinjaTemplate:
    _incidents: Optional['Incidents'] = None

    def __init__(self, template: str):
        self.template = template

    @classmethod
    def set_incidents(cls, incidents: Optional['Incidents']):
        """Set incidents storage used to resolve parent/child incident objects in templates."""
        cls._incidents = incidents

    def form_message(self, alert_state, incident: Incident = None):
        """Render a message template with alert state and incident data."""
        template = Template(self.template)
        incident_data = incident.serialize() if incident else {}
        return template.render(payload=alert_state, incident=incident_data, incidents=self._incidents)

    def form_notification(self, fields):
        """Render a notification template with provided fields."""
        template = Template(self.template)
        return template.render(fields=fields)

    def render(self, **kwargs):
        """Generic render method for any template with provided kwargs."""
        template = Template(self.template)
        return template.render(**kwargs)
