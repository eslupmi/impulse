import asyncio
import datetime
import json
from typing import Dict, List, Any
from zoneinfo import ZoneInfo

import jwt
import requests
from requests.adapters import HTTPAdapter
from urllib3 import Retry

from app.im.chain.schedule_chain import ScheduleChain
from app.logging import logger
from config import provider_sync_interval, provider_max_events, provider_days_to_sync, provider_service_account_file


class GoogleCalendarChain(ScheduleChain):
    def __init__(self, name, config: dict):
        super().__init__(name)
        
        self.calendar_id = config.get('calendar_id')
        if not self.calendar_id:
            raise ValueError("calendar_id is required in config")
            
        self.default_steps = config.get('default_steps', [])
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
            logger.error(f"API request failed: {str(e)}")
            if hasattr(e.response, 'text'):
                logger.error(f"Response text: {e.response.text}")
            raise
        
    def _update_timezone(self, new_timezone: str) -> None:
        """Update the chain's timezone if it has changed."""
        if new_timezone != self.timezone:
            logger.info(f"Updating timezone from {self.timezone} to {new_timezone}")
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
            logger.info(f"Initial sync: {len(events)} events from Google Calendar")
        except Exception as e:
            logger.error(f"Error during initial calendar sync: {str(e)}")
            # Initialize with empty schedule if sync fails
            self.schedule = []
            
    def _update_schedule(self, events: List[Dict[str, Any]]) -> None:
        """Update the schedule with new events."""
        matchers = [self._convert_event_to_matcher(event) for event in events]
        self.schedule = matchers
        self._last_sync_time = datetime.datetime.now(datetime.UTC)
            
    def start_sync(self) -> None:
        """Start the sync task in the background."""
        if self._sync_task is None:
            loop = asyncio.get_event_loop()
            self._sync_task = loop.create_task(self._sync_calendar())
            logger.info(f"Started Google Calendar sync task for {self.name}")
            
    def stop_sync(self) -> None:
        """Stop the sync task."""
        if self._sync_task is not None:
            self._sync_task.cancel()
            try:
                # Get the event loop and run until the task is done
                loop = asyncio.get_event_loop()
                loop.run_until_complete(self._sync_task)
            except asyncio.CancelledError:
                # Task was cancelled, this is expected
                pass
            except Exception as e:
                logger.error(f"Error while stopping sync task: {str(e)}")
            finally:
                self._sync_task = None
                logger.info(f"Stopped Google Calendar sync task for {self.name}")
            
    def cleanup(self) -> None:
        """Cleanup resources when shutting down."""
        self.stop_sync()
        self.session.close()
        
    def _load_credentials(self) -> None:
        """Load service account credentials from JSON file."""
        try:
            with open(provider_service_account_file, 'r') as f:
                self.credentials = json.load(f)
            # Validate required fields
            required_fields = ['client_email', 'private_key', 'token_uri']
            for field in required_fields:
                if field not in self.credentials:
                    raise ValueError(f"Missing required field '{field}' in service account file")
        except FileNotFoundError:
            raise ValueError(f"Service account file {provider_service_account_file} not found")
        except json.JSONDecodeError:
            raise ValueError(f"Invalid JSON in service account file {provider_service_account_file}")
            
    def _get_access_token(self) -> str:
        """Get access token using JWT with retry logic."""
        try:
            # Check if we have a valid cached token
            if self._last_token and self._token_expiry:
                now = datetime.datetime.now(datetime.UTC)
                if now < self._token_expiry:
                    return self._last_token
            
            # Get current time in UTC
            now = datetime.datetime.now(datetime.UTC)
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
            self._token_expiry = now + datetime.timedelta(seconds=token_data.get('expires_in', 3600) - 300)  # 5 min buffer
            
            return self._last_token
            
        except jwt.InvalidTokenError as e:
            logger.error(f"JWT token generation failed: {str(e)}")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Token request failed: {str(e)}")
            if hasattr(e.response, 'text'):
                logger.error(f"Response text: {e.response.text}")
            raise
        except KeyError as e:
            logger.error(f"Missing key in response: {str(e)}")
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
            logger.error(f"Failed to get calendar timezone: {str(e)}")
            return 'UTC'  # Fallback to UTC
        
    def _fetch_events(self) -> List[Dict[str, Any]]:
        """Fetch events from Google Calendar with retry logic."""
        try:
            token = self._get_access_token()
            
            date_from = datetime.datetime.utcnow()
            date_to = date_from + datetime.timedelta(days=provider_days_to_sync)
            
            params = {
                'timeMin': date_from.isoformat() + 'Z',
                'timeMax': date_to.isoformat() + 'Z',
                'maxResults': provider_max_events,
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
            logger.error(f"Failed to fetch calendar events: {str(e)}")
            return []
        
    @staticmethod
    def _parse_steps_from_description(description: str) -> List[Dict[str, str]]:
        """Parse steps from event description."""
        if not description:
            return []
            
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
        
    def _convert_event_to_matcher(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Convert Google Calendar event to matcher format."""
        start_time = event['start'].get('dateTime', event['start'].get('date'))
        end_time = event['end'].get('dateTime', event['end'].get('date'))
        
        # Convert to datetime objects in calendar's timezone
        start_dt = datetime.datetime.fromisoformat(start_time.replace('Z', '+00:00'))
        end_dt = datetime.datetime.fromisoformat(end_time.replace('Z', '+00:00'))
        
        # Calculate duration
        duration = end_dt - start_dt
        duration_str = f"{int(duration.total_seconds() / 3600)}h"
        
        # Get steps from description or use default steps
        steps = self._parse_steps_from_description(event.get('description', ''))
        if not steps and self.default_steps:
            steps = self.default_steps
            logger.debug(f"Using default steps for event {event.get('summary', 'No summary')}")
        
        return {
            'matcher': {
                'start_day_expr': 'date',
                'start_day_values': [start_dt.strftime('%Y-%m-%d')],
                'start_time': start_dt.strftime('%H:%M'),
                'duration': duration_str
            },
            'steps': steps
        }
        
    async def _sync_calendar(self) -> None:
        """Periodically sync calendar events with error recovery."""
        while True:
            try:
                # First sync the timezone
                calendar_timezone = self._get_calendar_timezone()
                self._update_timezone(calendar_timezone)
                
                # Then sync events
                events = self._fetch_events()
                self._update_schedule(events)
                logger.info(f"Synced {len(events)} events from Google Calendar")
                
            except Exception as e:
                logger.error(f"Error syncing Google Calendar: {str(e)}")
                # Add exponential backoff for errors
                await asyncio.sleep(min(provider_sync_interval * 2, 300))  # Max 5 minutes
                continue
                
            await asyncio.sleep(provider_sync_interval)

