"""Tests for Jinja template utilities."""
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.incident.incident import Incident
from app.jinja_template import JinjaTemplate, encode_mattermost_markdown_link_urls

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"


@contextmanager
def parent_child_incident_context():
    template_str = (
        "Parent: {{ incident.parents['parent-1'].status }}, "
        "Child: {{ incident.childs['child-1'].status }}"
    )
    template = JinjaTemplate(template_str)

    class MockIncident(Mock):
        def __init__(self, *args, **kwargs):
            kwargs.setdefault("spec", Incident)
            super().__init__(*args, **kwargs)

    incidents = SimpleNamespace(
        uniq_ids={
            "parent-1": SimpleNamespace(status="firing"),
            "child-1": SimpleNamespace(status="resolved"),
        }
    )

    JinjaTemplate.set_incidents(incidents)
    try:
        mock_incident = MockIncident()
        mock_incident.parents = ["parent-1"]
        mock_incident.childs = ["child-1"]
        mock_incident.serialize.return_value = {"parents": ["parent-1"], "childs": ["child-1"]}
        yield template, mock_incident
    finally:
        JinjaTemplate.set_incidents(None)


class TestJinjaTemplate:
    """Test the JinjaTemplate class."""

    def test_render_simple_template(self):
        """Test rendering a simple template."""
        template = JinjaTemplate("Hello {{ name }}!")
        result = template.render(name="World")
        assert result == "Hello World!"


class TestEncodeMattermostMarkdownLinkUrls:
    def test_encodes_quotes_in_markdown_link_url(self):
        raw = '[task](https://youtrack.example/issue?q="slowpoke")'
        encoded = encode_mattermost_markdown_link_urls(raw)
        assert encoded == '[task](https://youtrack.example/issue?q=%22slowpoke%22)'

    def test_preserves_already_percent_encoded_urls(self):
        raw = '[task](https://example.com/path?q=%22foo%22)'
        encoded = encode_mattermost_markdown_link_urls(raw)
        assert encoded == raw

    def test_leaves_plain_text_without_links_unchanged(self):
        text = 'job "slowpoke" fired on host-1'
        assert encode_mattermost_markdown_link_urls(text) == text

    def test_mattermost_body_template_encodes_task_link_globally(self):
        template = JinjaTemplate(
            (TEMPLATES_DIR / "mattermost_body.j2").read_text(),
            encode_markdown_link_urls=True,
        )
        payload = {
            "commonAnnotations": {"summary": "summary"},
            "commonLabels": {},
            "alerts": [{"labels": {"instance": "host-1"}, "annotations": {}}],
        }
        incident = Mock(spec=Incident)
        incident.serialize = lambda: {
            "task_link": 'https://youtrack.example/issue?q="slowpoke"',
            "assigned_user": "",
            "parents": [],
            "childs": [],
        }
        rendered = template.form_message(payload, incident)
        assert '[task](https://youtrack.example/issue?q=%22slowpoke%22)' in rendered

    def test_slack_body_template_does_not_encode_links(self):
        template = JinjaTemplate((TEMPLATES_DIR / "slack_body.j2").read_text())
        payload = {
            "commonAnnotations": {"summary": "summary"},
            "commonLabels": {},
            "alerts": [{"labels": {"instance": "host-1"}, "annotations": {}}],
        }
        incident = Mock(spec=Incident)
        incident.serialize = lambda: {
            "task_link": 'https://youtrack.example/issue?q="slowpoke"',
            "assigned_user_id": "",
            "parents": [],
            "childs": [],
        }
        rendered = template.form_message(payload, incident)
        assert '<https://youtrack.example/issue?q="slowpoke"|task>' in rendered
