from .buttons import buttons

status_colors = {
    'firing': '#f61f1f',
    'unknown': '#c1a300',
    'resolved': '#56c15e',
    'closed': '#969696',
    'deleted': '#969696',
    'frozen': '#38ade6',
}


def mattermost_get_button_update_payload(incident, body, header, status_icons, callback_url):
    actions = _build_mattermost_actions(incident, callback_url)
    attachment = _attachment(incident, body, actions)
    return {
        'update': {
            'message': f'{status_icons} {header}',
            'props': {'attachments': [attachment]},
        }
    }


def mattermost_get_create_thread_payload(incident, body, header, status_icons, callback_url):
    actions = _build_mattermost_actions(incident, callback_url)
    return {
        'channel_id': incident.channel_id,
        'message': f'{status_icons} {header}',
        'props': {'attachments': [_attachment(incident, body, actions)]},
    }


def mattermost_get_update_payload(incident, body, header, status_icons, callback_url):
    actions = _build_mattermost_actions(incident, callback_url)
    return {
        'channel_id': incident.channel_id,
        'id': incident.thread_id,
        'message': f'{status_icons} {header}',
        'props': {'attachments': [_attachment(incident, body, actions)]},
    }


def _attachment(incident, body, actions):
    display_status = 'frozen' if incident.frozen else incident.status
    attachment = {
        'fallback': 'test',
        'text': body,
        'color': status_colors.get(display_status),
    }
    if actions:
        attachment['actions'] = actions
    return attachment


def _build_mattermost_actions(incident, callback_url):
    if incident.status == 'closed':
        return []

    chain_text, chain_style = _chain_attrs(incident.chain_enabled, incident.status)
    if incident.frozen_by_inhibition:
        chain_style = 'default'

    actions = [{
        'id': 'chain',
        'type': 'button',
        'name': chain_text,
        'style': chain_style,
        'integration': {'url': callback_url, 'context': {'action': 'chain'}},
    }]

    if incident.frozen_by_maintenance:
        actions.append(_freeze_button('Maintenance', {'action': 'noop'}, callback_url))
    elif incident.frozen_by_inhibition:
        actions.append(_freeze_button(buttons['freeze']['inhibited']['text'], {'action': 'noop'}, callback_url))
    elif incident.can_unfreeze:
        actions.append(_freeze_button(incident.frozen_until_text, {'action': 'unfreeze'}, callback_url))
    else:
        actions.append({
            'id': 'freeze',
            'type': 'select',
            'name': buttons['freeze']['inactive']['text'],
            'style': buttons['freeze']['inactive']['style'],
            'integration': {'url': callback_url, 'context': {}},
            'options': [
                {'text': opt['text'], 'value': f"freeze_{opt['value']}"}
                for opt in buttons['freeze']['options']
            ],
        })

    if incident.can_create_task and not incident.task_link:
        actions.append({
            'id': 'task',
            'type': 'button',
            'name': buttons['task']['create']['text'],
            'style': buttons['task']['create']['style'],
            'integration': {'url': callback_url, 'context': {'action': 'task'}},
        })
    return actions


def _freeze_button(text, context, callback_url):
    return {
        'id': 'freeze',
        'type': 'button',
        'name': text,
        'style': buttons['freeze']['inactive']['style'],
        'integration': {'url': callback_url, 'context': context},
    }


def _chain_attrs(chain_enabled, status):
    if chain_enabled:
        return buttons['chain']['takeit']['text'], buttons['chain']['takeit']['style']
    if status != 'resolved':
        return buttons['chain']['assigned']['text'], buttons['chain']['assigned']['style']
    return buttons['chain']['release']['text'], buttons['chain']['release']['style']
