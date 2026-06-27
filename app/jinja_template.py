import re
from typing import Optional, TYPE_CHECKING
from urllib.parse import quote

from jinja2 import Environment

_MARKDOWN_LINK_RE = re.compile(r'\[([^\]]*)\]\(([^)]+)\)')


def _urlencode_url(value: str) -> str:
    return quote(str(value), safe=":/?#[]@!$&'()*+,;=.-_~%")


def encode_mattermost_markdown_link_urls(text: str) -> str:
    """Encode URLs in Markdown [label](url) links for Mattermost mobile rendering."""
    if not text:
        return text

    def replace_link(match: re.Match[str]) -> str:
        label, url = match.group(1), match.group(2)
        return f'[{label}]({_urlencode_url(url)})'

    return _MARKDOWN_LINK_RE.sub(replace_link, text)


_jinja_env = Environment(autoescape=False)  # NOSONAR python:S5439 - not HTML output

if TYPE_CHECKING:
    from app.incident.incident import Incident
    from app.incident.incidents import Incidents


class JinjaTemplate:
    _incidents: Optional['Incidents'] = None

    def __init__(self, template: str, encode_markdown_link_urls: bool = False):
        self.template = template
        self._encode_markdown_link_urls = encode_markdown_link_urls

    def form_message(self, alert_state, incident: Optional['Incident'] = None):
        """Render a message template with alert state and incident data."""
        template = _jinja_env.from_string(self.template)
        incident_data = incident.serialize() if incident else {}
        rendered = template.render(payload=alert_state, incident=incident_data, incidents=self._incidents)
        return self._finalize(rendered)

    def form_notification(self, fields):
        """Render a notification template with provided fields."""
        template = _jinja_env.from_string(self.template)
        rendered = template.render(fields=fields)
        return self._finalize(rendered)

    def render(self, **kwargs):
        """Generic render method for any template with provided kwargs."""
        template = _jinja_env.from_string(self.template)
        rendered = template.render(**kwargs)
        return self._finalize(rendered)

    def _finalize(self, rendered: str) -> str:
        if self._encode_markdown_link_urls:
            return encode_mattermost_markdown_link_urls(rendered)
        return rendered

    @classmethod
    def set_incidents(cls, incidents: Optional['Incidents']):
        """Set incidents storage used to resolve parent/child incident objects in templates."""
        cls._incidents = incidents
