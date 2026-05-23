import json
import logging
from datetime import datetime, timezone

import requests
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.errors import HttpError

from notifications.service import trigger_email

from .forms import DoctorSignupForm, LoginForm, PatientSignupForm

logger = logging.getLogger(__name__)

GOOGLE_SCOPES = [
    'https://www.googleapis.com/auth/calendar.events',
    'openid',
    'https://www.googleapis.com/auth/userinfo.email',
]


def signup_choose(request):
    return render(request, 'accounts/signup_choose.html')


@require_http_methods(["GET", "POST"])
def doctor_signup(request):
    if request.method == 'POST':
        form = DoctorSignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            # Fire welcome email via serverless function
            trigger_email('SIGNUP_WELCOME', {
                'email': user.email,
                'name': user.get_full_name() or user.username,
                'role': 'Doctor',
            })
            messages.success(request, f'Welcome, Dr. {user.get_full_name()}! Your account is ready.')
            return redirect('dashboard')
    else:
        form = DoctorSignupForm()
    return render(request, 'accounts/signup.html', {'form': form, 'role': 'Doctor'})


@require_http_methods(["GET", "POST"])
def patient_signup(request):
    if request.method == 'POST':
        form = PatientSignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            trigger_email('SIGNUP_WELCOME', {
                'email': user.email,
                'name': user.get_full_name() or user.username,
                'role': 'Patient',
            })
            messages.success(request, f'Welcome, {user.get_full_name()}! Your account is ready.')
            return redirect('dashboard')
    else:
        form = PatientSignupForm()
    return render(request, 'accounts/signup.html', {'form': form, 'role': 'Patient'})


@require_http_methods(["GET", "POST"])
def user_login(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            login(request, form.get_user())
            return redirect(request.GET.get('next', 'dashboard'))
        messages.error(request, 'Invalid username or password.')
    else:
        form = LoginForm()
    return render(request, 'accounts/login.html', {'form': form})


@login_required
def user_logout(request):
    logout(request)
    return redirect('login')


# ─── Google OAuth2 ────────────────────────────────────────────────────────────

def _build_flow():
    return Flow.from_client_config(
        {
            "web": {
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uris": [settings.GOOGLE_REDIRECT_URI],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=GOOGLE_SCOPES,
        redirect_uri=settings.GOOGLE_REDIRECT_URI,
    )


@login_required
def google_authorize(request):
    if not settings.GOOGLE_CLIENT_ID:
        messages.warning(request, 'Google Calendar integration is not configured.')
        return redirect('dashboard')

    flow = _build_flow()
    auth_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent',
    )
    request.session['google_oauth_state'] = state
    return redirect(auth_url)


@login_required
def google_oauth_callback(request):
    if not settings.GOOGLE_CLIENT_ID:
        return redirect('dashboard')

    state = request.session.get('google_oauth_state')
    flow = _build_flow()
    flow.fetch_token(authorization_response=request.build_absolute_uri())

    creds = flow.credentials
    user = request.user
    user.google_access_token = creds.token
    user.google_refresh_token = creds.refresh_token or user.google_refresh_token
    if creds.expiry:
        user.google_token_expiry = creds.expiry.replace(tzinfo=timezone.utc)
    user.save(update_fields=['google_access_token', 'google_refresh_token', 'google_token_expiry'])

    messages.success(request, 'Google Calendar connected successfully!')
    return redirect('dashboard')
