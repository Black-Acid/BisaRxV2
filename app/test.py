import requests

# Dummy history (simulating previous messages in a session)
dummy_history = [
    {"sender": "user", "message_text": "Hello, my leg feels numb."},
    {"sender": "ai", "message_text": "I'm glad you're here. Can you tell me more about the numbness?"},
    {"sender": "user", "message_text": "It happens mostly in the mornings and sometimes tingles."},
    {"sender": "ai", "message_text": "Thanks for the info. Have you had any recent injuries or started new medications?"}
]

# Concatenate into a single string for AI
full_message = ""
for msg in dummy_history:
    role = "You" if msg["sender"] == "user" else "AI"
    full_message += f"{role}: {msg['message_text']}\n"

# Add new user message
new_user_message = "Also, my left knee feels weak."
full_message += f"You: {new_user_message}\n"

print("Message to send to AI:\n")
print(full_message)




url = "https://bisarx-assistant-1031993103540.us-central1.run.app/chat"

payload = {
    "message": full_message
}

headers = {
    "Content-Type": "application/json"
}

response = requests.post(
    url,
    json=payload,
    headers=headers,
    timeout=30  # good practice
)

print("Status Code:", response.status_code)
print("Response JSON:", response.json())

