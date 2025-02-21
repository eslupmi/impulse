from config import ui_config


def get_incident_table_config():
    """
    Get the table configuration for the incidents table.

    Returns:
        dict: The configuration for the incidents table.
    """
    tabulator_config = [{
        'title': '',
        'field': 'indicator',
        'type': 'indicator',
        'headerSort': False
    }]

    for field in ui_config['columns']:
        field_name = field['name']
        field_type = field.get('type')
        if field_type == 'link':
            tabulator_config.append({
                'title': field['header'],
                'field': field_name,
                'type': field_type,
                'urlField': f'{field_name}Url',
            })
            tabulator_config.append({
                'title': f'{field["header"]}Url',
                'field': f'{field_name}Url',
                'visible': False,
            })
        elif field_type == 'datetime':
            tabulator_config.append({
                'title': field['header'],
                'field': field_name,
                'type': field_type,
                'formatType': field.get('format', 'absolute'),
            })
        else:
            tabulator_config.append({
                'title': field['header'],
                'field': field_name,
                'type': field_type,
            })

    return tabulator_config


def get_incident_table_sorting():
    """
    Convert sorting configuration to a format compatible with Tabulator's JavaScript sorting logic.

    Returns:
        list: A list of Tabulator-compatible sorting configurations.
    """
    tabulator_sorting = []

    for rule in ui_config.get("sorting", []):
        column = rule.get("column")
        order = rule.get("order", None)
        direction = rule.get("sort", None)

        sorting_rule = {
            "column": column,
        }

        if order:
            sorting_rule["order"] = order
        if direction:
            sorting_rule["direction"] = direction

        tabulator_sorting.append(sorting_rule)
    return tabulator_sorting

def get_incident_table_colors():
    """
    Get the colors for the incidents table.

    Returns:
        dict: The colors for the incidents table.
    """
    return ui_config.get('colors', {})

def get_incident_table_filters():
    """
    Get the filters for the incidents table.

    Returns:
        dict: The filters for the incidents table.
    """
    return ui_config.get('filters', [])
