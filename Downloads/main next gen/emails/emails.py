from flask import Flask, request, redirect, session, url_for, jsonify
from openai import OpenAI

# Initialize the OpenAI client and Flask app
client = OpenAI()  # Ensure OpenAI is properly initialized with your API key
app = Flask(__name__)
app.secret_key = 'supersecretkey'

# In-memory user database and message storage
users = {}
messages = {}

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username not in users:
            users[username] = password
            messages[username] = {}
            return redirect(url_for('login'))
        else:
            return 'Username already exists. Please choose a different username.'
    return '''
    <form method="post">
        Username: <input type="text" name="username"><br>
        Password: <input type="password" name="password"><br>
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
        <br>'''

    return f'''
    <h2>Welcome, {current_user}</h2>
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
                replyContainer.value = data.reply;  // Set the generated reply as editable text
                replyContainer.removeAttribute('readonly');  // Make it editable
            })
            .catch(error => {
                console.error('Error:', error);
            });
        }
    </script>
    '''

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

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
