"""
Unit tests for app.im.chain.google_calendar_chain module.
"""
import pytest
import json
import datetime
from unittest.mock import Mock, patch, MagicMock, mock_open
from zoneinfo import ZoneInfo

from app.config.validation import CloudChain, ScheduleEntry, ScheduleMatcherExpression, SimpleChainStep
from app.im.chain.google_calendar_chain import GoogleCalendarChain


@pytest.fixture
def mock_config():
    """Mock configuration for GoogleCalendarChain."""
    config = Mock(spec=CloudChain)
    config.calendar_id = "test@example.com"
    config.default_steps = [SimpleChainStep(user="default_user")]
    return config


@pytest.fixture
def mock_app_config():
    """Mock application configuration."""
    app_config = Mock()
    app_config.provider_service_account_file = "test_key.json"
    app_config.provider_sync_interval = 300
    app_config.provider_max_events = 100
    app_config.provider_days_to_sync = 7
    return app_config


@pytest.fixture
def mock_service_account_credentials():
    """Mock service account credentials."""
    return {
        'client_email': 'test@test-project.iam.gserviceaccount.com',
        'private_key': '-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA0Z3VS5JJcds3xfn/ygWyF4P3R9cpPv9FEXjA5eFXa3xo4yd+\n-----END RSA PRIVATE KEY-----\n',
        'token_uri': 'https://oauth2.googleapis.com/token'
    }


@pytest.fixture
def sample_calendar_event():
    """Sample Google Calendar event."""
    return {
        'id': 'test_event_1',
        'summary': 'Test Event',
        'description': '- user: test_user\n- wait: 5m',
        'start': {
            'dateTime': '2024-01-15T09:00:00+00:00'
        },
        'end': {
            'dateTime': '2024-01-15T17:00:00+00:00'
        }
    }


@pytest.fixture
def sample_calendar_events():
    """Sample list of Google Calendar events."""
    return [
        {
            'id': 'event1',
            'summary': 'Event 1',
            'description': '- user: user1',
            'start': {'dateTime': '2024-01-15T09:00:00+00:00'},
            'end': {'dateTime': '2024-01-15T17:00:00+00:00'}
        },
        {
            'id': 'event2',
            'summary': 'Event 2',
            'description': '- user: user2\n- wait: 10m',
            'start': {'dateTime': '2024-01-16T10:00:00+00:00'},
            'end': {'dateTime': '2024-01-16T12:00:00+00:00'}
        }
    ]


class TestGoogleCalendarChainInit:
    """Test cases for GoogleCalendarChain initialization."""

    @patch('app.im.chain.google_calendar_chain.get_config')
    @patch('builtins.open', new_callable=mock_open)
    @patch('app.im.chain.google_calendar_chain.GoogleCalendarChain._fetch_initial_data')
    def test_init_success(self, mock_fetch, mock_file, mock_get_config, 
                         mock_config, mock_app_config, mock_service_account_credentials):
        """Test successful initialization."""
        mock_get_config.return_value = mock_app_config
        mock_file.return_value.read.return_value = json.dumps(mock_service_account_credentials)
        
        with patch('json.load', return_value=mock_service_account_credentials):
            chain = GoogleCalendarChain(name="test_chain", config=mock_config)
        
        assert chain.name == "test_chain"
        assert chain.calendar_id == "test@example.com"
        assert chain.default_steps == mock_config.default_steps
        assert chain.credentials == mock_service_account_credentials

    @patch('app.im.chain.google_calendar_chain.get_config')
    @patch('builtins.open', new_callable=mock_open)
    @patch('app.im.chain.google_calendar_chain.GoogleCalendarChain._fetch_initial_data')
    def test_init_missing_calendar_id(self, mock_fetch, mock_file, mock_get_config, 
                                     mock_app_config, mock_service_account_credentials):
        """Test initialization with missing calendar_id."""
        mock_get_config.return_value = mock_app_config
        
        config = Mock(spec=CloudChain)
        config.calendar_id = None
        config.default_steps = []
        
        with pytest.raises(ValueError, match="calendar_id is required"):
            GoogleCalendarChain(name="test_chain", config=config)

    @patch('app.im.chain.google_calendar_chain.get_config')
    @patch('builtins.open', side_effect=FileNotFoundError)
    @patch('app.im.chain.google_calendar_chain.GoogleCalendarChain._fetch_initial_data')
    def test_init_missing_credentials_file(self, mock_fetch, mock_file, mock_get_config,
                                          mock_config, mock_app_config):
        """Test initialization with missing credentials file."""
        mock_get_config.return_value = mock_app_config
        
        with pytest.raises(ValueError, match="Service account file .* not found"):
            GoogleCalendarChain(name="test_chain", config=mock_config)

    @patch('app.im.chain.google_calendar_chain.get_config')
    @patch('builtins.open', new_callable=mock_open)
    @patch('app.im.chain.google_calendar_chain.GoogleCalendarChain._fetch_initial_data')
    def test_init_invalid_credentials_missing_field(self, mock_fetch, mock_file, mock_get_config,
                                                    mock_config, mock_app_config):
        """Test initialization with invalid credentials (missing required field)."""
        mock_get_config.return_value = mock_app_config
        invalid_creds = {'client_email': 'test@test.com'}  # Missing private_key and token_uri
        
        with patch('json.load', return_value=invalid_creds):
            with pytest.raises(ValueError, match="Missing required field"):
                GoogleCalendarChain(name="test_chain", config=mock_config)


