"""Tests for Jinja template utilities."""
import pytest
from pathlib import Path

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
        assert 'Incident Status' in template_content
        assert 'Group Labels' in template_content
        
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
        
        # Create a mock incident object
        class MockIncident:
            status = "firing"
        
        result = template.render(incident=MockIncident())
        assert result == "Status: firing"

