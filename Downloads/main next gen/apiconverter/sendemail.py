import os
import base64
import logging
import httplib2
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from flask import Flask, request, jsonify, redirect, session, url_for, render_template_string
import pickle
from openai import OpenAI
import re

# Define the scopes for Gmail API access
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly', 'https://www.googleapis.com/auth/gmail.send']
CLIENTSECRETS_LOCATION = './apiconverter/credentials.json'

# Initialize Flask app
app = Flask(__name__)
app.secret_key = 'supersecretkey'

# Initialize the OpenAI client
client = OpenAI()  # Ensure OpenAI is properly initialized with your API key

# Function to authenticate and connect to Gmail API
def authenticate_gmail():
    creds = None
    # Load credentials from token.pickle if available
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    
    # If credentials are not available or invalid, authenticate using client_secrets.json
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENTSECRETS_LOCATION, SCOPES)
            creds = flow.run_local_server(port=53730)  # Use fixed port 53730 to match redirect URI in Google Cloud Console
        # Save the credentials for future use
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    # Build the Gmail API service
    service = build('gmail', 'v1', credentials=creds)
    return service

# Function to get the latest email and retrieve sender's email address and body
def get_latest_email():
    service = authenticate_gmail()
    # Get the latest email from the inbox
    results = service.users().messages().list(userId='me', labelIds=['INBOX'], maxResults=1).execute()
    messages = results.get('messages', [])
    
    if not messages:
        print("No emails found.")
        return None, None
    
    # Get the message details
    message = service.users().messages().get(userId='me', id=messages[0]['id']).execute()
    headers = message['payload'].get('headers', [])
    sender_email = None
    for header in headers:
        if header['name'] == 'From':
            sender_email = header['value']
            break
    
    body = ''
    if 'parts' in message['payload']:
        for part in message['payload']['parts']:
            if part['mimeType'] == 'text/plain' and 'data' in part['body']:
                data = part['body']['data']
                body = base64.urlsafe_b64decode(data).decode('utf-8')
                break
    elif 'body' in message['payload'] and 'data' in message['payload']['body']:
        data = message['payload']['body']['data']
        body = base64.urlsafe_b64decode(data).decode('utf-8')
    
    return sender_email, body

# Function to summarize a given text using OpenAI
def summarize_text(conversation_text):
    # Call OpenAI API for summarization
    completion = client.chat.completions.create(
        model="gpt-4o-mini",  # Adjust the model based on your access and preference
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {
                "role": "user",
                "content": f"Summarize this email by giving me 2 bullet points and total 10-15 words only:\n{conversation_text}"
            }
        ]
    )
    summary = completion.choices[0].message.content.strip()
    return summary

# Function to generate a reply to a given email using OpenAI
def generate_reply(conversation_text):
    # Call OpenAI API to generate a reply
    completion = client.chat.completions.create(
        model="gpt-4o-mini",  # Adjust the model based on your access and preference
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {
                "role": "user",
                "content": f"Generate a polite and helpful reply to this email:\n{conversation_text}"
            }
        ]
    )
    reply = completion.choices[0].message.content.strip()
    return reply

# Function to send an email using Gmail API
def send_email(recipient, subject, body):
    service = authenticate_gmail()
    message = f"From: me\nTo: {recipient}\nSubject: {subject}\n\n{body}"
    encoded_message = base64.urlsafe_b64encode(message.encode('utf-8')).decode('utf-8')
    
    create_message = {
        'raw': encoded_message
    }
    try:
        sent_message = service.users().messages().send(userId='me', body=create_message).execute()
        return sent_message
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        return None

# Flask route to display the latest email, summary, and AI-generated reply
@app.route('/')
def index():
    sender_email, email_body = get_latest_email()
    summary = None
    reply = None
    if sender_email and email_body:
        summary = summarize_text(email_body)
        reply = generate_reply(email_body)
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Email Summary and Reply</title>
    </head>
    <body>
        <h1>Email Summary and Reply</h1>
        {% if sender_email and summary and reply %}
            <p><strong>From:</strong> {{ sender_email }}</p>
            <p><strong>Summary:</strong> {{ summary }}</p>
            <p><strong>AI-Generated Reply:</strong> {{ reply }}</p>
            <form action="/send_summary" method="post">
                <input type="hidden" name="sender_email" value="{{ sender_email }}">
                <input type="hidden" name="reply" value="{{ reply }}">
                <button type="submit">Send Reply</button>
            </form>
        {% else %}
            <p>No email found to summarize.</p>
        {% endif %}
    </body>
    </html>
    """
    return render_template_string(html_content, sender_email=sender_email, summary=summary, reply=reply)

# Flask route to handle sending email on button click
@app.route('/send_summary', methods=['POST'])
def send_summary():
    sender_email = request.form.get('sender_email')
    reply = request.form.get('reply')
    if sender_email and reply:
        subject = "Re: Your Email"
        body = reply
        result = send_email(sender_email, subject, body)
        if result:
            return jsonify({'message': 'Email sent successfully!'}), 200
        else:
            return jsonify({'message': 'Failed to send email.'}), 500
    return jsonify({'message': 'Invalid data.'}), 400

if __name__ == '__main__':
    app.run(debug=True)
