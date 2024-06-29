import os
from datetime import datetime, timedelta

from app.incident import Incident, Incidents
from app.logger import logger
from app.queue import unix_sleep_to_timedelta, Queue
from app.slack import update_thread, create_thread, button_handler, admin_message, post_thread
from app.slack.user import env, admins_template_string
from app.update.check import get_latest_tag
from config import incidents_path, slack_verification_token, timeouts


def queue_handle(incidents, queue_, application, webhooks, latest_tag):
    if len(queue_.dates) == 0:
        return
    type_, uuid_, identifier = queue_.handle()
    if type_ is not None:
        if type_ == 'update_status':
            queue_handle_status_update(incidents, uuid_, queue_, application)
        elif type_ == 'chain_step':
            queue_handle_step(incidents, uuid_, application, identifier, webhooks)
        elif type_ == 'check_update':
            queue_handle_check_update(identifier, queue_, application, latest_tag)


def queue_handle_check_update(identifier, queue_, application, latest_tag):
    current_tag = get_latest_tag()
    if identifier == 'first':
        latest_tag['version'] = current_tag
    else:
        if current_tag != latest_tag['version']:
            application.new_version_notification(application.default_channel_id, current_tag)
            latest_tag['version'] = current_tag
    queue_.put(datetime.utcnow() + timedelta(days=1), 'check_update', None, identifier=None)


def queue_handle_step(incidents, uuid_, application, identifier, webhooks):
    incident_ = incidents.by_uuid[uuid_]
    step = incident_.chain[identifier]
    if step['type'] == 'webhook':
        webhook_name = step['identifier']
        webhook = webhooks.get(webhook_name)
        admins_ids = [a.slack_id for a in application.admin_users]
        text = f'notify webhook *{webhook_name}*'
        if webhook:
            r_code = webhook.push()
            incident_.chain_update(uuid_, identifier, done=True, result=r_code)
            if r_code > 300:
                admins_text = env.from_string(admins_template_string).render(users=admins_ids)
                text += (f'\n>_response code: {r_code}_'
                         f'\n>_{admins_text}_')
                _ = post_thread(incident_.channel_id, incident_.ts, text)
                logger.warning(f'Webhook \'{webhook_name}\' response code is {r_code}')
                incident_.chain_update(uuid_, identifier, done=True, result=None)
        else:
            admins_text = env.from_string(admins_template_string).render(users=admins_ids)
            text += (f'\n>_not found in `impulse.yml`_'
                     f'\n>_{admins_text}_')
            _ = post_thread(incident_.channel_id, incident_.ts, text)
            logger.warning(f'Webhook \'{webhook_name}\' not found in impulse.yml')
            incident_.chain_update(uuid_, identifier, done=True, result=None)
    else:
        r_code = application.notify(incident_, step['type'], step['identifier'])
        incident_.chain_update(uuid_, identifier, done=True, result=r_code)


def queue_handle_status_update(incidents, uuid, queue_, application):
    incident_ = incidents.by_uuid[uuid]
    updated = incident_.set_next_status()
    application.update(
        uuid, incident_, incident_.status, incident_.last_state, updated,
        incident_.chain_enabled, incident_.status_enabled
    )
    if incident_.status == 'closed':
        incidents.del_by_uuid(uuid)
        queue_.delete_by_id(uuid)
    elif incident_.status == 'unknown':
        queue_.update(uuid, incident_.status_update_datetime, incident_.status)


def alert_handle_create(application, route, incidents, queue_, alert_state):
    channel, chain_name = route.get_route(alert_state)

    channel = application.channels[channel]
    template = application.message_template
    message = template.form_message(alert_state)
    ts = create_thread(channel_id=channel['id'], message=message, status=alert_state['status'])
    status = alert_state['status']

    updated_datetime = datetime.utcnow()
    status_update_datetime = datetime.utcnow() + unix_sleep_to_timedelta(timeouts.get(status))
    chain = application.chains.get(chain_name)
    incident_ = Incident(
        alert=alert_state, status=status, ts=ts, channel_id=channel['id'], chain=[], chain_enabled=True,
        status_enabled=True, updated=updated_datetime, status_update_datetime=status_update_datetime
    )
    uuid_ = incidents.add(incident_)

    logger.info(f'Incident \'{uuid_}\' created. Link: {incident_.link}')
    [logger.info(f'  {i}: {alert_state["groupLabels"][i]}') for i in alert_state['groupLabels'].keys()]

    queue_.put(status_update_datetime, 'update_status', uuid_)

    incident_.generate_chain(chain)
    queue_.append(uuid_, incident_.chain)
    incident_.dump(f'{incidents_path}/{uuid_}.yml')


def alert_handle_update(uuid_, incident_, queue_, alert_state, application):
    # update incident
    is_state_updated, is_status_updated = incident_.update(alert_state, uuid_)

    # update slack
    if is_state_updated:
        application.update(
            uuid_, incident_, alert_state['status'], alert_state, is_status_updated,
            incident_.chain_enabled, incident_.status_enabled
        )

    # update queue
    queue_.update(uuid_, incident_.status_update_datetime, incident_.status)


def alert_handle(application, route_, incidents, queue_, alert_state):
    incident_, uuid_ = incidents.get(alert=alert_state)
    if incident_ is None:
        alert_handle_create(application, route_, incidents, queue_, alert_state)
    else:
        alert_handle_update(uuid_, incident_, queue_, alert_state, application)


def slack_handler(payload, incidents, queue_):
    if payload.get('token') != slack_verification_token:
        logger.error(f'Unauthorized request to \'/slack\'')
        return {}, 401

    incident_, uuid_ = incidents.get_by_ts(ts=payload['message_ts'])
    original_message = payload.get('original_message')
    actions = payload.get('actions')

    for action in actions:
        if action['name'] == 'chain':
            if incident_.chain_enabled:
                incident_.chain_enabled = False
                queue_.delete_by_id(uuid_, delete_steps=True, delete_status=False)
            else:
                incident_.chain_enabled = True
                queue_.append(uuid_, incident_.chain)
        elif action['name'] == 'status':
            if incident_.status_enabled:
                incident_.status_enabled = False
            else:
                incident_.status_enabled = True
    incident_.dump(f'{incidents_path}/{uuid_}.yml')
    modified_message = button_handler(original_message, incident_.chain_enabled, incident_.status_enabled)
    return modified_message, 200


def recreate_incidents():
    if not os.path.exists(incidents_path):
        logger.debug(f'creating incidents_directory')
        os.makedirs(incidents_path)
        logger.debug(f'created incidents_directory')
    else:
        logger.debug(f'load incidents from disk')

    incidents = Incidents([])
    for path, directories, files in os.walk(incidents_path):
        for filename in files:
            incident_ = Incident.load(f'{incidents_path}/{filename}')
            incidents.add(incident_)
    return incidents


def recreate_queue(incidents, check_update):
    logger.debug(f'Creating Queue')
    queue_ = Queue(check_update)
    if bool(incidents.by_uuid):
        for uuid_, i in incidents.by_uuid.items():
            queue_.append(uuid_, i.get_chain())
            queue_.put(i.status_update_datetime, 'update_status', uuid_)
        logger.debug(f'Queue restored')
    else:
        logger.debug(f'Empty Queue created')
    return queue_