"""Template rendering utilities for IMPulse application."""
from pathlib import Path
from typing import Dict, Optional, TYPE_CHECKING

from jinja2 import Template

from app.incident.incident import Incident

if TYPE_CHECKING:
    from app.incident.incidents import Incidents


class JinjaTemplate:
    """Jinja2 template wrapper for rendering messages and notifications."""
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
        incident_data = self._build_incident_data(incident) if incident else {}
        return template.render(payload=alert_state, incident=incident_data)

    def form_notification(self, fields):
        """Render a notification template with provided fields."""
        template = Template(self.template)
        return template.render(fields=fields)

    def render(self, **kwargs):
        """Generic render method for any template with provided kwargs."""
        template = Template(self.template)
        incident = kwargs.get('incident')
        if incident:
            kwargs = dict(kwargs)
            kwargs['incident'] = self._build_incident_data(incident)
        return template.render(**kwargs)

    def _build_incident_data(self, incident: Incident) -> Dict:
        """Build incident data for template context with resolved parent/child objects."""
        incident_data = incident.serialize()
        incident_data['parents'] = self._build_related_map(getattr(incident, 'parents', []))
        incident_data['childs'] = self._build_related_map(getattr(incident, 'childs', []))
        return incident_data

    def _build_related_map(self, relation_ids) -> Dict[str, Incident]:
        """Convert relation uniq_id list to dict of uniq_id -> Incident object."""
        if not self._incidents:
            return {}

        if isinstance(relation_ids, dict):
            relation_keys = relation_ids.keys()
        else:
            relation_keys = relation_ids or []

        related_incidents: Dict[str, Incident] = {}
        for uniq_id in relation_keys:
            related_incident = self._incidents.uniq_ids.get(uniq_id)
            if related_incident:
                related_incidents[uniq_id] = related_incident
        return related_incidents


def load_template_file(filename: str) -> str:
    """
    Load a template file from the templates directory.
    
    Args:
        filename: Name of the template file (e.g., 'jira_summary.j2')
        
    Returns:
        Template content as string
        
    Raises:
        FileNotFoundError: If template file doesn't exist
    """
    # Get the project root directory (parent of app directory)
    app_dir = Path(__file__).parent
    project_root = app_dir.parent
    template_path = project_root / 'templates' / filename

    if not template_path.exists():
        raise FileNotFoundError(f"Template file not found: {template_path}")

    with open(template_path, 'r', encoding='utf-8') as f:
        return f.read()
