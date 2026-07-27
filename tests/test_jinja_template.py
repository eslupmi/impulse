"""Tests for Jinja template utilities."""
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.incident.incident import Incident
from app.jinja_template import JinjaTemplate


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

    def test_autoescape_disabled_by_default(self):
        template = JinjaTemplate('<a href="{{ url }}">link</a>')
        result = template.render(url='https://example.com?q="x"&y=1')
        assert result == '<a href="https://example.com?q="x"&y=1">link</a>'

    def test_autoescape_escapes_html_attribute_values(self):
        template = JinjaTemplate('<a href="{{ url }}">link</a>', autoescape=True)
        result = template.render(url='https://example.com?q="x"&y=1')
        assert result == '<a href="https://example.com?q=&#34;x&#34;&amp;y=1">link</a>'

    def test_autoescape_preserves_literal_html_tags(self):
        template = JinjaTemplate('<b>{{ text }}</b>', autoescape=True)
        result = template.render(text='Summary <script>')
        assert result == '<b>Summary &lt;script&gt;</b>'

