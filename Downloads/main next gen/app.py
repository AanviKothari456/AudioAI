
# prioritises, generates reply and sends, summarises and reads aloud. 
import os
import base64
import logging
import httplib2
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from flask import Flask, request, jsonify, render_template
import pickle
from openai import OpenAI
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

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

# Function to retrieve the latest 3 emails
def get_latest_emails():
    service = authenticate_gmail()
    # Call the Gmail API to get the latest 3 messages in the inbox label, ordered by the most recent
    results = service.users().messages().list(userId='me', labelIds=['INBOX'], maxResults=3).execute()
    messages = results.get('messages', [])
    
    emails = []
    for msg in messages:
        msg_id = msg['id']
        message = service.users().messages().get(userId='me', id=msg_id).execute()

        # Extract message payload and decode it
        payload = message['payload']
        headers = payload.get('headers', [])
        subject = ''
        sender = ''
        for header in headers:
            if header['name'] == 'Subject':
                subject = header['value']
            if header['name'] == 'From':
                sender = header['value']

        # Decode the email body
        body = extract_email_body(payload)

        emails.append({'sender': sender, 'subject': subject, 'body': body, 'id': msg_id})
    
    return emails

# Function to extract the email body from payload
def extract_email_body(payload):
    body = ''
    if 'parts' in payload:
        for part in payload['parts']:
            if part['mimeType'] == 'text/plain' and 'data' in part['body']:
                data = part['body']['data']
                body = base64.urlsafe_b64decode(data).decode('utf-8')
                break
            elif part['mimeType'] == 'multipart/alternative':
                # If it's multipart/alternative, recursively search for text/plain
                for sub_part in part['parts']:
                    if sub_part['mimeType'] == 'text/plain' and 'data' in sub_part['body']:
                        data = sub_part['body']['data']
                        body = base64.urlsafe_b64decode(data).decode('utf-8')
                        break
    elif 'body' in payload and 'data' in payload['body']:
        data = payload['body']['data']
        body = base64.urlsafe_b64decode(data).decode('utf-8')
    return body

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

# Function to generate a reply to a summarized email using OpenAI
def generate_reply(summary, sender):
    # Call OpenAI API to generate a reply to the summary
    completion = client.chat.completions.create(
        model="gpt-4o-mini",  # Adjust the model based on your access and preference
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {
                "role": "user",
                "content": f"Generate a professional and friendly reply to this email summary:\n{summary}\n\nSign off with 'Best regards,\nAanvi' and address the reply to {sender}."
            }
        ]
    )
    reply = completion.choices[0].message.content.strip()
    return reply

# Function to send an email using Gmail API
def send_email(recipient, subject, body):
    service = authenticate_gmail()

    # Create the MIME message
    msg = MIMEMultipart()
    msg['From'] = 'me'  # 'me' means the authenticated user
    msg['To'] = recipient
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    raw_message = base64.urlsafe_b64encode(msg.as_bytes()).decode('utf-8')

    # Send the email
    send_message = service.users().messages().send(userId="me", body={'raw': raw_message}).execute()
    return send_message

# Function to escape special characters in the email body
def escape_js_string(text):
    if text is None:
        return ""
    # Escape special characters for JavaScript
    text = text.replace("'", "\\'").replace('"', '\\"').replace("\n", " ").replace("\r", "")
    return text

# Route to generate the reply (summary) and send it
@app.route('/generate_summary', methods=['POST'])
def generate_summary():
    email_id = request.form['email_id']
    emails = get_latest_emails()
    email = next((e for e in emails if e['id'] == email_id), None)

    if email:
        # Generate the summary
        summary = summarize_text(email['body'])

        # Generate the reply to the summary
        reply = generate_reply(summary, email['sender'])

        return jsonify({"summary": summary, "reply": reply, "email_id": email_id})
    else:
        return jsonify({"error": "Email not found."}), 404