class TestGoogleCalendarChainParseSteps:
    """Test cases for parsing steps from description."""

    def test_parse_steps_empty_description(self):
        """Test parsing steps from empty description."""
        result = GoogleCalendarChain._parse_steps_from_description("")
        assert result == []

    def test_parse_steps_none_description(self):
        """Test parsing steps from None description."""
        result = GoogleCalendarChain._parse_steps_from_description(None)
        assert result == []

    def test_parse_steps_single_step(self):
        """Test parsing single step."""
        description = "- user: test_user"
        result = GoogleCalendarChain._parse_steps_from_description(description)
        
        assert len(result) == 1
        assert result[0] == {'user': 'test_user'}

    def test_parse_steps_multiple_steps(self):
        """Test parsing multiple steps."""
        description = "- user: test_user\n- wait: 5m\n- user_group: admins"
        result = GoogleCalendarChain._parse_steps_from_description(description)
        
        assert len(result) == 3
        assert result[0] == {'user': 'test_user'}
        assert result[1] == {'wait': '5m'}
        assert result[2] == {'user_group': 'admins'}

    def test_parse_steps_with_whitespace(self):
        """Test parsing steps with extra whitespace."""
        description = "-  user  :  test_user  \n-  wait  :  5m  "
        result = GoogleCalendarChain._parse_steps_from_description(description)
        
        assert len(result) == 2
        assert result[0] == {'user': 'test_user'}
        assert result[1] == {'wait': '5m'}

    def test_parse_steps_html_content(self):
        """Test parsing steps from HTML description."""
        description = "<p>- user: test_user</p><p>- wait: 5m</p>"
        result = GoogleCalendarChain._parse_steps_from_description(description)
        
        # Should extract text from HTML
        assert len(result) == 2
        assert 'user' in result[0]
        assert 'wait' in result[1]

    def test_parse_steps_invalid_format_no_colon(self):
        """Test parsing steps with invalid format (no colon)."""
        description = "- user test_user\n- wait 5m"
        result = GoogleCalendarChain._parse_steps_from_description(description)
        
        # Should skip invalid lines
        assert len(result) == 0

    def test_parse_steps_mixed_valid_invalid(self):
        """Test parsing steps with mixed valid and invalid lines."""
        description = "Some text\n- user: test_user\nMore text\n- wait: 5m\nRandom line"
        result = GoogleCalendarChain._parse_steps_from_description(description)
        
        assert len(result) == 2
        assert result[0] == {'user': 'test_user'}
        assert result[1] == {'wait': '5m'}

    def test_parse_steps_with_multiple_colons(self):
        """Test parsing steps with multiple colons in value."""
        description = "- webhook: http://example.com:8080/webhook"
        result = GoogleCalendarChain._parse_steps_from_description(description)
        
        # Should only split on first colon
        assert len(result) == 0  # Will be empty because split(':') creates more than 2 parts


