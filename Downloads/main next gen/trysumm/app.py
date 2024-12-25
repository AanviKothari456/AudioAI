from flask import Flask, request, redirect, session, url_for, jsonify, render_template
from openai import OpenAI

# Initialize the OpenAI client and Flask app
client = OpenAI()  # Ensure OpenAI is properly initialized with your API key
app = Flask(__name__)
app.secret_key = 'supersecretkey'

# In-memory user database and message storage
users = {}
messages = {}
schedules = {}  # Stores schedules for each user

class Calendar:
    def __init__(self, schedule):
        """
        Initialize the calendar with a list of time slots.
        Each time slot is a tuple in the form (start_time, end_time, status),
        where status can be 'free' or 'busy'.
        """
        self.schedule = schedule

    def find_common_free_slot(self, other_calendar):
        """
        Find common free slots between this calendar and another calendar.
        Returns a list of common free time slots.
        """
        common_free_slots = []
        for my_slot in self.schedule:
            if my_slot[2] == 'free':
                for their_slot in other_calendar.schedule:
                    if their_slot[2] == 'free':
                        start_time = max(my_slot[0], their_slot[0])
                        end_time = min(my_slot[1], their_slot[1])
                        if start_time < end_time:
                            common_free_slots.append((start_time, end_time))
                            self.mark_busy(start_time, end_time)
                            other_calendar.mark_busy(start_time, end_time)
        return common_free_slots

    def mark_busy(self, start_time, end_time):
        for i, (start, end, status) in enumerate(self.schedule):
            if start < end_time and end > start_time and status == 'free':
                if start < start_time:
                    self.schedule[i] = (start, start_time, 'free')
                    self.schedule.insert(i + 1, (start_time, end_time, 'busy'))
                    if end > end_time:
                        self.schedule.insert(i + 2, (end_time, end, 'free'))
                else:
                    self.schedule[i] = (start, end, 'busy')

    def format_schedule(self):
        formatted_schedule = []
        for start, end, status in self.schedule:
            formatted_schedule.append(f"{start}:00-{end}:00 - {status.capitalize()}")
        return "\n".join(formatted_schedule)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        schedule_9_10 = request.form['schedule_9_10']
        schedule_10_11 = request.form['schedule_10_11']
        schedule_11_12 = request.form['schedule_11_12']

        if username not in users:
            users[username] = password
            messages[username] = {}
            schedules[username] = [
                (9, 10, schedule_9_10.lower()),
                (10, 11, schedule_10_11.lower()),
                (11, 12, schedule_11_12.lower())
            ]
            return redirect(url_for('login'))
        else:
            return 'Username already exists. Please choose a different username.'
    return '''
    <form method="post">
        Username: <input type="text" name="username"><br>
        Password: <input type="password" name="password"><br>
        9-10: <input type="text" name="schedule_9_10" placeholder="free/busy"><br>
        10-11: <input type="text" name="schedule_10_11" placeholder="free/busy"><br>
        11-12: <input type="text" name="schedule_11_12" placeholder="free/busy"><br>
        <input type="submit" value="Register">
    </form>
    '''

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
    
    return '''
    <form method="post">
        Username: <input type="text" name="username"><br>
        Password: <input type="password" name="password"><br>
        <input type="submit" value="Login">
        <br><br>
        <a href="/register">Register</a>
    </form>
    '''

@app.route('/chat', methods=['GET', 'POST'])
def chat():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    current_user = session['username']
    user_schedule = schedules.get(current_user, [])
    schedule_display = "<h3>Your Schedule:</h3><br>" + "<br>".join(
        [f"{slot[0]}:00-{slot[1]}:00 - {slot[2].capitalize()}" for slot in user_schedule]
    )

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

    chat_display = ""
    for contact, conversation in messages[current_user].items():
        formatted_conversation = "<br>".join([f"<div style='margin-bottom: 10px;'>{msg}</div>" for msg in conversation])
        chat_display += f"<h3>Conversation with {contact}</h3><br>{formatted_conversation}<br>" + f'''
        <form onsubmit="summarizeConversation(event, '{contact}')">
            <button type="submit">Summarize Conversation</button>
        </form>
        <div id="summary-{contact}"></div>
        <br>
        <form onsubmit="generateReply(event, '{contact}')">
            <button type="submit">Generate Reply</button>
        </form>
        <div id="reply-container-{contact}">
            <textarea id="reply-{contact}" style="width: 100%; height: 100px;" readonly></textarea>
        </div>
        <br>
        <form onsubmit="checkSchedule(event, '{contact}')">
            <button type="submit">Generate Schedule Button</button>
        </form>
        <div id="schedule-{contact}"></div>
        <br>'''

    return f'''
    <h2>Welcome, {current_user}</h2>
    {schedule_display}
    <form method="post">
        Recipient: <input type="text" name="recipient"><br>
        Message: <input type="text" name="message"><br>
        <input type="submit" value="Send">
    </form>
    <h3>Chat History</h3>
    {chat_display}
    <br>
    <a href="/logout">Logout</a>
    ''' + '''
    <script>
        function summarizeConversation(event, contact) {
            event.preventDefault();
            fetch('/summarize', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ contact: contact })
            })
            .then(response => response.json())
            .then(data => {
                document.getElementById('summary-' + contact).innerText = 'Summary: ' + data.summary;
            })
            .catch(error => {
                console.error('Error:', error);
            });
        }

        function generateReply(event, contact) {
            event.preventDefault();
            fetch('/generate_reply', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ contact: contact })
            })
            .then(response => response.json())
            .then(data => {
                const replyContainer = document.getElementById('reply-' + contact);
                replyContainer.value = data.reply;
                replyContainer.removeAttribute('readonly');
            })
            .catch(error => {
                console.error('Error:', error);
            });
        }

        function checkSchedule(event, contact) {
            event.preventDefault();
            fetch('/check_schedule', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ contact: contact })
            })
            .then(response => response.json())
            .then(data => {
                document.getElementById('schedule-' + contact).innerText = data.message;
            })
            .catch(error => {
                console.error('Error:', error);
            });
        }
    </script>
    '''

if __name__ == '__main__':
    app.run(debug=True)
