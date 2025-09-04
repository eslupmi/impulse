from jinja2 import Environment


buttons = {
    # styles: normal, danger
    'chain': {
        'takeit': {
            'text': 'Take',
            'callback_data': 'stop_chain'
        },
        'release': {
            'text': 'Release',
            'callback_data': 'start_chain'
        }
    },
    'status': {
        'enabled': {
            'text': '🔔 ON',
            'callback_data': 'stop_status'
        },
        'disabled': {
            'text': '🔕 OFF',
            'callback_data': 'start_status'
        }
    },
    'silence': {
        'mute': {
            'text': '🔇 Mute',
            'callback_data': 'silence'
        },
        'mute_url': {
            'text': '🔇 Mute',
            'url': None  # Will be set dynamically
        }
    }
}

telegram_env = Environment()
# TODO: Add the correct template string to include `@` before each username
telegram_admins_template_string = "{{ users | join(', ') }}"