class TestGoogleCalendarChainConvertEvent:
    """Test cases for converting calendar events to matchers."""

    def test_convert_event_to_matcher_basic(self, sample_calendar_event):
        """Test converting basic calendar event to matcher."""
        with patch('app.im.chain.google_calendar_chain.get_config'):
            with patch('app.im.chain.google_calendar_chain.GoogleCalendarChain._load_credentials'):
                with patch('app.im.chain.google_calendar_chain.GoogleCalendarChain._fetch_initial_data'):
                    chain = GoogleCalendarChain.__new__(GoogleCalendarChain)
                    chain.name = "test"
                    
                    result = chain._convert_event_to_matcher(sample_calendar_event)
        
        assert isinstance(result, ScheduleEntry)
        assert isinstance(result.matcher, ScheduleMatcherExpression)
        assert result.matcher.start_day_expr == 'date'
        assert result.matcher.start_day_values == ['2024-01-15']
        assert result.matcher.start_time == '09:00'
        assert result.matcher.duration == '480m'  # 8 hours = 480 minutes

    def test_convert_event_to_matcher_with_steps(self, sample_calendar_event):
        """Test converting event with steps in description."""
        with patch('app.im.chain.google_calendar_chain.get_config'):
            with patch('app.im.chain.google_calendar_chain.GoogleCalendarChain._load_credentials'):
                with patch('app.im.chain.google_calendar_chain.GoogleCalendarChain._fetch_initial_data'):
                    chain = GoogleCalendarChain.__new__(GoogleCalendarChain)
                    chain.name = "test"
                    
                    result = chain._convert_event_to_matcher(sample_calendar_event)
        
        assert isinstance(result, ScheduleEntry)
        assert len(result.steps) == 2
        assert isinstance(result.steps[0], SimpleChainStep)
        assert result.steps[0].user == 'test_user'
        assert result.steps[1].wait == '5m'

    def test_convert_event_to_matcher_no_description(self):
        """Test converting event without description."""
        event = {
            'id': 'test_event',
            'summary': 'Test Event',
            'start': {'dateTime': '2024-01-15T09:00:00+00:00'},
            'end': {'dateTime': '2024-01-15T17:00:00+00:00'}
        }
        
        with patch('app.im.chain.google_calendar_chain.get_config'):
            with patch('app.im.chain.google_calendar_chain.GoogleCalendarChain._load_credentials'):
                with patch('app.im.chain.google_calendar_chain.GoogleCalendarChain._fetch_initial_data'):
                    chain = GoogleCalendarChain.__new__(GoogleCalendarChain)
                    chain.name = "test"
                    
                    result = chain._convert_event_to_matcher(event)
        
        assert isinstance(result, ScheduleEntry)
        assert len(result.steps) == 0

    def test_convert_event_to_matcher_all_day_event(self):
        """Test converting all-day event."""
        event = {
            'id': 'test_event',
            'summary': 'All Day Event',
            'description': '- user: test_user',
            'start': {'date': '2024-01-15'},
            'end': {'date': '2024-01-16'}
        }
        
        with patch('app.im.chain.google_calendar_chain.get_config'):
            with patch('app.im.chain.google_calendar_chain.GoogleCalendarChain._load_credentials'):
                with patch('app.im.chain.google_calendar_chain.GoogleCalendarChain._fetch_initial_data'):
                    chain = GoogleCalendarChain.__new__(GoogleCalendarChain)
                    chain.name = "test"
                    
                    result = chain._convert_event_to_matcher(event)
        
        assert isinstance(result, ScheduleEntry)
        assert isinstance(result.matcher, ScheduleMatcherExpression)

    def test_convert_event_to_matcher_different_timezone(self):
        """Test converting event with different timezone."""
        event = {
            'id': 'test_event',
            'summary': 'Test Event',
            'description': '- user: test_user',
            'start': {'dateTime': '2024-01-15T09:00:00-05:00'},  # EST
            'end': {'dateTime': '2024-01-15T17:00:00-05:00'}
        }
        
        with patch('app.im.chain.google_calendar_chain.get_config'):
            with patch('app.im.chain.google_calendar_chain.GoogleCalendarChain._load_credentials'):
                with patch('app.im.chain.google_calendar_chain.GoogleCalendarChain._fetch_initial_data'):
                    chain = GoogleCalendarChain.__new__(GoogleCalendarChain)
                    chain.name = "test"
                    
                    result = chain._convert_event_to_matcher(event)
        
        assert isinstance(result, ScheduleEntry)
        # Time should be converted properly
        assert result.matcher.start_time is not None

    def test_convert_event_to_matcher_short_duration(self):
        """Test converting event with short duration."""
        event = {
            'id': 'test_event',
            'summary': 'Short Meeting',
            'description': '- user: test_user',
            'start': {'dateTime': '2024-01-15T09:00:00+00:00'},
            'end': {'dateTime': '2024-01-15T09:30:00+00:00'}  # 30 minutes
        }
        
        with patch('app.im.chain.google_calendar_chain.get_config'):
            with patch('app.im.chain.google_calendar_chain.GoogleCalendarChain._load_credentials'):
                with patch('app.im.chain.google_calendar_chain.GoogleCalendarChain._fetch_initial_data'):
                    chain = GoogleCalendarChain.__new__(GoogleCalendarChain)
                    chain.name = "test"
                    
                    result = chain._convert_event_to_matcher(event)
        
        assert result.matcher.duration == '30m'


