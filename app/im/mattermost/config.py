from jinja2 import Environment

from config import mattermost_access_token

mattermost_headers = {
    'Content-Type': 'application/json',
    'Authorization': f'Bearer {mattermost_access_token}',
}
buttons = {
    # styles: good, warning, danger, default, primary, and success
    'chain': {
        'takeit': {
            'text': 'Take It',
            'style': 'primary'
        },
        'assigned': {
            'text': 'Take It',
            'style': 'default'
        },
        'release': {
            'text': 'Release',
            'style': 'primary'
        }
    },
    'status': {
        'enabled': {
            'text': ':large_green_circle: Status',
            'style': 'default'
        },
        'disabled': {
            'text': ':red_circle: Status',
            'style': 'default'
        }
    }
}
mattermost_request_delay = 0.5  # seconds


def mattermost_bold_text(value):
    return f"**{value}**"


def mattermost_mention_text(value):
    return f"@{value}"


mattermost_env = Environment()
mattermost_env.filters['mattermost_bold_text'] = mattermost_bold_text
mattermost_env.filters['mattermost_mention_text'] = mattermost_mention_text
mattermost_admins_template_string = "{{ users | map('mattermost_mention_text') | join(', ') }}"
