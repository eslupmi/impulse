from jinja2 import Environment


buttons = {
    # styles: normal, danger
    'chain': {
        'enabled': {
            'text': 'Take It',
            'callback_data': 'stop_chain'
        },
        'disabled': {
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
    }
}

telegram_env = Environment()
# TODO: Add the correct template string to include `@` before each username
telegram_admins_template_string = "{{ users | join(', ') }}"
