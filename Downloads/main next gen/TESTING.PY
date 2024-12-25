import os
import base64
import logging
import httplib2
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from flask import Flask, request, jsonify, redirect, session, url_for, render_template
import pickle
from openai import OpenAI
import re
import html

# Define the scopes for Gmail API access
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
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

# Function to generate a reply to an email using OpenAI
def generate_reply(email_body, sender):
    # Call OpenAI API to generate a reply
    completion = client.chat.completions.create(
        model="gpt-4o-mini",  # Adjust the model based on your access and preference
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {
                "role": "user",
                "content": f"Generate a professional and friendly reply to this email:\n{email_body}\n\nSign off with 'Best regards,\nAanvi' and address the reply to {sender}."
            }
        ]
    )
    reply = completion.choices[0].message.content.strip()
    return reply

# Function to prioritize emails based on summaries
def prioritize_emails(emails):
    return sorted(emails, key=lambda x: x['subject'].lower())  # Simplified prioritization for now

# Route to display the latest 3 emails and their summaries
@app.route('/')
def index():
    emails = get_latest_emails()

    # Extract the first 4 sentences of the body of each email and generate a summary
    for email in emails:
        sentences = re.split(r'(?<=[.!?]) +', email['body'])
        email['body_preview'] = ' '.join(sentences[:4])
        email['summary'] = summarize_text(email['body_preview'])

    # Prioritize emails based on summaries
    sorted_emails = prioritize_emails(emails)

    # Add priority numbers to each email
    for idx, email in enumerate(sorted_emails, start=1):
        email['priority'] = idx

    # Generate the HTML content dynamically
    email_cards = ""
    for email in sorted_emails:
        # Use html.escape to safely include text in HTML and JavaScript
        escaped_summary = html.escape(email['summary'])
        escaped_sender = html.escape(email['sender'])
        escaped_subject = html.escape(email['subject'])

        # Remove line breaks from escaped_summary to avoid JavaScript issues
        escaped_summary = escaped_summary.replace("\n", " ").replace("\r", "")

        # Fallback for empty summaries
        escaped_summary = escaped_summary if escaped_summary else "No summary available"

        email_cards += f"""
          <div class="email-card" id="email-{email['id']}">
            <p><span class="priority-badge">Priority: {email['priority']}</span></p>
            <h4>From: {escaped_sender}</h4>
            <p><strong>Subject:</strong> {escaped_subject}</p>
            <p style="display: flex; align-items: center;">
                <strong>Summary:</strong> {escaped_summary}
                <button class="speak-summary-btn ml-3" onclick="speakSummary('{escaped_summary}')">Listen</button>
            </p>
            <form action="/generate_reply" method="post" onsubmit="generateReply(event, '{email['id']}')" style="margin-top: 15px;">
              <input type="hidden" name="email_id" value="{email['id']}">
              <button type="submit" class="generate-reply-btn">Generate Reply</button>
            </form>
            <div class="reply" id="reply-{email['id']}" style="display:none;"></div>
          </div>
        """

    html_content = f"""
    <!doctype html>
    <html lang="en">
      <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">
        <title>Latest Emails with Text-to-Speech</title>
        <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css">
        <style>
          body {{
            background-color: #f8f9fa;
            padding: 20px;
          }}
          .email-card {{
            background-color: #ffffff;
            border-radius: 10px;
            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
            margin-bottom: 20px;
            padding: 20px;
          }}
          .priority-badge {{
            background-color: #007bff;
            color: #ffffff;
            padding: 5px 10px;
            border-radius: 5px;
          }}
          .generate-reply-btn, .speak-summary-btn, .speak-sample-btn {{
            background-color: #28a745;
            color: #ffffff;
            padding: 10px 20px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            margin-left: 10px;
          }}
          .generate-reply-btn:hover, .speak-summary-btn:hover, .speak-sample-btn:hover {{
            background-color: #218838;
          }}
          .reply {{
            margin-top: 20px;
            padding: 15px;
            background-color: #e9f7ef;
            border-radius: 10px;
            border: 1px solid #d4edda;
          }}
          .ml-3 {{
            margin-left: 15px;
          }}
        </style>
      </head>
      <body>
        <div class="container">
          <h1 class="mb-4">Latest Emails (Prioritized)</h1>
          <button class="speak-sample-btn mb-4" onclick="speakSampleText()">Listen to Sample Text</button>
          {email_cards}
        </div>
        <script>
          function generateReply(event, emailId) {{
            event.preventDefault();
            fetch('/generate_reply', {{
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
              if (data.reply) {{
                document.getElementById(`reply-${{emailId}}`).innerHTML = `<strong>Generated Reply:</strong><p>${{data.reply}}</p>`;
                document.getElementById(`reply-${{emailId}}`).style.display = 'block';
              }} else {{
                alert('Error: ' + data.error);
              }}
            }})
            .catch(error => console.error('Error:', error));
          }}

          // Function to speak the summary of an email
          function speakSummary(summary) {{
            try {{
              console.log("speakSummary called with summary:", summary);
              if (!('speechSynthesis' in window)) {{
                alert("Your browser does not support text-to-speech.");
                return;
              }}
              const utterance = new SpeechSynthesisUtterance(summary);
              utterance.lang = 'en-US';
              utterance.pitch = 1;
              utterance.rate = 1;
              utterance.volume = 1;

              utterance.onstart = () => {{
                console.log("Speech has started.");
              }};
              
              utterance.onend = () => {{
                console.log("Speech has finished.");
              }};

              utterance.onerror = (event) => {{
                console.error("SpeechSynthesisUtterance error:", event.error);
              }};

              if (summary) {{
                speechSynthesis.speak(utterance);
              }} else {{
                console.warn("Empty summary provided to speech synthesis.");
              }}
            }} catch (error) {{
              console.error("Error during text-to-speech:", error);
            }}
          }}

          // Function to speak a sample text
          function speakSampleText() {{
            const sampleText = "Hello, I am working";
            try {{
              console.log("speakSampleText called with text:", sampleText);
              if (!('speechSynthesis' in window)) {{
                alert("Your browser does not support text-to-speech.");
                return;
              }}
              const utterance = new SpeechSynthesisUtterance(sampleText);
              utterance.lang = 'en-US';
              utterance.pitch = 1;
              utterance.rate = 1;
              utterance.volume = 1;

              utterance.onstart = () => {{
                console.log("Speech has started.");
              }};
              
              utterance.onend = () => {{
                console.log("Speech has finished.");
              }};

              utterance.onerror = (event) => {{
                console.error("SpeechSynthesisUtterance error:", event.error);
              }};

              speechSynthesis.speak(utterance);
            }} catch (error) {{
              console.error("Error during text-to-speech:", error);
            }}
          }}
        </script>
      </body>
    </html>
    """

    return html_content

# Route to generate a reply to an email
@app.route('/generate_reply', methods=['POST'])
def generate_reply_route():
    email_id = request.form['email_id']
    emails = get_latest_emails()
    email = next((e for e in emails if e['id'] == email_id), None)

    if email:
        reply = generate_reply(email['body'], email['sender'])
        return jsonify({"reply": reply, "email_id": email_id})
    else:
        return jsonify({"error": "Email not found."}), 404

# Run the Flask app
if __name__ == '__main__':
    app.run(port=53730, debug=True)
