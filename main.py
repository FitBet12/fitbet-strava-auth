from flask import Flask, request
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
SHEET_NAME = "FitBet Strava Users"  # Must match your Google Sheet name
SHEET_ID = os.getenv("SHEET_ID")  # The part after /d/ in your sheet URL

@app.route('/')
def home():
    auth_url = (
        f"https://www.strava.com/oauth/authorize?"
        f"client_id={CLIENT_ID}&response_type=code&"
        f"redirect_uri={REDIRECT_URI}&scope=activity:read_all&"
        f"approval_prompt=force"
    )
    return f'''
        <h2>Welcome to FitBet!</h2>

        <a href="{auth_url}">
            <img src="https://github.com/strava/developer-website/blob/main/assets/img/connect_with_strava.png?raw=true" 
                 alt="Connect with Strava" 
                 style="height: 48px;" />
        </a>

        <br><br>

        <img src="https://github.com/strava/developer-website/blob/main/assets/img/powered_by_strava_black.png?raw=true" 
             alt="Powered by Strava" 
             style="height: 32px;" />
    '''
@app.route('/callback')
def callback():
    code = request.args.get('code')
    if not code:
        return "No code returned from Strava."

    # Get tokens from Strava
    token_response = requests.post("https://www.strava.com/oauth/token", data={
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'code': code,
        'grant_type': 'authorization_code'
    }).json()

    access_token = token_response["access_token"]
    refresh_token = token_response["refresh_token"]
    athlete = token_response.get("athlete", {})
    name = athlete.get("firstname", "unknown")
    strava_id = athlete.get("id", "unknown")

    # Load Google Sheets credentials from environment
    key_json = os.getenv("GOOGLE_SHEETS_CRED_JSON")
    info = json.loads(key_json)
    credentials = Credentials.from_service_account_info(info, scopes=SCOPES)

    # Connect to Google Sheets
    client = gspread.authorize(credentials)
    sheet = client.open_by_key(SHEET_ID).sheet1

    # Save to spreadsheet
    sheet.append_row([name, strava_id, access_token, refresh_token])

    return f'''
        <h2>Thanks for connecting, {name}!</h2>
        <p>You can now compete in FitBet Challenges!</p>
    '''

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)