from app.im.slack.config import buttons
from app.logging import logger
from config import slack_verification_token


def reformat_message(original_message, text, attachments, chain_enabled, status_enabled):
    original_message['text'] = text
    original_message['attachments'] = attachments

    if chain_enabled:
        original_message['attachments'][1]['actions'][0]['text'] = buttons['chain']['enabled']['text']
        original_message['attachments'][1]['actions'][0]['style'] = buttons['chain']['enabled']['style']
    else:
        original_message['attachments'][1]['actions'][0]['text'] = buttons['chain']['disabled']['text']
        original_message['attachments'][1]['actions'][0]['style'] = buttons['chain']['disabled']['style']

    if status_enabled:
        original_message['attachments'][1]['actions'][1]['text'] = buttons['status']['enabled']['text']
        original_message['attachments'][1]['actions'][1]['style'] = buttons['status']['enabled']['style']
    else:
        original_message['attachments'][1]['actions'][1]['text'] = buttons['status']['disabled']['text']
        original_message['attachments'][1]['actions'][1]['style'] = buttons['status']['disabled']['style']
    return original_message


def slack_buttons_handler(app, payload, incidents, queue_, route):
    if payload.get('token') != slack_verification_token:
        logger.error(f'Unauthorized request to \'/app\'')
        return {}, 401

    incident_ = incidents.get_by_ts(ts=payload['message_ts'])
    original_message = payload.get('original_message')
    if incident_ is None:
        return original_message, 200
    actions = payload.get('actions')

    user_id = payload.get('user')['id']

    for action in actions:
        if action['name'] == 'chain':
            if incident_.chain_enabled:
                incident_.assign_user_id(user_id)
                incident_.chain_enabled = False
                queue_.delete_by_id(incident_.uuid, delete_steps=True, delete_status=False)
            else:
                queue_.delete_by_id(incident_.uuid, delete_steps=True, delete_status=False)
                _, chain_name = route.get_route(incident_.last_state)
                chain = app.chains.get(chain_name)
                incident_.recreate_chain(chain)

                incident_.assign_user_id("")
                incident_.chain_enabled = True
                queue_.recreate(incident_.status, incident_.uuid, incident_.chain)
        elif action['name'] == 'status':
            if incident_.status_enabled:
                incident_.status_enabled = False
            else:
                incident_.status_enabled = True

    body = app.body_template.form_message(incident_.last_state, incident_)
    header = app.header_template.form_message(incident_.last_state, incident_)
    status_icons = app.status_icons_template.form_message(incident_.last_state, incident_)
    payload = app.update_thread_payload(incident_.channel_id, incident_.ts, body, header, status_icons,
                                        incident_.status, incident_.chain_enabled, incident_.status_enabled)
    incident_.dump()
    modified_message = reformat_message(original_message, payload['text'], payload['attachments'],
                                        incident_.chain_enabled, incident_.status_enabled)
    return modified_message, 200
