"""from flask import Flask, redirect, url_for, session, request
import os
import google.oauth2.credentials
import google_auth_oauthlib.flow
import googleapiclient.discovery

app = Flask(__name__)
app.secret_key = 'YOUR_SECRET_KEY'

# OAuth 2.0 client IDs and secrets are pre-configured by the developer.
CLIENT_SECRETS_FILE =  "./userLogin/client_secret.json"

SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly'
]
API_SERVICE_NAME = 'gmail'
API_VERSION = 'v1'

@app.route('/')
def index():
    return 'Welcome! <a href="/authorize">Sign in with Gmail</a>'

@app.route('/authorize')
def authorize():
    # Create the flow using the client secrets file
    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE, scopes=SCOPES)

    # Redirect URI for the authorization flow
    flow.redirect_uri = url_for('oauth2callback', _external=True)

    # Generate authorization URL
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true'
    )

    # Store state in session to verify later
    session['state'] = state

    return redirect(authorization_url)

@app.route('/oauth2callback')
def oauth2callback():
    # Validate state
    state = session['state']

    # Create flow using client secret and redirect_uri
    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE, scopes=SCOPES, state=state)
    flow.redirect_uri = url_for('oauth2callback', _external=True)

    # Exchange authorization code for credentials
    authorization_response = request.url
    flow.fetch_token(authorization_response=authorization_response)

    # Store credentials in the session
    credentials = flow.credentials
    session['credentials'] = credentials_to_dict(credentials)

    return redirect(url_for('get_latest_email'))

@app.route('/get_latest_email')

def get_latest_email():
    # Check if credentials are available
    if 'credentials' not in session:
        return redirect('authorize')

    # Load credentials
    credentials = google.oauth2.credentials.Credentials(**session['credentials'])

    # Connect to Gmail API
    service = googleapiclient.discovery.build(
        API_SERVICE_NAME, API_VERSION, credentials=credentials)

    # Get the latest email in user's inbox
    results = service.users().messages().list(userId='me', maxResults=1).execute()
    messages = results.get('messages', [])

    if not messages:
        return 'No new emails found.'
    else:
        # Get the full message using the message ID
        message = service.users().messages().get(userId='me', id=messages[0]['id']).execute()

        # Extract the necessary information from the message
        headers = message['payload']['headers']
        subject = next(header['value'] for header in headers if header['name'] == 'Subject')
        sender = next(header['value'] for header in headers if header['name'] == 'From')
        
        # The email body can be found in 'payload' for both plain text and HTML versions
        body = ''
        if 'parts' in message['payload']:
            for part in message['payload']['parts']:
                if part['mimeType'] == 'text/plain':
                    body = part['body']['data']
                    break
        else:
            body = message['payload']['body']['data']
        
        # Decode the base64url-encoded email body
        import base64
        body = base64.urlsafe_b64decode(body).decode('utf-8')

        # Display the full email content
        return f'<h2>Subject: {subject}</h2>' \
               f'<h3>From: {sender}</h3>' \
               f'<pre>{body}</pre>'

# Helper function to convert credentials to dictionary
def credentials_to_dict(credentials):
    return {'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes}

if __name__ == '__main__':
    # Run Flask app with SSL certificates
    app.run('localhost', 53730, debug=True, ssl_context=('cert.pem', 'key.pem'))

    """


from flask import Flask, redirect, url_for, session, request, jsonify
import os
import google.oauth2.credentials
import google_auth_oauthlib.flow
import googleapiclient.discovery
import base64
import re
from openai import OpenAI

# Flask app initialization
app = Flask(__name__)
app.secret_key = 'YOUR_SECRET_KEY'

# OAuth and Gmail API setup
CLIENT_SECRETS_FILE = './userLogin/client_secret.json'
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
API_SERVICE_NAME = 'gmail'
API_VERSION = 'v1'

# Initialize the OpenAI client
client = OpenAI()  # Ensure OpenAI is properly initialized with your API key

