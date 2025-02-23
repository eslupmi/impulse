import json
from abc import ABC, abstractmethod
from time import sleep

import requests
from requests.adapters import HTTPAdapter
from urllib3 import Retry

from app.im.chain_factory import ChainFactory
from app.im.groups import generate_user_groups
from app.im.template import JinjaTemplate, notification_user, notification_user_group, update_status
from app.logging import logger


class Application(ABC):

    def __init__(self, app_config, channels, default_channel):
        self.http = self._setup_http()
        self.type = app_config['type']
        self.url = self.get_url(app_config)
        self.public_url = self._get_public_url(app_config)
        self.team = self.get_team_name(app_config)
        self.chains = ChainFactory.generate(app_config.get('chains', dict()))
        self.templates = app_config.get('template_files', dict())
        self.body_template, self.header_template, self.status_icons_template = self.generate_template()

        # Application-specific parameters
        self.post_message_url = None
        self.headers = None
        self.post_delay = None
        self.thread_id_key = None
        self._initialize_specific_params()

        self.channels = channels
        self.default_channel_id = self.channels[default_channel]['id']
        self.users = self._generate_users(app_config['users'])
        self.user_groups = generate_user_groups(app_config.get('user_groups'), self.users)
        self.admin_users = [self.users[admin] for admin in app_config['admin_users']]

    def get_url(self, app_config):
        return self._get_url(app_config)

    def get_team_name(self, app_config):
        return self._get_team_name(app_config)

    def _generate_users(self, users_dict):
        logger.info(f'Creating users')

        users = dict()
        for name, user_info in users_dict.items():
            if user_info.get('id') is not None:
                user_details = self.get_user_details(user_info)
                if not user_details['exists']:
                    logger.warning(f'.. user {name} not found in {self.type.capitalize()} and will not be notified')
            else:
                logger.warning(f'.. user {name} has no \'id\' and will not be notified')
                user_details = {}
            users[name] = self.create_user(name, user_details)
        logger.info(f'.. done')

        return users

    def generate_template(self):
        def read_template(file_key, default_path):
            file_path = self.templates.get(file_key, default_path)
            return JinjaTemplate(open(file_path).read())

        body_template = read_template('body', f'./templates/{self.type}_body.j2')
        header_template = read_template('header', f'./templates/{self.type}_header.j2')
        status_icons_template = read_template('status_icons', f'./templates/{self.type}_status_icons.j2')

        return body_template, header_template, status_icons_template

    def notify(self, incident, notify_type, identifier):
        destinations = self.get_notification_destinations()
        if notify_type == 'user':
            unit = self.users.get(identifier)
            text_template = JinjaTemplate(notification_user)
        else:
            unit = self.user_groups.get(identifier)
            text_template = JinjaTemplate(notification_user_group)
        fields = {'type': self.type, 'name': identifier, 'unit': unit, 'admins': destinations}
        text = text_template.form_notification(fields)
        header = self.format_text_italic(self.header_template.form_message(incident.last_state, incident))
        if self.type == 'telegram':
            message = text
        else:
            message = header + '\n' + text
        response_code = self.post_thread(incident.channel_id, incident.ts, message)
        logger.info(f'Incident {incident.uuid} -> chain step {notify_type} \'{identifier}\'')
        return response_code

    def update(self, uuid_, incident, incident_status, alert_state, updated_status, chain_enabled, status_enabled):
        body = self.body_template.form_message(alert_state, incident)
        header = self.header_template.form_message(alert_state, incident)
        status_icons = self.status_icons_template.form_message(alert_state, incident)
        self.update_thread(
            incident.channel_id, incident.ts, incident_status, body, header, status_icons, chain_enabled, status_enabled
        )
        if updated_status:
            logger.info(f'Incident {uuid_} updated with new status \'{incident_status}\'')
            # post to thread
            if status_enabled and incident_status != 'closed':
                header = self.format_text_italic(self.header_template.form_message(incident.last_state, incident))

                text_template = JinjaTemplate(update_status)
                admins = self.get_notification_destinations()
                fields = {'type': self.type, 'status': incident_status, 'admins': admins}
                text = text_template.form_notification(fields)

                if self.type == 'telegram':
                    message = text
                else:
                    message = header + '\n' + text
                self.post_thread(incident.channel_id, incident.ts, message)

    def new_version_notification(self, channel_id, new_tag):
        r = requests.get(f'https://api.github.com/repos/eslupmi/impulse/releases/tags/{new_tag}')
        release_notes = r.json().get('body')
        new_version_text = self.format_text_bold(f'New IMPulse version available: {new_tag}')
        changelog_link_text = self._format_text_link("CHANGELOG.md",
                                                     "https://github.com/eslupmi/impulse/blob/main/CHANGELOG.md")
        text = f"{new_version_text} {changelog_link_text}\n\n{release_notes}"
        native_formatted_text = self._markdown_links_to_native_format(text)
        admins_text = self.get_admins_text()
        self.send_message(channel_id, native_formatted_text, admins_text)

    def create_thread(self, channel_id, body, header, status_icons, status):
        payload = self._create_thread_payload(channel_id, body, header, status_icons, status)
        return self._send_create_thread(payload)

    def _send_create_thread(self, payload):
        response = requests.post(self.post_message_url, headers=self.headers, data=json.dumps(payload))
        sleep(self.post_delay)
        response_json = response.json()
        return response_json.get(self.thread_id_key)

    def update_thread(self, channel_id, id_, status, body, header, status_icons, chain_enabled=True,
                      status_enabled=True):
        payload = self.update_thread_payload(channel_id, id_, body, header, status_icons, status, chain_enabled,
                                             status_enabled)
        self._update_thread(id_, payload)

    def post_thread(self, channel_id, id_, text):
        payload = self._post_thread_payload(channel_id, id_, text)
        response = requests.post(self.post_message_url, headers=self.headers, data=json.dumps(payload))
        sleep(self.post_delay)
        return response.status_code

    @staticmethod
    def _setup_http():
        retry_strategy = Retry(
            total=3,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
            backoff_factor=2
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        http = requests.Session()
        http.mount("https://", adapter)
        return http

    @abstractmethod
    def buttons_handler(self, payload, incidents, queue_, route):
        pass

    @abstractmethod
    def _initialize_specific_params(self):
        pass

    @abstractmethod
    def _markdown_links_to_native_format(self, text):
        pass

    @abstractmethod
    def _get_url(self, app_config):
        pass

    @abstractmethod
    def _get_public_url(self, app_config):
        """Get the public URL of the application to share with users."""
        pass

    @abstractmethod
    def _get_team_name(self, app_config):
        pass

    @abstractmethod
    def get_notification_destinations(self):
        pass

    @abstractmethod
    def format_text_bold(self, text):
        pass

    @abstractmethod
    def _format_text_link(self, text, url):
        pass

    @abstractmethod
    def format_text_italic(self, text):
        pass

    @abstractmethod
    def get_admins_text(self):
        pass

    @abstractmethod
    def send_message(self, channel_id, text, attachment):
        pass

    @abstractmethod
    def _create_thread_payload(self, channel_id, body, header, status_icons, status):
        pass

    @abstractmethod
    def _post_thread_payload(self, channel_id, id_, text):
        pass

    @abstractmethod
    def update_thread_payload(self, channel_id, id_, body, header, status_icons, status, chain_enabled, status_enabled):
        pass

    @abstractmethod
    def _update_thread(self, id_, payload):
        pass

    @abstractmethod
    def get_user_details(self, user_details):
        """Fetch user-specific details (ID, name, etc.) from the system. Must be implemented by subclasses."""
        pass

    @abstractmethod
    def create_user(self, name, user_details):
        """Create a user object specific to the application (Slack/Mattermost)."""
        pass
