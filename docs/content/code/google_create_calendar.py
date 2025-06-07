import os
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


SERVICE_ACCOUNT_FILE = 'key.json'
USER_EMAIL_TO_SHARE_WITH = 'future_owner@email.com'
NEW_CALENDAR_SUMMARY = 'IMPulse'
NEW_CALENDAR_DESCRIPTION = ''
NEW_CALENDAR_TIMEZONE = 'Asia/Tashkent'


SCOPES = ['https://www.googleapis.com/auth/calendar', 'https://www.googleapis.com/auth/calendar.events']


def authenticate_service_account():
    try:    
        credentials = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=SCOPES
        )
        return credentials
    except FileNotFoundError:
        print(f"Error: Service account key file not found at: {SERVICE_ACCOUNT_FILE}")
        print("Please make sure the path is correct and the file exists.")
        exit(1)
    except Exception as e:
        print(f"Error during service account authentication: {e}")
        exit(1)


def create_calendar(service):
    calendar_body = {
        'summary': NEW_CALENDAR_SUMMARY,
        'description': NEW_CALENDAR_DESCRIPTION,
        'timeZone': NEW_CALENDAR_TIMEZONE
    }

    try:
        print(f"Attempting to create calendar: '{NEW_CALENDAR_SUMMARY}'...")
        created_calendar = service.calendars().insert(body=calendar_body).execute()
        calendar_id = created_calendar['id']
        print(f"Calendar successfully created! ID: {calendar_id}")
        return calendar_id
    except HttpError as error:
        print(f"Error while creating calendar: {error}")
        return None


def share_calendar(service, calendar_id, user_email):
    rule = {
        'scope': {
            'type': 'user',
            'value': user_email,
        },
        # 'owner' - full access, including deleting the calendar
        # 'writer' - can create, edit, and delete events
        # 'reader' - can only view event details
        # 'freeBusyReader' - can only see free/busy information
        'role': 'owner'
    }

    try:
        print(f"Attempting to grant '{user_email}' access to calendar '{calendar_id}' with role 'owner'...")
        created_rule = service.acl().insert(calendarId=calendar_id, body=rule).execute()
        print(f"Access successfully granted! Rule ID: {created_rule['id']}")
    except HttpError as error:
        print(f"Error while sharing the calendar: {error}")


def main():
    credentials = authenticate_service_account()
    service = build('calendar', 'v3', credentials=credentials)
    calendar_id = create_calendar(service)
    if calendar_id:
        share_calendar(service, calendar_id, USER_EMAIL_TO_SHARE_WITH)
    else:
        print("Failed to create calendar. Sharing process aborted.")


if __name__ == '__main__':
    main()