@app.route('/')
def index():
    return '''
    <!doctype html>
    <html lang="en">
      <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">
        <title>Gmail Integration</title>
        <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css">
      </head>
      <body>
        <div class="container mt-5">
          <h1>Welcome!</h1>
          <a href="/authorize" class="btn btn-primary">Sign in with Gmail</a>
        </div>
      </body>
    </html>
    '''

@app.route('/authorize')
def authorize():
    # Create the flow using the client secrets file
    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE, scopes=SCOPES)

    # Redirect URI for the authorization flow
    flow.redirect_uri = url_for('oauth2callback', _external=True)

    # Generate authorization URL
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true'
    )

    # Store state in session to verify later
    session['state'] = state

    return redirect(authorization_url)

@app.route('/oauth2callback')
def oauth2callback():
    # Validate state
    state = session['state']

    # Create flow using client secret and redirect_uri
    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE, scopes=SCOPES, state=state)
    flow.redirect_uri = url_for('oauth2callback', _external=True)

    # Exchange authorization code for credentials
    authorization_response = request.url
    flow.fetch_token(authorization_response=authorization_response)

    # Store credentials in the session
    credentials = flow.credentials
    session['credentials'] = credentials_to_dict(credentials)

    return redirect(url_for('get_latest_emails'))

@app.route('/get_latest_emails')
def get_latest_emails():
    # Check if credentials are available
    if 'credentials' not in session:
        return redirect(url_for('authorize'))

    # Load credentials
    credentials = google.oauth2.credentials.Credentials(**session['credentials'])

    # Connect to Gmail API
    service = googleapiclient.discovery.build(
        API_SERVICE_NAME, API_VERSION, credentials=credentials)

    # Get the latest emails in user's inbox
    results = service.users().messages().list(userId='me', maxResults=3).execute()
    messages = results.get('messages', [])

    emails = []
    for msg in messages:
        msg_id = msg['id']
        message = service.users().messages().get(userId='me', id=msg_id).execute()

        # Extract message payload and decode it
        payload = message['payload']
        headers = payload.get('headers', [])
        subject = next((header['value'] for header in headers if header['name'] == 'Subject'), '')
        sender = next((header['value'] for header in headers if header['name'] == 'From'), '')

        # Decode the email body
        body = extract_email_body(payload)

        emails.append({'sender': sender, 'subject': subject, 'body': body, 'id': msg_id})
    
    # Summarize emails
    for email in emails:
        email['summary'] = summarize_text(email['body'])

    # Generate the HTML content dynamically
    email_cards = ""
    for email in emails:
        email_cards += f"""
          <div class="card mb-3">
            <div class="card-body">
              <h5 class="card-title">From: {email['sender']}</h5>
              <h6 class="card-subtitle mb-2 text-muted">Subject: {email['subject']}</h6>
              <p class="card-text">Summary: {email['summary']}</p>
            </div>
          </div>
        """

    html_content = f"""
    <!doctype html>
    <html lang="en">
      <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">
        <title>Latest Emails</title>
        <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css">
      </head>
      <body>
        <div class="container mt-5">
          <h1>Latest Emails</h1>
          {email_cards}
        </div>
      </body>
    </html>
    """

    return html_content

# Helper function to extract the email body from payload
def extract_email_body(payload):
    body = ''
    if 'parts' in payload:
        for part in payload['parts']:
            if part['mimeType'] == 'text/plain' and 'data' in part['body']:
                data = part['body']['data']
                body = base64.urlsafe_b64decode(data).decode('utf-8')
                break
    elif 'body' in payload and 'data' in payload['body']:
        data = payload['body']['data']
        body = base64.urlsafe_b64decode(data).decode('utf-8')
    return body

# Helper function to summarize a given text using OpenAI
def summarize_text(conversation_text):
    # Call OpenAI API for summarization
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": f"Summarize this email by giving me 2 bullet points and total 10-15 words only:\n{conversation_text}"}
        ]
    )
    summary = completion.choices[0].message.content.strip()
    return summary

# Helper function to convert credentials to dictionary
def credentials_to_dict(credentials):
    return {'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes}

if __name__ == '__main__':
    # Run Flask app with SSL certificates
    app.run('localhost', 53730, debug=True, ssl_context=('cert.pem', 'key.pem'))
