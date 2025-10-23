"""
Unit tests for app.ui.table_config module.
"""
from unittest.mock import Mock, patch

import pytest

from app.ui.table_config import (
    get_all_ui_config, get_incident_table_config, get_incident_table_sorting,
    get_incident_table_colors, get_incident_table_filters
)
from tests.utils import create_mock_config


class TestTableConfig:
    """Test cases for table_config module functions."""

    @patch('app.ui.table_config.get_config')
    def test_get_all_ui_config(self, mock_get_config):
        """Test getting all UI configuration."""
        # Use utility function for mock config
        mock_config = create_mock_config()
        mock_ui_config = Mock()
        mock_ui_config.columns = []
        mock_ui_config.sorting = []
        mock_ui_config.colors = {}
        mock_ui_config.filters = []
        mock_config.ui_config = mock_ui_config
        mock_get_config.return_value = mock_config

        result = get_all_ui_config()

        assert 'table_config' in result
        assert 'sorting' in result
        assert 'colors' in result
        assert 'filters' in result

    @patch('app.ui.table_config.get_config')
    def test_get_incident_table_config_default(self, mock_get_config):
        """Test getting incident table config with default indicator column."""
        # Use utility function for mock config
        mock_config = create_mock_config()
        mock_ui_config = Mock()
        mock_ui_config.columns = None
        mock_config.ui_config = mock_ui_config
        mock_get_config.return_value = mock_config

        result = get_incident_table_config()

        assert len(result) == 1
        assert result[0]['field'] == 'indicator'
        assert result[0]['type'] == 'indicator'
        assert result[0]['headerSort'] is False

    @patch('app.ui.table_config.get_config')
    def test_get_incident_table_config_with_columns(self, mock_get_config):
        """Test getting incident table config with custom columns."""
        # Use utility function for mock config
        mock_config = create_mock_config()

        # Create mock column objects
        mock_column1 = Mock()
        mock_column1.name = 'status'
        mock_column1.type = 'string'
        mock_column1.header = 'Status'
        mock_column1.visible = True

        mock_column2 = Mock()
        mock_column2.name = 'link'
        mock_column2.type = 'link'
        mock_column2.header = 'Link'
        mock_column2.visible = True

        mock_column3 = Mock()
        mock_column3.name = 'created'
        mock_column3.type = 'datetime'
        mock_column3.header = 'Created'
        mock_column3.format = 'absolute'
        mock_column3.visible = True

        mock_ui_config = Mock()
        mock_ui_config.columns = [mock_column1, mock_column2, mock_column3]
        mock_config.ui_config = mock_ui_config
        mock_get_config.return_value = mock_config

        result = get_incident_table_config()

        # Should have indicator + 3 custom columns + 1 URL field for link
        assert len(result) == 5

        # Check indicator column
        assert result[0]['field'] == 'indicator'

        # Check string column
        string_col = next(col for col in result if col['field'] == 'status')
        assert string_col['title'] == 'Status'
        assert string_col['type'] == 'string'
        assert string_col['visible'] is True

        # Check link column
        link_col = next(col for col in result if col['field'] == 'link')
        assert link_col['title'] == 'Link'
        assert link_col['type'] == 'link'
        assert link_col['urlField'] == 'linkUrl'

        # Check URL field for link
        url_col = next(col for col in result if col['field'] == 'linkUrl')
        assert url_col['title'] == 'LinkUrl'
        assert url_col['visible'] is False

        # Check datetime column
        datetime_col = next(col for col in result if col['field'] == 'created')
        assert datetime_col['title'] == 'Created'
        assert datetime_col['type'] == 'datetime'
        assert datetime_col['formatType'] == 'absolute'

    @patch('app.ui.table_config.get_config')
    def test_get_incident_table_config_with_visible_false(self, mock_get_config):
        """Test getting incident table config with visible=False column."""
        # Use utility function for mock config
        mock_config = create_mock_config()

        mock_column = Mock()
        mock_column.name = 'hidden_field'
        mock_column.type = 'string'
        mock_column.header = 'Hidden Field'
        mock_column.visible = False

        mock_ui_config = Mock()
        mock_ui_config.columns = [mock_column]
        mock_config.ui_config = mock_ui_config
        mock_get_config.return_value = mock_config

        result = get_incident_table_config()

        # Should have indicator + 1 custom column
        assert len(result) == 2

        # Check hidden column
        hidden_col = next(col for col in result if col['field'] == 'hidden_field')
        assert hidden_col['visible'] is False

    @patch('app.ui.table_config.get_config')
    def test_get_incident_table_config_with_none_visible(self, mock_get_config):
        """Test getting incident table config with visible=None (defaults to True)."""
        # Use utility function for mock config
        mock_config = create_mock_config()

        mock_column = Mock()
        mock_column.name = 'default_field'
        mock_column.type = 'string'
        mock_column.header = 'Default Field'
        mock_column.visible = None

        mock_ui_config = Mock()
        mock_ui_config.columns = [mock_column]
        mock_config.ui_config = mock_ui_config
        mock_get_config.return_value = mock_config

        result = get_incident_table_config()

        # Check default visible column
        default_col = next(col for col in result if col['field'] == 'default_field')
        assert default_col['visible'] is True

    @patch('app.ui.table_config.get_config')
    def test_get_incident_table_config_with_none_type(self, mock_get_config):
        """Test getting incident table config with type=None (defaults to string)."""
        # Use utility function for mock config
        mock_config = create_mock_config()

        mock_column = Mock()
        mock_column.name = 'default_type_field'
        mock_column.type = None
        mock_column.header = 'Default Type Field'
        mock_column.visible = True

        mock_ui_config = Mock()
        mock_ui_config.columns = [mock_column]
        mock_config.ui_config = mock_ui_config
        mock_get_config.return_value = mock_config

        result = get_incident_table_config()

        # Check default type column
        default_type_col = next(col for col in result if col['field'] == 'default_type_field')
        assert default_type_col['type'] == 'string'

    @patch('app.ui.table_config.get_config')
    def test_get_incident_table_config_with_none_format(self, mock_get_config):
        """Test getting incident table config with format=None (defaults to relative)."""
        # Use utility function for mock config
        mock_config = create_mock_config()

        mock_column = Mock()
        mock_column.name = 'default_format_field'
        mock_column.type = 'datetime'
        mock_column.header = 'Default Format Field'
        mock_column.format = None
        mock_column.visible = True

        mock_ui_config = Mock()
        mock_ui_config.columns = [mock_column]
        mock_config.ui_config = mock_ui_config
        mock_get_config.return_value = mock_config

        result = get_incident_table_config()

        # Check default format column
        default_format_col = next(col for col in result if col['field'] == 'default_format_field')
        assert default_format_col['formatType'] == 'relative'

    @patch('app.ui.table_config.get_config')
    def test_get_incident_table_sorting_empty(self, mock_get_config):
        """Test getting incident table sorting with no sorting rules."""
        # Use utility function for mock config
        mock_config = create_mock_config()
        mock_ui_config = Mock()
        mock_ui_config.sorting = None
        mock_config.ui_config = mock_ui_config
        mock_get_config.return_value = mock_config

        result = get_incident_table_sorting()

        assert result == []

    @patch('app.ui.table_config.get_config')
    def test_get_incident_table_sorting_with_rules(self, mock_get_config):
        """Test getting incident table sorting with sorting rules."""
        # Use utility function for mock config
        mock_config = create_mock_config()

        # Create mock sorting rules
        mock_rule1 = Mock()
        mock_rule1.column_name = 'status'
        mock_rule1.sort_order = 'asc'
        mock_rule1.order = 1

        mock_rule2 = Mock()
        mock_rule2.column_name = 'created'
        mock_rule2.sort_order = 'desc'
        mock_rule2.order = 2

        mock_rule3 = Mock()
        mock_rule3.column_name = 'severity'
        mock_rule3.sort_order = 'none'
        mock_rule3.order = 3

        mock_ui_config = Mock()
        mock_ui_config.sorting = [mock_rule1, mock_rule2, mock_rule3]
        mock_config.ui_config = mock_ui_config
        mock_get_config.return_value = mock_config

        result = get_incident_table_sorting()

        assert len(result) == 3

        # Check first rule
        assert result[0]['column'] == 'status'
        assert result[0]['direction'] == 'asc'
        assert result[0]['order'] == 1

        # Check second rule
        assert result[1]['column'] == 'created'
        assert result[1]['direction'] == 'desc'
        assert result[1]['order'] == 2

        # Check third rule (none direction)
        assert result[2]['column'] == 'severity'
        assert 'direction' not in result[2]
        assert result[2]['order'] == 3

    @patch('app.ui.table_config.get_config')
    def test_get_incident_table_sorting_without_order(self, mock_get_config):
        """Test getting incident table sorting without order field."""
        # Use utility function for mock config
        mock_config = create_mock_config()

        mock_rule = Mock()
        mock_rule.column_name = 'status'
        mock_rule.sort_order = 'asc'
        mock_rule.order = None

        mock_ui_config = Mock()
        mock_ui_config.sorting = [mock_rule]
        mock_config.ui_config = mock_ui_config
        mock_get_config.return_value = mock_config

        result = get_incident_table_sorting()

        assert len(result) == 1
        assert result[0]['column'] == 'status'
        assert result[0]['direction'] == 'asc'
        assert 'order' not in result[0]

    @patch('app.ui.table_config.get_config')
    def test_get_incident_table_colors_with_colors(self, mock_get_config):
        """Test getting incident table colors with colors configured."""
        # Use utility function for mock config
        mock_config = create_mock_config()

        colors = {
            'firing': '#ff0000',
            'resolved': '#00ff00',
            'unknown': '#ffff00'
        }

        mock_ui_config = Mock()
        mock_ui_config.colors = colors
        mock_config.ui_config = mock_ui_config
        mock_get_config.return_value = mock_config

        result = get_incident_table_colors()

        assert result == colors

    @patch('app.ui.table_config.get_config')
    def test_get_incident_table_colors_without_colors(self, mock_get_config):
        """Test getting incident table colors without colors configured."""
        # Use utility function for mock config
        mock_config = create_mock_config()
        mock_ui_config = Mock()
        mock_ui_config.colors = None
        mock_config.ui_config = mock_ui_config
        mock_get_config.return_value = mock_config

        result = get_incident_table_colors()

        assert result == {}

    @patch('app.ui.table_config.get_config')
    def test_get_incident_table_filters_with_filters(self, mock_get_config):
        """Test getting incident table filters with filters configured."""
        # Use utility function for mock config
        mock_config = create_mock_config()

        filters = [
            {'field': 'status', 'type': 'select', 'values': ['firing', 'resolved']},
            {'field': 'severity', 'type': 'input', 'placeholder': 'Enter severity'}
        ]

        mock_ui_config = Mock()
        mock_ui_config.filters = filters
        mock_config.ui_config = mock_ui_config
        mock_get_config.return_value = mock_config

        result = get_incident_table_filters()

        assert result == filters

    @patch('app.ui.table_config.get_config')
    def test_get_incident_table_filters_without_filters(self, mock_get_config):
        """Test getting incident table filters without filters configured."""
        # Use utility function for mock config
        mock_config = create_mock_config()
        mock_ui_config = Mock()
        mock_ui_config.filters = None
        mock_config.ui_config = mock_ui_config
        mock_get_config.return_value = mock_config

        result = get_incident_table_filters()

        assert result == []
