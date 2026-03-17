from flask import Flask, request, redirect
import requests
import os
import gspread
import json
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)

CLIENT_ID = "169738"
CLIENT_SECRET = os.getenv("STRAVA_SECRET")
REDIRECT_URI = "https://fitbet-strava-auth-1.onrender.com/callback"

# Google Sheets setup
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SHEET_ID = os.getenv("SHEET_ID")

# Bubble endpoint
BUBBLE_STRAVA_UPSERT_URL = os.getenv("BUBBLE_STRAVA_UPSERT_URL")


@app.route('/')
def home():
    return """
        <h2>FitBet Strava Auth</h2>
        <p>Use /connect?platform=iphone</p>
        <p>Or /connect?platform=android&uid=YOUR_BUBBLE_USER_ID</p>
    """


@app.route('/connect')
def connect():
    platform = request.args.get('platform', '').strip().lower()
    uid = request.args.get('uid', '').strip()

    if platform not in ['android', 'iphone']:
        return "Missing or invalid platform. Use platform=android or platform=iphone.", 400

    if platform == 'android' and not uid:
        return "Missing uid for android flow.", 400

    state = f"{platform}|{uid}"

    auth_url = (
        f"https://www.strava.com/oauth/authorize?"
        f"client_id={CLIENT_ID}&response_type=code&"
        f"redirect_uri={REDIRECT_URI}&"
        f"scope=read,activity:read_all,profile:read_all&"
        f"approval_prompt=auto&"
        f"state={state}"
    )

    return redirect(auth_url)


@app.route('/callback')
def callback():
    code = request.args.get('code')
    state = request.args.get('state', '')

    if not code:
        return "No code returned from Strava.", 400

    parts = state.split('|')
    platform = parts[0] if len(parts) > 0 else ''
    uid = parts[1] if len(parts) > 1 else ''

    # Exchange code for tokens
    token_response = requests.post(
        "https://www.strava.com/oauth/token",
        data={
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET,
            'code': code,
            'grant_type': 'authorization_code'
        }
    )

    if token_response.status_code != 200:
        return f"Strava token exchange failed: {token_response.text}", 500

    token_data = token_response.json()

    access_token = token_data.get("access_token", "")
    refresh_token = token_data.get("refresh_token", "")
    expires_at = token_data.get("expires_at", 0)

    athlete = token_data.get("athlete", {})
    firstname = athlete.get("firstname", "")
    lastname = athlete.get("lastname", "")
    name = f"{firstname} {lastname}".strip() or "unknown"
    strava_id = athlete.get("id", 0)

    if platform == "android":
        if not BUBBLE_STRAVA_UPSERT_URL:
            return "Missing BUBBLE_STRAVA_UPSERT_URL env var.", 500

        if not uid:
            return "Missing Bubble uid in state.", 400

        bubble_response = requests.post(
            BUBBLE_STRAVA_UPSERT_URL,
            json={
                "uid": uid,
                "name": name,
                "firstname": firstname,
                "lastname": lastname,
                "access_token": access_token,
                "refresh_token": refresh_token,
                "strava_id": strava_id,
                "expires_at": expires_at
            },
            timeout=20
        )

        if bubble_response.status_code >= 400:
            return f"Bubble update failed: {bubble_response.text}", 500

        return f"""
            <h2>Thanks for connecting, {name}!</h2>
            <p>Your Strava account has been linked to FitBet.</p>
            <p>You can now return to the app.</p>
        """

    elif platform == "iphone":
        key_json = os.getenv("GOOGLE_SHEETS_CRED_JSON")
        if not key_json:
            return "Missing GOOGLE_SHEETS_CRED_JSON env var.", 500

        info = json.loads(key_json)
        credentials = Credentials.from_service_account_info(info, scopes=SCOPES)

        client = gspread.authorize(credentials)
        sheet = client.open_by_key(SHEET_ID).sheet1
        sheet.append_row([name, strava_id, access_token, refresh_token])

        return f"""
            <h2>Thanks for connecting, {name}!</h2>
            <p>You can now compete in FitBet challenges.</p>
        """

    else:
        return f"Unknown platform in state: {platform}", 400


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)