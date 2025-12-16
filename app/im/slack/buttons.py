from app.im.slack.config import buttons
from app.config.environment import get_environment_config
from app.config.config import get_config
from app.time import format_freeze_expiration


def reformat_message(original_message, text, attachments, status, chain_enabled, frozen_until, task_link=''):
    env_config = get_environment_config()
    config = get_config()
    
    original_message['text'] = text
    original_message['attachments'] = attachments

    original_message['attachments'][1]['actions'][0]['text'] = chain_attrs(chain_enabled, status)[0]
    original_message['attachments'][1]['actions'][0]['style'] = chain_attrs(chain_enabled, status)[1]

    # Update freeze button - change type based on frozen state
    if frozen_until:
        freeze_text = format_freeze_expiration(frozen_until)
        original_message['attachments'][1]['actions'][1] = {
            'name': 'freeze',
            'type': 'button',
            'text': freeze_text,
            'style': 'primary',
        }
    else:
        freeze_text = buttons['freeze']['inactive']['text']
        freeze_options = [
            {"text": opt['text'], "value": opt['value']}
            for opt in buttons['freeze']['options']
        ]
        original_message['attachments'][1]['actions'][1] = {
            'name': 'freeze',
            'type': 'select',
            'text': freeze_text,
            'style': buttons['freeze']['inactive']['style'],
            'options': freeze_options
        }
    
    if config.app.task_management and env_config.task_management_enabled and len(original_message['attachments'][1]['actions']) > 2:
        if task_link:
            original_message['attachments'][1]['actions'][2]['text'] = buttons['task']['open']['text']
            original_message['attachments'][1]['actions'][2]['style'] = buttons['task']['open']['style']
            original_message['attachments'][1]['actions'][2]['url'] = task_link
        else:
            original_message['attachments'][1]['actions'][2]['text'] = buttons['task']['create']['text']
            original_message['attachments'][1]['actions'][2]['style'] = buttons['task']['create']['style']
            # Remove url if it exists
            original_message['attachments'][1]['actions'][2].pop('url', None)
    
    return original_message


def chain_attrs(chain_enabled, status):
    if chain_enabled:
        chain_text = buttons['chain']['takeit']['text']
        chain_style = buttons['chain']['takeit']['style']
    else:
        if status != 'resolved':
            chain_text = buttons['chain']['assigned']['text']
            chain_style = buttons['chain']['assigned']['style']
        else:
            chain_text = buttons['chain']['release']['text']
            chain_style = buttons['chain']['release']['style']
    return chain_text, chain_style
