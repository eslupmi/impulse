import asyncio
import datetime
import json
from typing import Dict, List, Any
from zoneinfo import ZoneInfo

import jwt
import requests
from requests.adapters import HTTPAdapter
from urllib3 import Retry

from app.config.validation import CloudChain, ScheduleEntry, ScheduleMatcherExpression, SimpleChainStep
from app.im.chain.schedule_chain import ScheduleChain
from app.logging import logger
from app.tools import HTMLTextExtractor
from app.config.config import get_config


class GoogleCalendarChain(ScheduleChain):
    _UTC_OFFSET = '+00:00'
    _Z_TIMEZONE = 'Z'

    def __init__(self, name, config: CloudChain):
        super().__init__(name)
        
        # Get environment configuration
        self._app_config = get_config()

        self.calendar_id = config.calendar_id
        if not self.calendar_id:
            raise ValueError("calendar_id is required in config")

        self.default_steps = config.default_steps
        self._load_credentials()

        # Create a task for syncing
        self._sync_task = None
        self._last_sync_time = None
        self._last_token = None
        self._token_expiry = None

        # Setup retry strategy for requests
        self._setup_session()

        # Fetch initial data
        self._fetch_initial_data()

    def _setup_session(self) -> None:
        """Setup the requests session with retry strategy."""
        retry_strategy = Retry(
            total=3,  # number of retries
            backoff_factor=1,  # wait 1, 2, 4 seconds between retries
            status_forcelist=[429, 500, 502, 503, 504]  # HTTP status codes to retry on
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session = requests.Session()
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def _make_api_request(self, method: str, url: str, **kwargs) -> Dict[str, Any]:
        """Make an API request with proper error handling."""
        try:
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Calendar API request failed: {str(e)}", extra={'extra_fields': {'provider': 'google'}})
            if hasattr(e.response, 'text'):
                logger.error(f"Response text: {e.response.text}", extra={'extra_fields': {'provider': 'google'}})
            raise

    def _update_timezone(self, new_timezone: str) -> None:
        """Update the chain's timezone if it has changed."""
        if new_timezone != self.timezone:
            logger.info(f"Updating timezone from {self.timezone} to {new_timezone}", extra={'extra_fields': {'provider': 'google'}})
            self.timezone = new_timezone
            self.tz = ZoneInfo(new_timezone)

    def _fetch_initial_data(self) -> None:
        """Fetch initial calendar data synchronously."""
        try:
            # First sync the timezone
            calendar_timezone = self._get_calendar_timezone()
            self._update_timezone(calendar_timezone)

            # Then sync events
            events = self._fetch_events()
            self._update_schedule(events)
            logger.info(f"Initial sync: {len(events)} events", extra={'extra_fields': {'provider': 'google'}})
        except Exception as e:
            logger.error(f"Error during initial calendar sync: {str(e)}", extra={'extra_fields': {'provider': 'google'}})
            # Initialize with empty schedule if sync fails
            self.schedule = []

    def _update_schedule(self, events: List[Dict[str, Any]]) -> None:
        """Update the schedule with new events."""
        matchers = [self._convert_event_to_matcher(event) for event in events]

        # Add default steps as a separate entry if they exist
        if self.default_steps:
            matchers.append(ScheduleEntry(matcher=None, steps=self.default_steps))

        self.schedule = matchers
        self._last_sync_time = datetime.datetime.now(datetime.timezone.utc)

    def start_sync(self) -> None:
        """Start the sync task in the background."""
        if self._sync_task is None:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    self._sync_task = asyncio.create_task(self._sync_calendar())
                    logger.info(f"Started calendar sync task", extra={'extra_fields': {'provider': 'google'}})
                else:
                    logger.warning(f"Event loop not running, cannot start calendar sync task", extra={'extra_fields': {'provider': 'google'}})
            except RuntimeError:
                logger.error(f"Failed to start calendar sync task, no event loop", extra={'extra_fields': {'provider': 'google'}})

    def stop_sync(self) -> None:
        """Stop the sync task."""
        if self._sync_task is not None:
            self._sync_task.cancel()
            self._sync_task = None
            logger.info(f"Stopped calendar sync task", extra={'extra_fields': {'provider': 'google'}})

    def cleanup(self) -> None:
        """Cleanup resources when shutting down."""
        self.stop_sync()
        self.session.close()

    def _load_credentials(self) -> None:
        """Load service account credentials from JSON file."""
        try:
            with open(self._app_config.provider_service_account_file, 'r') as f:
                self.credentials = json.load(f)
            # Validate required fields
            required_fields = ['client_email', 'private_key', 'token_uri']
            for field in required_fields:
                if field not in self.credentials:
                    raise ValueError(f"Missing required field '{field}' in service account file")
        except FileNotFoundError:
            raise ValueError(f"Service account file {self._app_config.provider_service_account_file} not found")
        except json.JSONDecodeError:
            raise ValueError(f"Invalid JSON in service account file {self._app_config.provider_service_account_file}")

    def _get_access_token(self) -> str:
        """Get access token using JWT with retry logic."""
        try:
            # Check if we have a valid cached token
            if self._last_token and self._token_expiry:
                now = datetime.datetime.now(datetime.timezone.utc)
                if now < self._token_expiry:
                    return self._last_token

            # Get current time in UTC
            now = datetime.datetime.now(datetime.timezone.utc)
            iat = int(now.timestamp())
            exp = iat + 3600  # Token expires in 1 hour

            # Prepare the JWT claims
            claims = {
                'iss': self.credentials['client_email'],
                'scope': 'https://www.googleapis.com/auth/calendar.readonly',
                'aud': self.credentials['token_uri'],
                'iat': iat,
                'exp': exp
            }

            # Generate the signed JWT
            signed_jwt = jwt.encode(
                claims,
                self.credentials['private_key'],
                algorithm='RS256',
                headers={'alg': 'RS256', 'typ': 'JWT'}
            )

            # Request the access token with proper headers
            response = self.session.post(
                self.credentials['token_uri'],
                data={
                    'grant_type': 'urn:ietf:params:oauth:grant-type:jwt-bearer',
                    'assertion': signed_jwt
                },
                headers={
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'Accept': 'application/json'
                }
            )

            response.raise_for_status()
            token_data = response.json()

            # Cache the token
            self._last_token = token_data['access_token']
            self._token_expiry = now + datetime.timedelta(
                seconds=token_data.get('expires_in', 3600) - 300)  # 5 min buffer

            return self._last_token

        except jwt.InvalidTokenError as e:
            logger.error(f"JWT token generation failed: {str(e)}", extra={'extra_fields': {'provider': 'google'}})
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Token request failed: {str(e)}", extra={'extra_fields': {'provider': 'google'}})
            if hasattr(e.response, 'text'):
                logger.error(f"Response text: {e.response.text}", extra={'extra_fields': {'provider': 'google'}})
            raise
        except KeyError as e:
            logger.error(f"Missing key in response: {str(e)}", extra={'extra_fields': {'provider': 'google'}})
            raise

    def _get_calendar_timezone(self) -> str:
        """Fetch calendar's timezone with retry logic."""
        try:
            token = self._get_access_token()
            headers = {'Authorization': f'Bearer {token}'}
            url = f'https://www.googleapis.com/calendar/v3/calendars/{self.calendar_id}'

            data = self._make_api_request('GET', url, headers=headers)
            return data.get('timeZone', 'UTC')
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get calendar timezone: {str(e)}", extra={'extra_fields': {'provider': 'google'}})
            return 'UTC'  # Fallback to UTC

    def _fetch_events(self) -> List[Dict[str, Any]]:
        """Fetch events from Google Calendar with retry logic."""
        try:
            token = self._get_access_token()

            date_from = datetime.datetime.now(datetime.timezone.utc)
            date_to = date_from + datetime.timedelta(days=self._app_config.provider_days_to_sync)

            params = {
                'timeMin': date_from.isoformat().replace(self._UTC_OFFSET, self._Z_TIMEZONE),
                'timeMax': date_to.isoformat().replace(self._UTC_OFFSET, self._Z_TIMEZONE),
                'maxResults': self._app_config.provider_max_events,
                'singleEvents': 'true',
                'orderBy': 'startTime'
            }

            headers = {
                'Authorization': f'Bearer {token}'
            }

            url = f'https://www.googleapis.com/calendar/v3/calendars/{self.calendar_id}/events'
            data = self._make_api_request('GET', url, headers=headers, params=params)
            return data.get('items', [])
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch calendar events: {str(e)}", extra={'extra_fields': {'provider': 'google'}})
            return []

    @staticmethod
    def _parse_steps_from_description(description: str) -> List[Dict[str, str]]:
        """Parse steps from event description."""
        if not description:
            return []

        parser = HTMLTextExtractor()
        try:
            parser.feed(description)
            description = parser.get_text()
        except (ValueError, TypeError) as e:
            logger.warning(f"Failed to parse description due to invalid input: {str(e)}", extra={'extra_fields': {'provider': 'google'}})
        except MemoryError as e:
            logger.error(f"Memory error while parsing description (content too large): {str(e)}", extra={'extra_fields': {'provider': 'google'}})
        except Exception as e:
            logger.warning(f"Unexpected error while parsing description: {str(e)}", extra={'extra_fields': {'provider': 'google'}})

        steps = []
        for line in description.strip().split('\n'):
            line = line.strip()
            if line.startswith('-'):
                parts = line[1:].strip().split(':')
                if len(parts) == 2:
                    key = parts[0].strip()
                    value = parts[1].strip()
                    steps.append({key: value})
        return steps

    def _convert_event_to_matcher(self, event: Dict[str, Any]) -> ScheduleEntry:
        """Convert Google Calendar event to matcher format."""
        start_time = event['start'].get('dateTime', event['start'].get('date'))
        end_time = event['end'].get('dateTime', event['end'].get('date'))

        # Convert to datetime objects in calendar's timezone
        start_dt = datetime.datetime.fromisoformat(start_time.replace(self._Z_TIMEZONE, self._UTC_OFFSET))
        end_dt = datetime.datetime.fromisoformat(end_time.replace(self._Z_TIMEZONE, self._UTC_OFFSET))

        # Calculate duration
        duration = end_dt - start_dt
        duration_str = f"{int(duration.total_seconds() / 60)}m"

        steps_dicts = self._parse_steps_from_description(event.get('description', ''))
        steps = [SimpleChainStep(**step_dict) for step_dict in steps_dicts]

        # Create matcher expression
        matcher = ScheduleMatcherExpression(
            start_day_expr='date',
            start_day_values=[start_dt.strftime('%Y-%m-%d')],
            start_time=start_dt.strftime('%H:%M'),
            duration=duration_str
        )

        return ScheduleEntry(matcher=matcher, steps=steps)

    async def _sync_calendar(self) -> None:
        """Periodically sync calendar events with error recovery."""
        while True:
            try:
                calendar_timezone = self._get_calendar_timezone()
                self._update_timezone(calendar_timezone)

                events = self._fetch_events()
                self._update_schedule(events)
                logger.debug(f"Synced {len(events)} events", extra={'extra_fields': {'provider': 'google'}})

            except Exception as e:
                logger.error(f"Error syncing сalendar: {str(e)}", extra={'extra_fields': {'provider': 'google'}})
                await asyncio.sleep(min(self._app_config.provider_sync_interval * 2, 300))  # Max 5 minutes
                continue

            await asyncio.sleep(self._app_config.provider_sync_interval)
