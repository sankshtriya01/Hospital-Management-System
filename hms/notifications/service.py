"""
Thin client that calls the local serverless-offline email endpoint.

The Django app never sends email directly. It posts a JSON payload to the
serverless function, which owns all SMTP logic. This keeps the Django app
decoupled from the email transport layer.
"""
import json
import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

# Timeout for the HTTP call to the serverless function (seconds)
_TIMEOUT = 5


def trigger_email(event_type: str, payload: dict) -> bool:
    """
    POST to the serverless email function.

    Args:
        event_type: One of 'SIGNUP_WELCOME' | 'BOOKING_CONFIRMATION'
        payload:    Dict of template variables (email, name, etc.)

    Returns:
        True if the function accepted the request, False on any error.
    """
    url = settings.EMAIL_SERVICE_URL
    body = {'event_type': event_type, **payload}

    try:
        resp = requests.post(url, json=body, timeout=_TIMEOUT)
        resp.raise_for_status()
        logger.info('Email triggered: %s → %s (HTTP %s)', event_type, payload.get('email', '?'), resp.status_code)
        return True
    except requests.exceptions.ConnectionError:
        logger.warning(
            'Serverless email service is not reachable at %s. '
            'Start it with: cd email-service && npx serverless offline', url
        )
        return False
    except requests.exceptions.Timeout:
        logger.warning('Email service timed out for event %s', event_type)
        return False
    except requests.exceptions.HTTPError as exc:
        logger.error('Email service returned error for %s: %s', event_type, exc)
        return False
    except Exception as exc:
        logger.error('Unexpected error calling email service: %s', exc)
        return False