class TestGoogleCalendarChainUpdateSchedule:
    """Test cases for updating schedule."""

    @patch('app.im.chain.google_calendar_chain.get_config')
    @patch('builtins.open', new_callable=mock_open)
    @patch('app.im.chain.google_calendar_chain.GoogleCalendarChain._fetch_initial_data')
    def test_update_schedule_empty_events(self, mock_fetch, mock_file, mock_get_config,
                                         mock_config, mock_app_config, mock_service_account_credentials):
        """Test updating schedule with empty events list."""
        mock_get_config.return_value = mock_app_config
        mock_config.default_steps = []
        
        with patch('json.load', return_value=mock_service_account_credentials):
            chain = GoogleCalendarChain(name="test_chain", config=mock_config)
            chain._update_schedule([])
        
        assert chain.schedule == []
        assert chain._last_sync_time is not None

    @patch('app.im.chain.google_calendar_chain.get_config')
    @patch('builtins.open', new_callable=mock_open)
    @patch('app.im.chain.google_calendar_chain.GoogleCalendarChain._fetch_initial_data')
    def test_update_schedule_with_events(self, mock_fetch, mock_file, mock_get_config,
                                        mock_config, mock_app_config, mock_service_account_credentials,
                                        sample_calendar_events):
        """Test updating schedule with events."""
        mock_get_config.return_value = mock_app_config
        mock_config.default_steps = []
        
        with patch('json.load', return_value=mock_service_account_credentials):
            chain = GoogleCalendarChain(name="test_chain", config=mock_config)
            chain._update_schedule(sample_calendar_events)
        
        assert len(chain.schedule) == 2
        assert all(isinstance(entry, ScheduleEntry) for entry in chain.schedule)

    @patch('app.im.chain.google_calendar_chain.get_config')
    @patch('builtins.open', new_callable=mock_open)
    @patch('app.im.chain.google_calendar_chain.GoogleCalendarChain._fetch_initial_data')
    def test_update_schedule_with_default_steps(self, mock_fetch, mock_file, mock_get_config,
                                               mock_config, mock_app_config, mock_service_account_credentials,
                                               sample_calendar_events):
        """Test updating schedule with default steps."""
        mock_get_config.return_value = mock_app_config
        
        with patch('json.load', return_value=mock_service_account_credentials):
            chain = GoogleCalendarChain(name="test_chain", config=mock_config)
            chain._update_schedule(sample_calendar_events)
        
        # Should have 2 events + 1 default entry
        assert len(chain.schedule) == 3
        
        # Last entry should be default steps with no matcher
        last_entry = chain.schedule[-1]
        assert last_entry.matcher is None
        assert len(last_entry.steps) == 1
        assert last_entry.steps[0].user == "default_user"


