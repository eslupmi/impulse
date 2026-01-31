from jinja2 import Environment


buttons = {
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
    'freeze': {
        'inactive': {
            'text': 'Freeze',
            'callback_data': 'freeze_menu'
        },
        'inhibited': {
            'text': '❄️ Inhibited',
            'callback_data': 'noop'
        },
        'options': [
            {'text': 'Tomorrow', 'callback_data': 'freeze_tomorrow'},
            {'text': 'Next Monday', 'callback_data': 'freeze_next_monday'},
            {'text': 'In Month', 'callback_data': 'freeze_month'},
            {'text': 'In 6 months', 'callback_data': 'freeze_6months'},
            {'text': '« Back', 'callback_data': 'freeze_back'}
        ]
    },
    'task': {
        'create': {
            'text': '📌',
            'callback_data': 'task'
        }
    }
}

telegram_env = Environment()
telegram_admins_template_string = "{{ users | join(', ') }}"
