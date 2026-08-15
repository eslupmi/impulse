from collections.abc import Iterable
from typing import TYPE_CHECKING, Optional

from jinja2 import Template

if TYPE_CHECKING:
    from app.incident.incident import Incident
    from app.incident.incidents import Incidents


class JinjaTemplate:
    _incidents: Optional['Incidents'] = None

    def __init__(self, template: str):
        self.template = template

    def form_message(self, alert_state, incident: Optional['Incident'] = None):
        """Render a message template with alert state and incident data."""
        template = Template(self.template)
        incident_data = incident.serialize() if incident else {}
        return template.render(payload=alert_state, incident=incident_data, incidents=self._incidents)

    def form_notification(self, **kwargs):
        """Render a thread notification template with the provided context kwargs."""
        template = Template(self.template)
        return template.render(**kwargs)

    def render(self, **kwargs):
        """Generic render method for any template with provided kwargs."""
        template = Template(self.template)
        return template.render(**kwargs)

    @classmethod
    def set_incidents(cls, incidents: Optional['Incidents']):
        """Set incidents storage used to resolve parent/child incident objects in templates."""
        cls._incidents = incidents

    @classmethod
    def related_incidents(cls, uniq_ids: Iterable[str], skip: Iterable[str] = ()) -> dict[str, 'Incident']:
        """Resolve uniq_ids to live Incident objects from the shared incidents store."""
        skip_set = set(skip)
        result = {}
        for uniq_id in uniq_ids:
            if uniq_id in skip_set:
                continue
            incident = cls._incidents.uniq_ids.get(uniq_id) if cls._incidents else None
            if incident is not None:
                result[uniq_id] = incident
        return result
