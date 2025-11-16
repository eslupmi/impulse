from jinja2 import Environment


buttons = {
    # styles: normal, danger
    'chain': {
        'takeit': {
            'text': 'Take It',
            'callback_data': 'stop_chain'
        },
        'release': {
            'text': 'Release',
            'callback_data': 'start_chain'
        }
    },
    'status': {
        'enabled': {
            'text': '🟢 Status',
            'callback_data': 'stop_status'
        },
        'disabled': {
            'text': '🔴 Status',
            'callback_data': 'start_status'
        }
    },
    'jira': {
        'create': {
            'text': '📌',
            'callback_data': 'jira'
        },
        'open': {
            'text': '📌',
            'callback_data': 'jira'
        }
    }
}

telegram_env = Environment()
telegram_admins_template_string = "{{ users | join(', ') }}"
