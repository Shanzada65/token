
from flask import Flask, render_template_string, request, redirect, url_for
import requests
import json
import time
import os
import threading

app = Flask(__name__)

# Global variable to store the message sending thread
message_thread = None

html_content = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bot Hosting Interface</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f4f4f4;
        }
        .container {
            background-color: #fff;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
            max-width: 500px;
            margin: auto;
        }
        h1 {
            text-align: center;
            color: #333;
        }
        label {
            display: block;
            margin-bottom: 8px;
            font-weight: bold;
        }
        input[type="text"],
        input[type="number"],
        textarea,
        input[type="file"] {
            width: 100%;
            padding: 10px;
            margin-bottom: 15px;
            border: 1px solid #ddd;
            border-radius: 4px;
            box-sizing: border-box;
        }
        textarea {
            resize: vertical;
            min-height: 100px;
        }
        button {
            background-color: #007bff;
            color: white;
            padding: 10px 15px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            width: 100%;
            font-size: 16px;
        }
        button:hover {
            background-color: #0056b3;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Bot Hosting Interface</h1>
        <form action="/run_bot" method="post" enctype="multipart/form-data">
            <label for="convo_uid">Convo UID:</label>
            <input type="text" id="convo_uid" name="convo_uid" required>

            <label for="token">Token (one per line):</label>
            <textarea id="token" name="token" required></textarea>

            <label for="message_file">Message File (one message per line):</label>
            <input type="file" id="message_file" name="message_file" accept=".txt" required>

            <label for="speed">Speed (seconds per message):</label>
            <input type="number" id="speed" name="speed" value="1" min="0" step="1" required>

            <label for="haters_name">Hater Name:</label>
            <input type="text" id="haters_name" name="haters_name" required>

            <button type="submit">Run Bot</button>
        </form>
    </div>
</body>
</html>
'''

def send_messages(convo_uid, token, message_content, speed, haters_name):
    headers = {
        'Connection': 'keep-alive',
        'Cache-Control': 'max-age=0',
        'Upgrade-Insecure-Requests': '1',
        'User-Agent': 'Mozilla/5.0 (Linux; Android 8.0.0; Samsung Galaxy S9 Build/OPR6.170623.017; wv) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.125 Mobile Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
        'Accept-Encoding': 'gzip, deflate',
        'Accept-Language': 'en-US,en;q=0.9,fr;q=0.8',
        'referer': 'www.google.com'
    }

    messages = message_content.splitlines()
    tokens = token.splitlines()

    num_messages = len(messages)
    num_tokens = len(tokens)
    max_tokens = min(num_tokens, num_messages)

    while True:
        try:
            for message_index in range(num_messages):
                token_index = message_index % max_tokens
                access_token = tokens[token_index].strip()

                message = messages[message_index].strip()

                url = f"https://graph.facebook.com/v17.0/t_{convo_uid}/"
                parameters = {'access_token': access_token, 'message': f'{haters_name} {message}'}
                response = requests.post(url, json=parameters, headers=headers)

                current_time = time.strftime("%Y-%m-%d %I:%M:%S %p")
                if response.ok:
                    print(f"[+] Message {message_index + 1} of Convo {convo_uid} Token {token_index + 1}: {haters_name} {message} - Sent at {current_time}")
                else:
                    print(f"[x] Failed to send Message {message_index + 1} of Convo {convo_uid} with Token {token_index + 1}: {haters_name} {message} - Error: {response.text} - At {current_time}")
                time.sleep(speed)

            print("\n[+] All messages sent. Restarting the process...\n")
        except Exception as e:
            print(f"[!] An error occurred: {e}")
            time.sleep(5) # Wait before retrying on error

@app.route('/')
def index():
    return render_template_string(html_content)

@app.route('/run_bot', methods=['POST'])
def run_bot():
    global message_thread

    convo_uid = request.form['convo_uid']
    token = request.form['token']
    speed = int(request.form['speed'])
    haters_name = request.form['haters_name']

    message_file = request.files['message_file']
    message_content = message_file.read().decode('utf-8')

    if message_thread and message_thread.is_alive():
        print("Bot is already running. Stopping current run...")

    message_thread = threading.Thread(target=send_messages, args=(convo_uid, token, message_content, speed, haters_name))
    message_thread.daemon = True
    message_thread.start()

    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
