from config import ui_config


def get_incident_table_config():
    tabulator_config = []
    for field in ui_config['columns']:
        tabulator_config.append({
            'title': field['header'],
            'field': field['name'],
            'type': field.get('type'),
        })
    return tabulator_config
