import os
import json
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from config import settings

SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

def get_client_config() -> dict:
    """Load client configuration from credentials.json or env settings."""
    if os.path.exists(settings.CREDENTIALS_FILE_PATH):
        with open(settings.CREDENTIALS_FILE_PATH, 'r') as f:
            return json.load(f)
    elif settings.GMAIL_CLIENT_ID and settings.GMAIL_CLIENT_SECRET:
        return {
            "web": {
                "client_id": settings.GMAIL_CLIENT_ID,
                "client_secret": settings.GMAIL_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [settings.GMAIL_REDIRECT_URI]
            }
        }
    else:
        raise ValueError("No OAuth client credentials found. Provide credentials.json or GMAIL_CLIENT_ID & GMAIL_CLIENT_SECRET in .env.")

def create_oauth_flow(state: str = None) -> Flow:
    client_config = get_client_config()
    flow = Flow.from_client_config(
        client_config=client_config,
        scopes=SCOPES,
        state=state
    )
    flow.redirect_uri = settings.GMAIL_REDIRECT_URI
    return flow

def get_authorization_url(state: str = None) -> tuple[str, str]:
    flow = create_oauth_flow(state=state)
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent'
    )
    return authorization_url, state

def exchange_code_for_token(code: str, state: str = None) -> Credentials:
    flow = create_oauth_flow(state=state)
    flow.fetch_token(code=code)
    creds = flow.credentials
    save_credentials(creds)
    return creds

def save_credentials(creds: Credentials):
    with open(settings.TOKEN_FILE_PATH, 'w') as token_file:
        token_file.write(creds.to_json())

def get_saved_credentials() -> Credentials | None:
    if os.path.exists(settings.TOKEN_FILE_PATH):
        creds = Credentials.from_authorized_user_file(settings.TOKEN_FILE_PATH, SCOPES)
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                save_credentials(creds)
            except Exception as e:
                print(f"Error refreshing token: {e}")
                return None
        return creds
    return None

def is_authenticated() -> bool:
    creds = get_saved_credentials()
    return creds is not None and creds.valid
