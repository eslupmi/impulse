from app.im.colors import status_colors
from app.im.slack.buttons import chain_attrs
from app.im.slack.config import buttons


def slack_get_update_payload(channel_id, ts, body, header, status_icons, status, chain_enabled=True,
                             status_enabled=True):
    payload = {
        'channel': channel_id,
        'text': f'{status_icons} {header}',
        'attachments': [
            {
                'color': status_colors.get(status),
                'text': body,
                'mrkdwn_in': ['text'],
            },
            {
                'color': status_colors.get(status),
                'text': '',
                "callback_id": "buttons",
                "actions": [
                    {
                        "name": 'chain',
                        "type": 'button',
                        "text": chain_attrs(chain_enabled, status)[0],
                        "style": chain_attrs(chain_enabled, status)[1],
                    },
                    {
                        "name": 'status',
                        "type": 'button',
                        "text": buttons['status']['enabled']['text'] if status_enabled else
                        buttons['status']['disabled']['text'],
                        "style": buttons['status']['enabled']['style'] if status_enabled else
                        buttons['status']['disabled']['style'],
                    }
                ],
            },
        ],
        'ts': ts,
    }
    return payload


def slack_get_create_thread_payload(channel_id, body, header, status_icons, status):
    payload = {
        'channel': channel_id,
        'text': f'{status_icons} {header}',
        'attachments': [
            {
                'color': status_colors.get(status),
                'text': body,
                'mrkdwn_in': ['text'],
            },
            {
                'color': status_colors.get(status),
                'text': '',
                'callback_id': 'buttons',
                'actions': [
                    {
                        "name": "chain",
                        "text": buttons['chain']['takeit']['text'],
                        "type": "button",
                        "style": buttons['chain']['takeit']['style']
                    },
                    {
                        "name": "status",
                        "text": buttons['status']['enabled']['text'],
                        "type": "button",
                        "style": buttons['status']['enabled']['style']
                    }
                ]
            }
        ]
    }
    return payload
