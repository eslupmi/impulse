from config import ui_config


def get_incident_table_config():
    tabulator_config = []
    for field in ui_config['labels']:
        tabulator_config.append({
            'title': field['text'],
            'field': field['name'],
        })
    return tabulator_config