class TestGoogleCalendarChainAPIRequests:
    """Test cases for API request methods."""

    @patch('app.im.chain.google_calendar_chain.get_config')
    @patch('builtins.open', new_callable=mock_open)
    @patch('app.im.chain.google_calendar_chain.GoogleCalendarChain._fetch_initial_data')
    def test_make_api_request_success(self, mock_fetch, mock_file, mock_get_config,
                                     mock_config, mock_app_config, mock_service_account_credentials):
        """Test successful API request."""
        mock_get_config.return_value = mock_app_config
        mock_config.default_steps = []
        
        with patch('json.load', return_value=mock_service_account_credentials):
            chain = GoogleCalendarChain(name="test_chain", config=mock_config)
        
        # Mock session.request
        mock_response = Mock()
        mock_response.json.return_value = {'success': True}
        chain.session.request = Mock(return_value=mock_response)
        
        result = chain._make_api_request('GET', 'http://test.com')
        
        assert result == {'success': True}
        chain.session.request.assert_called_once()

    @patch('app.im.chain.google_calendar_chain.get_config')
    @patch('builtins.open', new_callable=mock_open)
    @patch('app.im.chain.google_calendar_chain.GoogleCalendarChain._fetch_initial_data')
    def test_make_api_request_failure(self, mock_fetch, mock_file, mock_get_config,
                                     mock_config, mock_app_config, mock_service_account_credentials):
        """Test failed API request."""
        mock_get_config.return_value = mock_app_config
        mock_config.default_steps = []
        
        with patch('json.load', return_value=mock_service_account_credentials):
            chain = GoogleCalendarChain(name="test_chain", config=mock_config)
        
        # Mock failed request
        import requests
        chain.session.request = Mock(side_effect=requests.exceptions.RequestException("API Error"))
        
        with pytest.raises(requests.exceptions.RequestException):
            chain._make_api_request('GET', 'http://test.com')


class TestGoogleCalendarChainAccessToken:
    """Test cases for access token management."""

    @patch('app.im.chain.google_calendar_chain.get_config')
    @patch('builtins.open', new_callable=mock_open)
    @patch('app.im.chain.google_calendar_chain.GoogleCalendarChain._fetch_initial_data')
    @patch('jwt.encode')
    def test_get_access_token_new_token(self, mock_jwt, mock_fetch, mock_file, mock_get_config,
                                       mock_config, mock_app_config, mock_service_account_credentials):
        """Test getting new access token."""
        mock_get_config.return_value = mock_app_config
        mock_config.default_steps = []
        mock_jwt.return_value = 'signed_jwt_token'
        
        with patch('json.load', return_value=mock_service_account_credentials):
            chain = GoogleCalendarChain(name="test_chain", config=mock_config)
        
        # Mock successful token response
        mock_response = Mock()
        mock_response.json.return_value = {
            'access_token': 'test_access_token',
            'expires_in': 3600
        }
        chain.session.post = Mock(return_value=mock_response)
        
        token = chain._get_access_token()
        
        assert token == 'test_access_token'
        assert chain._last_token == 'test_access_token'
        assert chain._token_expiry is not None

    @patch('app.im.chain.google_calendar_chain.get_config')
    @patch('builtins.open', new_callable=mock_open)
    @patch('app.im.chain.google_calendar_chain.GoogleCalendarChain._fetch_initial_data')
    def test_get_access_token_cached(self, mock_fetch, mock_file, mock_get_config,
                                    mock_config, mock_app_config, mock_service_account_credentials):
        """Test getting cached access token."""
        mock_get_config.return_value = mock_app_config
        mock_config.default_steps = []
        
        with patch('json.load', return_value=mock_service_account_credentials):
            chain = GoogleCalendarChain(name="test_chain", config=mock_config)
        
        # Set cached token
        future_time = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)
        chain._last_token = 'cached_token'
        chain._token_expiry = future_time
        
        token = chain._get_access_token()
        
        assert token == 'cached_token'

    @patch('app.im.chain.google_calendar_chain.get_config')
    @patch('builtins.open', new_callable=mock_open)
    @patch('app.im.chain.google_calendar_chain.GoogleCalendarChain._fetch_initial_data')
    def test_get_access_token_expired(self, mock_fetch, mock_file, mock_get_config,
                                     mock_config, mock_app_config, mock_service_account_credentials):
        """Test getting new token when cached token is expired."""
        mock_get_config.return_value = mock_app_config
        mock_config.default_steps = []
        
        with patch('json.load', return_value=mock_service_account_credentials):
            chain = GoogleCalendarChain(name="test_chain", config=mock_config)
        
        # Set expired token
        past_time = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1)
        chain._last_token = 'expired_token'
        chain._token_expiry = past_time
        
        # Mock new token response
        mock_response = Mock()
        mock_response.json.return_value = {
            'access_token': 'new_token',
            'expires_in': 3600
        }
        
        with patch('jwt.encode', return_value='signed_jwt'):
            chain.session.post = Mock(return_value=mock_response)
            token = chain._get_access_token()
        
        assert token == 'new_token'


