from .buttons import buttons, chain_attrs

status_colors = {
    'firing': '#f61f1f',
    'unknown': '#c1a300',
    'resolved': '#56c15e',
    'closed': '#969696',
    'deleted': '#969696',
    'frozen': '#38ade6',
}

def get_incident_message_payload(incident, body, header, status_icons, tz_str):
    actions = _build_slack_actions(incident, tz_str)
    display_status = 'frozen' if incident.frozen else incident.status

    attachments = [
        {
            'color': status_colors.get(display_status),
            'text': body,
            'mrkdwn_in': ['text'],
        }
    ]
    if actions:
        attachments.append({
            'color': status_colors.get(display_status),
            'text': '',
            'callback_id': 'buttons',
            'actions': actions
        })

    payload = {
        'channel': incident.channel_id,
        'text': f'{status_icons} {header}',
        'attachments': attachments
    }
    return payload

def slack_get_update_payload(incident, body, header, status_icons, tz_str):
    actions = _build_slack_actions(incident, tz_str)
    display_status = 'frozen' if incident.frozen else incident.status

    attachments = [
        {
            'color': status_colors.get(display_status),
            'text': body,
            'mrkdwn_in': ['text'],
        }
    ]
    if actions:
        attachments.append({
            'color': status_colors.get(display_status),
            'text': '',
            "callback_id": "buttons",
            "actions": actions,
        })

    payload = {
        'channel': incident.channel_id,
        'text': f'{status_icons} {header}',
        'attachments': attachments,
        'ts': incident.thread_id,
    }
    return payload


def _build_slack_actions(incident, tz_str: str = "UTC"):
    if incident.status == 'closed':
        return []

    chain_text, chain_style = chain_attrs(incident.chain_enabled, incident.status)
    if incident.frozen_by_inhibition:
        chain_style = 'normal'
    
    actions = [
        {
            "name": 'chain',
            "type": 'button',
            "text": chain_text,
            "style": chain_style,
        }
    ]
    
    if incident.frozen_by_maintenance:
        freeze_text = 'Maintenance'
        actions.append({
            "name": 'freeze',
            "type": 'button',
            "text": freeze_text,
            "style": buttons['freeze']['inhibited']['style'],
        })
    elif incident.frozen_by_inhibition:
        actions.append({
            "name": 'freeze',
            "type": 'button',
            "text": buttons['freeze']['inhibited']['text'],
            "style": buttons['freeze']['inhibited']['style'],
        })
    elif incident.can_unfreeze:
        freeze_text = incident.frozen_until_text
        actions.append({
            "name": 'freeze',
            "type": 'button',
            "text": freeze_text,
            "style": 'primary',
        })
    else:
        freeze_text = buttons['freeze']['inactive']['text']
        freeze_options = [
            {"text": opt['text'], "value": opt['value']}
            for opt in buttons['freeze']['options']
        ]
        actions.append({
            "name": 'freeze',
            "type": 'select',
            "text": freeze_text,
            "style": buttons['freeze']['inactive']['style'],
            "options": freeze_options
        })
    
    if incident.can_create_task and not incident.task_link:
        actions.append({
            "name": "task",
            "text": buttons['task']['create']['text'],
            "type": "button",
            "style": buttons['task']['create']['style']
        })
    
    return actions
