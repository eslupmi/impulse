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
    'freeze': {
        'inactive': {
            'text': 'Freeze',
            'style': 'normal'
        },
        'inhibited': {
            'text': ':snowflake: Inhibited',
            'style': 'normal'
        },
        'options': [
            {'text': 'Tomorrow', 'value': 'tomorrow'},
            {'text': 'Next Monday', 'value': 'next_monday'},
            {'text': 'In Month', 'value': 'month'},
            {'text': 'In 6 months', 'value': '6months'}
        ]
    },
    'task': {
        'create': {
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