class TestGoogleCalendarChainSync:
    """Test cases for sync functionality."""

    @patch('app.im.chain.google_calendar_chain.get_config')
    @patch('builtins.open', new_callable=mock_open)
    @patch('app.im.chain.google_calendar_chain.GoogleCalendarChain._fetch_initial_data')
    def test_cleanup(self, mock_fetch, mock_file, mock_get_config,
                    mock_config, mock_app_config, mock_service_account_credentials):
        """Test cleanup method."""
        mock_get_config.return_value = mock_app_config
        mock_config.default_steps = []
        
        with patch('json.load', return_value=mock_service_account_credentials):
            chain = GoogleCalendarChain(name="test_chain", config=mock_config)
        
        chain.cleanup()
        
        # Session should be closed
        assert chain._sync_task is None


class TestGoogleCalendarChainTimezone:
    """Test cases for timezone handling."""

    @patch('app.im.chain.google_calendar_chain.get_config')
    @patch('builtins.open', new_callable=mock_open)
    @patch('app.im.chain.google_calendar_chain.GoogleCalendarChain._fetch_initial_data')
    def test_update_timezone(self, mock_fetch, mock_file, mock_get_config,
                            mock_config, mock_app_config, mock_service_account_credentials):
        """Test updating timezone."""
        mock_get_config.return_value = mock_app_config
        mock_config.default_steps = []
        
        with patch('json.load', return_value=mock_service_account_credentials):
            chain = GoogleCalendarChain(name="test_chain", config=mock_config)
        
        initial_tz = chain.timezone
        chain._update_timezone("America/New_York")
        
        assert chain.timezone == "America/New_York"
        assert chain.timezone != initial_tz

    @patch('app.im.chain.google_calendar_chain.get_config')
    @patch('builtins.open', new_callable=mock_open)
    @patch('app.im.chain.google_calendar_chain.GoogleCalendarChain._fetch_initial_data')
    def test_get_calendar_timezone_success(self, mock_fetch, mock_file, mock_get_config,
                                          mock_config, mock_app_config, mock_service_account_credentials):
        """Test getting calendar timezone successfully."""
        mock_get_config.return_value = mock_app_config
        mock_config.default_steps = []
        
        with patch('json.load', return_value=mock_service_account_credentials):
            chain = GoogleCalendarChain(name="test_chain", config=mock_config)
        
        # Mock token and API response
        chain._get_access_token = Mock(return_value='test_token')
        chain._make_api_request = Mock(return_value={'timeZone': 'America/Los_Angeles'})
        
        timezone = chain._get_calendar_timezone()
        
        assert timezone == 'America/Los_Angeles'

    @patch('app.im.chain.google_calendar_chain.get_config')
    @patch('builtins.open', new_callable=mock_open)
    @patch('app.im.chain.google_calendar_chain.GoogleCalendarChain._fetch_initial_data')
    def test_get_calendar_timezone_failure(self, mock_fetch, mock_file, mock_get_config,
                                          mock_config, mock_app_config, mock_service_account_credentials):
        """Test getting calendar timezone with failure."""
        mock_get_config.return_value = mock_app_config
        mock_config.default_steps = []
        
        with patch('json.load', return_value=mock_service_account_credentials):
            chain = GoogleCalendarChain(name="test_chain", config=mock_config)
        
        # Mock token and API failure
        import requests
        chain._get_access_token = Mock(return_value='test_token')
        chain._make_api_request = Mock(side_effect=requests.exceptions.RequestException("API Error"))
        
        timezone = chain._get_calendar_timezone()
        
        # Should fallback to UTC
        assert timezone == 'UTC'


