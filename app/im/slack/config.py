from jinja2 import Environment

buttons = {
    # styles: normal, danger, primary
    'chain': {
        'takeit': {
            'text': 'Take It',
            'style': 'primary'
        },
        'assigned': {
            'text': 'Take It',
            'style': 'normal'
        },
        'release': {
            'text': 'Release',
            'style': 'primary'
        }
    },
    'status': {
        'enabled': {
            'text': ':large_green_circle: Status',
            'style': 'normal'
        },
        'disabled': {
            'text': ':red_circle: Status',
            'style': 'normal'
        }
    },
    'ticket': {
        'create': {
            'text': ':pushpin:',
            'style': 'normal'
        },
        'open': {
            'text': ':pushpin:',
            'style': 'normal'
        }
    }
}


def slack_normal_text(value):
    return f"{value}"


def slack_bold_text(value):
    return f"*{value}*"


def slack_mention_text(value):
    return f"<@{value}>"


slack_env = Environment()
slack_env.filters['slack_bold_text'] = slack_bold_text
slack_env.filters['slack_mention_text'] = slack_mention_text
slack_admins_template_string = "{{ users | map('slack_mention_text') | join(', ') }}"
