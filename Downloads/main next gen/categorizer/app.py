from flask import Flask, render_template, request, jsonify, send_file
from openai import OpenAI
from pathlib import Path

# Initialize the OpenAI client and Flask app
client = OpenAI()
app = Flask(__name__)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/categorize', methods=['POST'])
def categorize_emails():
    emails = [
        request.form.get('email1', ''),
        request.form.get('email2', ''),
        request.form.get('email3', ''),
        request.form.get('email4', '')
    ]

    categorized_emails = {}

    for email in emails:
        if email.strip():  # Ensure the email is not empty
            completion = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": (
                        "You are an AI that reads and categorizes emails into broad, reusable categories. "
                        "Examples include 'Academic Updates', 'Job Opportunities', 'Order Notifications', and 'Newsletters'. "
                        "If an email fits an existing category, use that category name. "
                        "Return the category name followed by a colon and the email content."
                    )},
                    {"role": "user", "content": f"Categorize this email:\n{email}"}
                ]
            )
            response = completion.choices[0].message.content.strip()

            # Extract category and email
            if ':' in response:
                category, categorized_email = map(str.strip, response.split(':', 1))
                if category and categorized_email:
                    if category not in categorized_emails:
                        categorized_emails[category] = []
                    categorized_emails[category].append(categorized_email)

    return jsonify(categorized_emails)

if __name__ == '__main__':
    app.run(debug=True)
