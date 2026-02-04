"""Tests for Jinja template utilities."""
import pytest
from types import SimpleNamespace
from unittest.mock import Mock

from app.incident.incident import Incident
from app.jinja_template import load_template_file, JinjaTemplate


class TestLoadTemplateFile:
    """Test the load_template_file function."""
    
    def test_load_existing_template(self):
        """Test loading an existing template file."""
        template_content = load_template_file('jira_summary.j2')
        assert template_content is not None
        assert len(template_content) > 0
        assert 'incident' in template_content
        
    def test_load_jira_description_template(self):
        """Test loading the jira_description.j2 template."""
        template_content = load_template_file('jira_description.j2')
        assert template_content is not None
        assert 'incident' in template_content
        assert 'Common Labels' in template_content or 'Links' in template_content
        
    def test_load_nonexistent_template(self):
        """Test loading a nonexistent template file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError) as exc_info:
            load_template_file('nonexistent_template.j2')
        assert 'Template file not found' in str(exc_info.value)


class TestJinjaTemplate:
    """Test the JinjaTemplate class."""
    
    def test_render_simple_template(self):
        """Test rendering a simple template."""
        template = JinjaTemplate("Hello {{ name }}!")
        result = template.render(name="World")
        assert result == "Hello World!"
        
    def test_render_with_incident_data(self):
        """Test rendering with incident object."""
        template_str = "Status: {{ incident.status }}"
        template = JinjaTemplate(template_str)

        class MockIncident(Mock):
            def __init__(self, *args, **kwargs):
                kwargs.setdefault("spec", Incident)
                super().__init__(*args, **kwargs)

        mock_incident = MockIncident()
        mock_incident.serialize.return_value = {"status": "firing"}

        result = template.render(incident=mock_incident)
        assert result == "Status: firing"

    def test_render_raises_for_non_serializable_incident(self):
        """Test strict behavior: incident must provide dict-like serialize() output."""
        template = JinjaTemplate("Status: {{ incident.status }}")
        mock_incident = Mock()
        mock_incident.status = "firing"
        with pytest.raises(TypeError):
            template.render(incident=mock_incident)

    def test_form_message_resolves_parent_and_child_incidents(self):
        """Test parents/childs are available as uniq_id -> incident object maps."""
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
            result = template.form_message({"status": "firing"}, mock_incident)
        finally:
            JinjaTemplate.set_incidents(None)

        assert result == "Parent: firing, Child: resolved"

    def test_render_resolves_parent_and_child_incidents(self):
        """Test generic render also resolves parents/childs incident object maps."""
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
            result = template.render(incident=mock_incident)
        finally:
            JinjaTemplate.set_incidents(None)

        assert result == "Parent: firing, Child: resolved"
