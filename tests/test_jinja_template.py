"""Tests for Jinja template utilities."""
from types import SimpleNamespace
from unittest.mock import Mock

from app.incident.freeze import MAINTENANCE_PARENT_SENTINEL
from app.incident.incident import Incident
from app.jinja_template import JinjaTemplate


class TestJinjaTemplate:
    def test_render_simple_template(self):
        template = JinjaTemplate("Hello {{ name }}!")
        result = template.render(name="World")
        assert result == "Hello World!"

    def test_form_message_passes_parents_and_childs(self):
        template = JinjaTemplate(
            "Parent: {{ parents['parent-1'].status }}, Child: {{ childs['child-1'].status }}"
        )
        parent = SimpleNamespace(status="firing")
        child = SimpleNamespace(status="resolved")
        JinjaTemplate.set_incidents(SimpleNamespace(uniq_ids={"parent-1": parent, "child-1": child}))
        try:
            incident = Mock(spec=Incident)
            incident.parents = [MAINTENANCE_PARENT_SENTINEL, "parent-1"]
            incident.childs = ["child-1"]
            incident.serialize.return_value = {}
            result = template.form_message({}, incident)
        finally:
            JinjaTemplate.set_incidents(None)

        assert result == "Parent: firing, Child: resolved"
