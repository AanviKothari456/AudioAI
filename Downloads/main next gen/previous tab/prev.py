from flask import Flask, render_template, request, jsonify
from openai import OpenAI

# Initialize the OpenAI client and Flask app
client = OpenAI()
app = Flask(__name__)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/categorize_threads', methods=['POST'])
def categorize_threads():
    # Demo emails to simulate real email input
    emails = [
        "Hi John, I wanted to follow up on our last meeting regarding the project timeline. Could you please provide an update on the deliverables? Thanks, - Client",
        "Hello, I am interested in setting up a meeting to discuss potential collaboration. Let me know your availability. Regards, - Client",
        "Reminder: Your next CS101 assignment is due this Friday. Make sure to submit it before midnight. - School",
        "This month in Tech News: AI advancements, new software releases, and upcoming conferences. Stay updated with our newsletter! - Newsletter"
    ]

    # Dictionary to hold thread titles and summaries
    threads = {}

    # Use OpenAI to categorize and summarize threads
    for i, email in enumerate(emails):
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an AI that organizes and summarizes email threads into cohesive topics with concise summaries."},
                {"role": "user", "content": f"Categorize this email with related emails and provide a title and a 2-line summary:\n{email}"}
            ]
        )
        response = completion.choices[0].message.content.strip()

        # Extract title and summary from the response
        lines = response.split('\n', 1)
        title = lines[0].strip()
        summary = lines[1].strip() if len(lines) > 1 else "No summary provided."

        # Add to threads dictionary
        if title in threads:
            threads[title].append({'email': email, 'summary': summary})
        else:
            threads[title] = [{'email': email, 'summary': summary}]

    # Prepare output to display categorized threads and their summaries
    formatted_threads = {title: "\n".join([entry['summary'] for entry in entries]) for title, entries in threads.items()}

    return jsonify(formatted_threads)

if __name__ == '__main__':
    app.run(debug=True)
