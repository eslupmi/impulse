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
    'ticket': {
        'create': {
            'text': '📌',
            'callback_data': 'ticket'
        },
        'open': {
            'text': '📌',
            'callback_data': 'ticket'
        }
    }
}

telegram_env = Environment()
telegram_admins_template_string = "{{ users | join(', ') }}"
