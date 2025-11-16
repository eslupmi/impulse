from app.im.slack.config import buttons


def reformat_message(original_message, text, attachments, status, chain_enabled, status_enabled, task_link=''):
    from app.config.environment import get_environment_config
    env_config = get_environment_config()
    
    original_message['text'] = text
    original_message['attachments'] = attachments

    original_message['attachments'][1]['actions'][0]['text'] = chain_attrs(chain_enabled, status)[0]
    original_message['attachments'][1]['actions'][0]['style'] = chain_attrs(chain_enabled, status)[1]

    if status_enabled:
        original_message['attachments'][1]['actions'][1]['text'] = buttons['status']['enabled']['text']
        original_message['attachments'][1]['actions'][1]['style'] = buttons['status']['enabled']['style']
    else:
        original_message['attachments'][1]['actions'][1]['text'] = buttons['status']['disabled']['text']
        original_message['attachments'][1]['actions'][1]['style'] = buttons['status']['disabled']['style']
    
    # Update Jira button if present
    if env_config.jira_enabled and len(original_message['attachments'][1]['actions']) > 2:
        if task_link:
            original_message['attachments'][1]['actions'][2]['text'] = buttons['jira']['open']['text']
            original_message['attachments'][1]['actions'][2]['style'] = buttons['jira']['open']['style']
            original_message['attachments'][1]['actions'][2]['url'] = task_link
        else:
            original_message['attachments'][1]['actions'][2]['text'] = buttons['jira']['create']['text']
            original_message['attachments'][1]['actions'][2]['style'] = buttons['jira']['create']['style']
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
