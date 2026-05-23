"""
Google Calendar integration.

Builds credentials from the tokens stored on the User model and creates
a calendar event for the given slot.
"""
import datetime
import logging

from django.conf import settings
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)


def _get_credentials(user):
    """
    Build and (if necessary) refresh Google OAuth2 credentials for a user.
    Returns None if the user has not connected Google Calendar.
    """
    if not user.google_access_token:
        return None

    creds = Credentials(
        token=user.google_access_token,
        refresh_token=user.google_refresh_token or None,
        token_uri='https://oauth2.googleapis.com/token',
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        scopes=['https://www.googleapis.com/auth/calendar.events'],
    )

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        # Persist refreshed token
        user.google_access_token = creds.token
        if creds.expiry:
            from django.utils import timezone as tz
            user.google_token_expiry = creds.expiry.replace(tzinfo=datetime.timezone.utc)
        user.save(update_fields=['google_access_token', 'google_token_expiry'])

    return creds


def create_calendar_event(user, title, slot):
    """
    Create a Google Calendar event for `user` and return the event ID.
    Raises an exception if anything goes wrong (caller decides how to handle).
    """
    creds = _get_credentials(user)
    if not creds:
        logger.info('User %s has no Google credentials — skipping calendar.', user)
        return ''

    service = build('calendar', 'v3', credentials=creds)

    # Combine date + time → RFC3339 datetime strings
    start_dt = datetime.datetime.combine(slot.date, slot.start_time)
    end_dt = datetime.datetime.combine(slot.date, slot.end_time)

    event_body = {
        'summary': title,
        'description': f'HMS appointment booked via Hospital Management System.',
        'start': {
            'dateTime': start_dt.isoformat(),
            'timeZone': 'UTC',
        },
        'end': {
            'dateTime': end_dt.isoformat(),
            'timeZone': 'UTC',
        },
        'reminders': {
            'useDefault': False,
            'overrides': [
                {'method': 'email', 'minutes': 60},
                {'method': 'popup', 'minutes': 15},
            ],
        },
    }

    created = service.events().insert(calendarId='primary', body=event_body).execute()
    logger.info('Calendar event created for %s: %s', user, created.get('id'))
    return created.get('id', '')
