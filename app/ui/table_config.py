from app.config.config import get_config
from app.config.environment import get_environment_config


def get_all_ui_config():
    """
    Get all UI configuration in a single response.

    Returns:
        dict: Complete UI configuration including table config, sorting, colors, filters, and features.
    """
    config = get_config()
    env_config = get_environment_config()
    return {
        'table_config': _get_incident_table_config(),
        'sorting': _get_incident_table_sorting(),
        'colors': _get_incident_table_colors(),
        'filters': _get_incident_table_filters(),
        'features': {
            'task_management': bool(config.app.task_management and env_config.task_management_enabled),
        },
    }


def _get_incident_table_config():
    """
    Get the table configuration for the incidents table.

    Returns:
        dict: The configuration for the incidents table.
    """
    config = get_config()
    ui_config = config.ui_config
    
    tabulator_config = [{
        'title': '',
        'field': 'indicator',
        'type': 'indicator',
        'headerSort': False
    }]

    if ui_config and ui_config.columns:
        for field in ui_config.columns:
            field_name = field.name
            field_type = field.type or 'string'
            field_visible = field.visible if field.visible is not None else True
            if field_type == 'link':
                tabulator_config.append({
                    'title': field.header,
                    'field': field_name,
                    'type': field_type,
                    'urlField': f'{field_name}Url',
                })
                tabulator_config.append({
                    'title': f'{field.header}Url',
                    'field': f'{field_name}Url',
                    'visible': False,
                })
            elif field_type == 'datetime':
                tabulator_config.append({
                    'title': field.header,
                    'field': field_name,
                    'type': field_type,
                    'formatType': field.format or 'relative',
                })
            else:
                tabulator_config.append({
                    'title': field.header,
                    'field': field_name,
                    'type': field_type,
                    'visible': field_visible,
                })

    return tabulator_config


def _get_incident_table_sorting():
    """
    Convert sorting configuration to a format compatible with Tabulator's JavaScript sorting logic.

    Returns:
        list: A list of Tabulator-compatible sorting configurations.
    """
    config = get_config()
    ui_config = config.ui_config
    
    tabulator_sorting = []

    if ui_config and ui_config.sorting:
        for rule in ui_config.sorting:
            # rule is now a UISorting object, not a dict
            sorting_rule = {"column": rule.column_name}
            
            if rule.sort_order in ["asc", "desc"]:
                sorting_rule["direction"] = rule.sort_order
                if rule.order:
                    sorting_rule["order"] = rule.order
            elif rule.sort_order == "none" and rule.order:
                sorting_rule["order"] = rule.order
            
            tabulator_sorting.append(sorting_rule)
    
    return tabulator_sorting

def _get_incident_table_colors():
    """
    Get the colors for the incidents table.

    Returns:
        dict: The colors for the incidents table.
    """
    config = get_config()
    ui_config = config.ui_config
    
    if ui_config and ui_config.colors:
        return ui_config.colors
    return {}

def _get_incident_table_filters():
    """
    Get the filters for the incidents table.

    Returns:
        dict: The filters for the incidents table.
    """
    config = get_config()
    ui_config = config.ui_config
    
    if ui_config and ui_config.filters:
        return ui_config.filters
    return []