# Route to handle sending email after summary and reply are ready
@app.route('/send_summary_reply', methods=['POST'])
def send_summary_reply():
    email_id = request.form['email_id']
    reply = request.form['reply']
    emails = get_latest_emails()
    email = next((e for e in emails if e['id'] == email_id), None)

    if email:
        # Send the reply
        send_email(email['sender'], f"Re: {email['subject']}", reply)
        return jsonify({'message': 'Email sent successfully!'}), 200
    else:
        return jsonify({'message': 'Failed to send email.'}), 500

# Route to display the latest emails and their summaries
# Route to display the latest emails and their summaries
@app.route('/')
def index():
    emails = get_latest_emails()

    # Extract the first 4 sentences of the body of each email and generate a summary
    for email in emails:
        sentences = re.split(r'(?<=[.!?]) +', email['body'])
        email['body_preview'] = ' '.join(sentences[:4])
        email['summary'] = summarize_text(email['body_preview'])  # Summary of the email body

    # Prioritize emails based on summaries
    sorted_emails = sorted(emails, key=lambda x: x['subject'].lower())  # Simplified prioritization for now

    # Add priority numbers to each email
    for idx, email in enumerate(sorted_emails, start=1):
        email['priority'] = idx

    # Generate the HTML content dynamically
    email_cards = ""
    for email in sorted_emails:
        body_escaped = escape_js_string(email['body'])  # Escape special characters in body
        summary_escaped = escape_js_string(email['summary'])  # Escape special characters in summary
        email_cards += f"""
          <div class="email-card" id="email-{email['id']}">
            <p><span class="priority-badge">Priority: {email['priority']}</span></p>
            <h4>From: {email['sender']}</h4>
            <p><strong>Subject:</strong> {email['subject']}</p>
            <p><strong>Summary:</strong> {email['summary']}</p>
            <button onclick="speakText('{summary_escaped}')">Read Summary Aloud</button>
            <button onclick="summarizeEmail('{email['id']}')">Generate Reply</button>
            <form id="reply-form-{email['id']}" onsubmit="sendReply(event, '{email['id']}')">
              <textarea id="reply-input-{email['id']}" name="reply" readonly></textarea>
              <button type="submit" id="send-reply-btn-{email['id']}" disabled>Send Reply</button>
            </form>
          </div>
        """

    html_content = f"""
    <!doctype html>
    <html lang="en">
      <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">
        <title>Latest Emails</title>
        <script>
          // Function to speak text (summary)
          function speakText(text) {{
            const utterance = new SpeechSynthesisUtterance(text);
            utterance.lang = 'en-US';
            utterance.pitch = 1;
            utterance.rate = 1;
            utterance.volume = 1;
            speechSynthesis.speak(utterance);
          }}

          // Function to summarize email
          function summarizeEmail(emailId) {{
            fetch('/generate_summary', {{
              method: 'POST',
              headers: {{
                'Content-Type': 'application/x-www-form-urlencoded',
              }},
              body: new URLSearchParams({{
                'email_id': emailId
              }})
            }})
            .then(response => response.json())
            .then(data => {{
              if (data.summary && data.reply) {{
                document.getElementById('reply-input-' + emailId).value = data.reply;
                document.getElementById('send-reply-btn-' + emailId).disabled = false;
              }} else {{
                alert('Error: ' + data.error);
              }}
            }})
            .catch(error => console.error('Error:', error));
          }}

          // Function to send the reply
          function sendReply(event, emailId) {{
            event.preventDefault();
            const reply = document.getElementById('reply-input-' + emailId).value;
            fetch('/send_summary_reply', {{
              method: 'POST',
              headers: {{
                'Content-Type': 'application/x-www-form-urlencoded',
              }},
              body: new URLSearchParams({{
                'email_id': emailId,
                'reply': reply
              }})
            }})
            .then(response => response.json())
            .then(data => {{
              alert(data.message);
            }})
            .catch(error => console.error('Error:', error));
          }}
        </script>
      </head>
      <body>
        <div class="container">
          <h1 class="mb-4">Latest Emails (Prioritized)</h1>
          {email_cards}
        </div>
      </body>
    </html>
    """

    return html_content


if __name__ == '__main__':
    app.run(debug=True)
