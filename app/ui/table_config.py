from config import ui_config


def get_incident_table_config():
    """
    Get the table configuration for the incidents table.

    Returns:
        dict: The configuration for the incidents table.
    """
    tabulator_config = []
    for field in ui_config['columns']:
        tabulator_config.append({
            'title': field['header'],
            'field': field['name'],
            'type': field.get('type'),
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

        if order:
            tabulator_sorting.append({
                "column": column,
                "order": order,
            })
        elif direction:
            tabulator_sorting.append({
                "column": column,
                "sort": direction,
            })

    return tabulator_sorting

