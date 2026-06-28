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
        
