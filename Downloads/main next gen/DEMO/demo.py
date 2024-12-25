


from datetime import date, datetime, time
from flask import Flask, request, redirect, session, url_for, jsonify, render_template
from openai import OpenAI
import re

# Initialize the OpenAI client and Flask app
client = OpenAI()  # Ensure OpenAI is properly initialized with your API key
app = Flask(__name__)
app.secret_key = 'supersecretkey'

# In-memory user database and message storage
users = {}
messages = {}
availability = {}  # New dictionary to store user availability

@app.route('/register', methods=['GET', 'POST'])
def register():
    time_slots = ['10-11', '11-12', '12-1']
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username not in users:
            # Get availability data
            user_availability = {}
            for slot in time_slots:
                status = request.form.get(slot)
                user_availability[slot] = status
            # Store user data
            users[username] = password
            messages[username] = {}
            availability[username] = user_availability  # Store availability
            return redirect(url_for('login'))
        else:
            return 'Username already exists. Please choose a different username.'
    return render_template('register.html', time_slots=time_slots)

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username in users and users[username] == password:
            session['username'] = username
            return redirect(url_for('chat'))
        else:
            return 'Invalid credentials. Please try again.'
    return render_template('login.html')

@app.route('/chat', methods=['GET', 'POST'])
def chat():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    current_user = session['username']
    if request.method == 'POST':
        recipient = request.form['recipient']
        message = request.form['message']
        if recipient in users and recipient != current_user:
            if recipient not in messages[current_user]:
                messages[current_user][recipient] = []
            if current_user not in messages[recipient]:
                messages[recipient][current_user] = []

            messages[recipient][current_user].append(f"{current_user}: {message}")
            messages[current_user][recipient].append(f"{current_user}: {message}")
        else:
            return 'Recipient not found or invalid recipient.'

    user_conversations = messages.get(current_user, {})
    user_availability = availability.get(current_user, {})
    return render_template('chat.html', current_user=current_user, user_conversations=user_conversations, user_availability=user_availability)

@app.route('/summarize', methods=['POST'])
def summarize():
    if 'username' not in session:
        return redirect(url_for('login'))

    data = request.get_json()
    current_user = session['username']
    contact = data['contact']
    conversation = messages[current_user].get(contact, [])

    if not conversation:
        return jsonify({"summary": "No conversation found to summarize."})

    conversation_text = "\n".join(conversation)

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

    return jsonify({"summary": summary})

@app.route('/generate_reply', methods=['POST'])
def generate_reply():
    if 'username' not in session:
        return redirect(url_for('login'))

    data = request.get_json()
    current_user = session['username']
    contact = data['contact']
    conversation = messages[current_user].get(contact, [])

    if not conversation:
        return jsonify({"reply": "No conversation found to generate a reply."})

    conversation_text = "\n".join(conversation)

    # Call OpenAI API to generate a reply
    completion = client.chat.completions.create(
        model="gpt-4o-mini",  # Adjust the model based on your access and preference
        messages=[
            {"role": "system", "content": "You are an email assistant that replies professionally and helpfully."},
            {"role": "user", "content": f"Reply to this email:\n{conversation_text}"}
        ]
    )
    reply = completion.choices[0].message.content.strip()

    return jsonify({"reply": reply})

@app.route('/extract_links', methods=['POST'])
def extract_links():
    if 'username' not in session:
        return redirect(url_for('login'))

    data = request.get_json()
    current_user = session['username']
    contact = data['contact']
    conversation = messages[current_user].get(contact, [])

    if not conversation:
        return jsonify({"links": []})

    conversation_text = "\n".join(conversation)
    links = re.findall(r'https?://\S+', conversation_text)

    return jsonify({"links": links})

@app.route('/get_availability', methods=['GET'])
def get_availability():
    if 'username' not in session:
        return redirect(url_for('login'))

    current_user = session['username']
    user_availability = availability.get(current_user, {})

    # Get today's date
    today = date.today()

    # Convert availability to a list of events
    events = []
    for time_slot, status in user_availability.items():
        start_hour, end_hour = map(int, time_slot.split('-'))
        start_datetime = datetime.combine(today, time(start_hour))
        end_datetime = datetime.combine(today, time(end_hour))
        event = {
            'title': status,
            'start': start_datetime.isoformat(),
            'end': end_datetime.isoformat(),
            'color': '#28a745' if status == 'Free' else '#dc3545'
        }
        events.append(event)

    return jsonify(events)

@app.route('/detect_meeting', methods=['POST'])
def detect_meeting():
    if 'username' not in session:
        return redirect(url_for('login'))

    data = request.get_json()
    current_user = session['username']
    contact = data['contact']
    conversation = messages[current_user].get(contact, [])

    if not conversation:
        return jsonify({"meeting_required": False})

    conversation_text = "\n".join(conversation)

    # Call OpenAI API to analyze the conversation and detect if a meeting is required
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are an assistant that determines if a meeting is required."},
            {"role": "user", "content": f"Analyze the following conversation and determine if a meeting is needed: {conversation_text}"}
        ]
    )
    analysis_result = completion.choices[0].message.content.strip().lower()
    
    meeting_required = "yes" in analysis_result or "meeting" in analysis_result

    return jsonify({"meeting_required": meeting_required})
@app.route('/categories', methods=['GET'])
def categories():
    # Replace this with your logic for rendering the categories page
    return render_template('categories.html')

@app.route('/calendar', methods=['GET'])
def calendar():
    # Render the calendar page
    return render_template('calendar.html')

@app.route('/priority', methods=['GET'])
def priority():
    # Render the priority page
    return render_template('priority.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