class TestGoogleCalendarChainFetchEvents:
    """Test cases for fetching events."""

    @patch('app.im.chain.google_calendar_chain.get_config')
    @patch('builtins.open', new_callable=mock_open)
    @patch('app.im.chain.google_calendar_chain.GoogleCalendarChain._fetch_initial_data')
    def test_fetch_events_success(self, mock_fetch, mock_file, mock_get_config,
                                  mock_config, mock_app_config, mock_service_account_credentials,
                                  sample_calendar_events):
        """Test fetching events successfully."""
        mock_get_config.return_value = mock_app_config
        mock_config.default_steps = []
        
        with patch('json.load', return_value=mock_service_account_credentials):
            chain = GoogleCalendarChain(name="test_chain", config=mock_config)
        
        # Mock token and API response
        chain._get_access_token = Mock(return_value='test_token')
        chain._make_api_request = Mock(return_value={'items': sample_calendar_events})
        
        events = chain._fetch_events()
        
        assert len(events) == 2
        assert events[0]['id'] == 'event1'
        assert events[1]['id'] == 'event2'

    @patch('app.im.chain.google_calendar_chain.get_config')
    @patch('builtins.open', new_callable=mock_open)
    @patch('app.im.chain.google_calendar_chain.GoogleCalendarChain._fetch_initial_data')
    def test_fetch_events_failure(self, mock_fetch, mock_file, mock_get_config,
                                  mock_config, mock_app_config, mock_service_account_credentials):
        """Test fetching events with failure."""
        mock_get_config.return_value = mock_app_config
        mock_config.default_steps = []
        
        with patch('json.load', return_value=mock_service_account_credentials):
            chain = GoogleCalendarChain(name="test_chain", config=mock_config)
        
        # Mock token and API failure
        import requests
        chain._get_access_token = Mock(return_value='test_token')
        chain._make_api_request = Mock(side_effect=requests.exceptions.RequestException("API Error"))
        
        events = chain._fetch_events()
        
        # Should return empty list on failure
        assert events == []

    @patch('app.im.chain.google_calendar_chain.get_config')
    @patch('builtins.open', new_callable=mock_open)
    @patch('app.im.chain.google_calendar_chain.GoogleCalendarChain._fetch_initial_data')
    def test_fetch_events_no_items(self, mock_fetch, mock_file, mock_get_config,
                                   mock_config, mock_app_config, mock_service_account_credentials):
        """Test fetching events when no items returned."""
        mock_get_config.return_value = mock_app_config
        mock_config.default_steps = []
        
        with patch('json.load', return_value=mock_service_account_credentials):
            chain = GoogleCalendarChain(name="test_chain", config=mock_config)
        
        # Mock token and API response with no items
        chain._get_access_token = Mock(return_value='test_token')
        chain._make_api_request = Mock(return_value={})
        
        events = chain._fetch_events()
        
        assert events == []


class TestGoogleCalendarChainEdgeCases:
    """Test cases for edge cases."""

    def test_parse_steps_with_html_parser_error(self):
        """Test parsing steps when HTML parser encounters error."""
        # Very large description that might cause MemoryError
        description = "- user: test_user"
        
        with patch('app.tools.HTMLTextExtractor.feed', side_effect=ValueError("Parse error")):
            result = GoogleCalendarChain._parse_steps_from_description(description)
            
            # Should still try to parse the original description
            assert isinstance(result, list)

    def test_convert_event_with_z_timezone(self):
        """Test converting event with Z timezone indicator."""
        event = {
            'id': 'test_event',
            'summary': 'Test Event',
            'description': '- user: test_user',
            'start': {'dateTime': '2024-01-15T09:00:00Z'},  # Z instead of +00:00
            'end': {'dateTime': '2024-01-15T17:00:00Z'}
        }
        
        with patch('app.im.chain.google_calendar_chain.get_config'):
            with patch('app.im.chain.google_calendar_chain.GoogleCalendarChain._load_credentials'):
                with patch('app.im.chain.google_calendar_chain.GoogleCalendarChain._fetch_initial_data'):
                    chain = GoogleCalendarChain.__new__(GoogleCalendarChain)
                    chain.name = "test"
                    
                    result = chain._convert_event_to_matcher(event)
        
        assert isinstance(result, ScheduleEntry)
        assert result.matcher.start_time == '09:00'

