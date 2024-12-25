from flask import Flask, render_template, request, jsonify
from openai import OpenAI

# Initialize the OpenAI client and Flask app
client = OpenAI()
app = Flask(__name__)

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
            if my_slot[2] == 'free':  # Check if the slot is free in this calendar
                for their_slot in other_calendar.schedule:
                    if their_slot[2] == 'free':  # Check if the slot is free in the other calendar
                        # Find overlapping free time
                        start_time = max(my_slot[0], their_slot[0])
                        end_time = min(my_slot[1], their_slot[1])

                        if start_time < end_time:  # Ensure it's a valid time slot
                            common_free_slots.append((start_time, end_time))

                            # Mark the common slot as busy in both calendars
                            self.mark_busy(start_time, end_time)
                            other_calendar.mark_busy(start_time, end_time)

        return common_free_slots

    def mark_busy(self, start_time, end_time):
        """
        Mark the time range between start_time and end_time as 'busy' in the calendar.
        """
        for i, (start, end, status) in enumerate(self.schedule):
            if start < end_time and end > start_time and status == 'free':
                # Adjust the schedule and mark the slot as busy
                if start < start_time:
                    self.schedule[i] = (start, start_time, 'free')
                    self.schedule.insert(i + 1, (start_time, end_time, 'busy'))
                    if end > end_time:
                        self.schedule.insert(i + 2, (end_time, end, 'free'))
                else:
                    self.schedule[i] = (start, end, 'busy')

    def format_schedule(self):
        """
        Return a formatted string representation of the schedule.
        """
        formatted_schedule = []
        for start, end, status in self.schedule:
            formatted_schedule.append(f"{start}:00-{end}:00 - {status.capitalize()}")
        return "\n".join(formatted_schedule)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/schedule_meeting', methods=['POST'])
def schedule_meeting():
    email_text = request.form['emailText']

    # Step 1: Use OpenAI to determine if a meeting needs to be scheduled
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are an AI assistant that determines if a meeting needs to be scheduled based on the email content."},
            {"role": "user", "content": f"Does this email require scheduling a meeting?\n{email_text}"}
        ]
    )

    response = completion.choices[0].message.content.strip().lower()

    # Step 2: Check if the AI response indicates a meeting is needed
    if 'yes' in response or 'schedule' in response:
        # Sample schedules for demonstration (these would typically be user inputs)
        my_schedule = [
            (9, 10, 'busy'),  # 9-10am busy
            (10, 11, 'free'),  # 10-11am free
            (11, 12, 'busy'),  # 11-12pm busy
            (12, 13, 'free')   # 12-1pm free
        ]

        sabrina_schedule = [
            (9, 10, 'free'),   # 9-10am free
            (10, 11, 'busy'),  # 10-11am busy
            (11, 12, 'busy'),  # 11-12pm busy
            (12, 13, 'free')   # 12-1pm free
        ]

        my_calendar = Calendar(my_schedule)
        sabrina_calendar = Calendar(sabrina_schedule)

        # Step 3: Find common free slots
        common_slots = my_calendar.find_common_free_slot(sabrina_calendar)

        # Step 4: Return common free slots and formatted schedules
        result = {
            "meeting_needed": True,
            "my_schedule": my_calendar.format_schedule(),
            "sabrina_schedule": sabrina_calendar.format_schedule()
        }

        if common_slots:
            result["common_slots"] = [f"{slot[0]}:00-{slot[1]}:00" for slot in common_slots]
        else:
            result["common_slots"] = "No common free slots found."

        return jsonify(result)
    else:
        return jsonify({"meeting_needed": False, "message": "No meeting scheduling is needed for this email."})

if __name__ == '__main__':
    app.run(debug=True)
