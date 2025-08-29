from flask import Flask, render_template_string, request, redirect, url_for, jsonify
import requests
import json
import time
import os
import threading
from datetime import datetime

app = Flask(__name__)

# Global variables
message_thread = None
stop_flag = False
logs = []

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
            max-width: 800px;
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
            margin-bottom: 10px;
        }
        button:hover {
            background-color: #0056b3;
        }
        .button-danger {
            background-color: #dc3545;
        }
        .button-danger:hover {
            background-color: #c82333;
        }
        .button-success {
            background-color: #28a745;
        }
        .button-success:hover {
            background-color: #218838;
        }
        .tabs {
            display: flex;
            margin-bottom: 20px;
        }
        .tab {
            padding: 10px 20px;
            cursor: pointer;
            background-color: #f1f1f1;
            border: 1px solid #ddd;
            border-bottom: none;
            border-radius: 5px 5px 0 0;
            margin-right: 5px;
        }
        .tab.active {
            background-color: #fff;
            font-weight: bold;
        }
        .tab-content {
            display: none;
            border: 1px solid #ddd;
            padding: 20px;
            border-radius: 0 0 5px 5px;
        }
        .tab-content.active {
            display: block;
        }
        .log-container {
            height: 300px;
            overflow-y: auto;
            border: 1px solid #ddd;
            padding: 10px;
            margin-bottom: 15px;
            background-color: #f8f9fa;
            font-family: monospace;
            font-size: 12px;
        }
        .token-result {
            margin-bottom: 15px;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 4px;
        }
        .token-valid {
            background-color: #d4edda;
            border-color: #c3e6cb;
        }
        .token-invalid {
            background-color: #f8d7da;
            border-color: #f5c6cb;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Bot Hosting Interface</h1>
        
        <div class="tabs">
            <div class="tab active" onclick="switchTab('bot-tab')">Bot Control</div>
            <div class="tab" onclick="switchTab('token-tab')">Token Checker</div>
            <div class="tab" onclick="switchTab('logs-tab')">View Logs</div>
        </div>
        
        <div id="bot-tab" class="tab-content active">
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

                <button type="submit" class="button-success">Run Bot</button>
            </form>
            
            <form action="/stop_bot" method="post">
                <button type="submit" class="button-danger">Stop Bot</button>
            </form>
        </div>
        
        <div id="token-tab" class="tab-content">
            <label for="check_tokens">Tokens to Check (one per line):</label>
            <textarea id="check_tokens" name="check_tokens"></textarea>
            <button onclick="checkTokens()" class="button-success">Check Tokens</button>
            <div id="token-results"></div>
        </div>
        
        <div id="logs-tab" class="tab-content">
            <div class="log-container" id="log-container">
                {% for log in logs %}
                <div>{{ log }}</div>
                {% endfor %}
            </div>
            <button onclick="refreshLogs()">Refresh Logs</button>
            <button onclick="clearLogs()" class="button-danger">Clear Logs</button>
        </div>
    </div>

    <script>
        function switchTab(tabId) {
            // Hide all tab contents
            document.querySelectorAll('.tab-content').forEach(tab => {
                tab.classList.remove('active');
            });
            
            // Show selected tab content
            document.getElementById(tabId).classList.add('active');
            
            // Update active tab
            document.querySelectorAll('.tab').forEach(tab => {
                tab.classList.remove('active');
            });
            event.currentTarget.classList.add('active');
            
            // If switching to logs tab, refresh logs
            if (tabId === 'logs-tab') {
                refreshLogs();
            }
        }
        
        function checkTokens() {
            const tokens = document.getElementById('check_tokens').value.split('\\n');
            const resultsContainer = document.getElementById('token-results');
            resultsContainer.innerHTML = '<div>Checking tokens...</div>';
            
            fetch('/check_tokens', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({tokens: tokens}),
            })
            .then(response => response.json())
            .then(data => {
                resultsContainer.innerHTML = '';
                data.results.forEach(result => {
                    const div = document.createElement('div');
                    div.className = result.valid ? 'token-result token-valid' : 'token-result token-invalid';
                    div.innerHTML = `<strong>${result.token}</strong>: ${result.message}`;
                    if (result.valid && result.name) {
                        div.innerHTML += `<br>Name: ${result.name}`;
                    }
                    if (result.valid && result.picture) {
                        div.innerHTML += `<br><img src="${result.picture}" width="50" height="50">`;
                    }
                    resultsContainer.appendChild(div);
                });
            })
            .catch(error => {
                resultsContainer.innerHTML = '<div>Error checking tokens</div>';
            });
        }
        
        function refreshLogs() {
            fetch('/get_logs')
            .then(response => response.json())
            .then(data => {
                const logContainer = document.getElementById('log-container');
                logContainer.innerHTML = '';
                data.logs.forEach(log => {
                    const div = document.createElement('div');
                    div.textContent = log;
                    logContainer.appendChild(div);
                });
                logContainer.scrollTop = logContainer.scrollHeight;
            });
        }
        
        function clearLogs() {
            fetch('/clear_logs', {method: 'POST'})
            .then(() => refreshLogs());
        }
        
        // Auto-refresh logs if on logs tab
        setInterval(() => {
            if (document.getElementById('logs-tab').classList.contains('active')) {
                refreshLogs();
            }
        }, 5000);
    </script>
</body>
</html>
'''

def add_log(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {message}"
    logs.append(log_entry)
    # Keep only the last 1000 logs to prevent memory issues
    if len(logs) > 1000:
        del logs[0:len(logs)-1000]

def check_token_validity(token):
    """Check if a Facebook token is valid and return user info"""
    try:
        # First, check if token is valid
        url = f"https://graph.facebook.com/v17.0/me?access_token={token}"
        response = requests.get(url)
        
        if response.status_code == 200:
            user_data = response.json()
            user_id = user_data.get('id')
            
            # Get profile picture
            picture_url = f"https://graph.facebook.com/v17.0/{user_id}/picture?access_token={token}&redirect=false"
            picture_response = requests.get(picture_url)
            picture_data = picture_response.json()
            picture = picture_data.get('data', {}).get('url') if picture_response.status_code == 200 else None
            
            # Get user name
            name_url = f"https://graph.facebook.com/v17.0/{user_id}?fields=name&access_token={token}"
            name_response = requests.get(name_url)
            name_data = name_response.json()
            name = name_data.get('name') if name_response.status_code == 200 else "Unknown"
            
            return {
                'valid': True,
                'message': 'Valid token',
                'name': name,
                'picture': picture
            }
        else:
            return {
                'valid': False,
                'message': f'Invalid token: {response.json().get("error", {}).get("message", "Unknown error")}',
                'name': None,
                'picture': None
            }
    except Exception as e:
        return {
            'valid': False,
            'message': f'Error checking token: {str(e)}',
            'name': None,
            'picture': None
        }

def send_messages(convo_uid, tokens, message_content, speed, haters_name):
    global stop_flag
    
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
    tokens = tokens.splitlines()

    num_messages = len(messages)
    num_tokens = len(tokens)
    max_tokens = min(num_tokens, num_messages)

    add_log(f"Starting bot with {num_messages} messages and {num_tokens} tokens")
    
    while not stop_flag:
        try:
            for message_index in range(num_messages):
                if stop_flag:
                    add_log("Bot stopped by user")
                    break
                    
                token_index = message_index % max_tokens
                access_token = tokens[token_index].strip()

                message = messages[message_index].strip()

                url = f"https://graph.facebook.com/v17.0/t_{convo_uid}/"
                parameters = {'access_token': access_token, 'message': f'{haters_name} {message}'}
                response = requests.post(url, json=parameters, headers=headers)

                current_time = time.strftime("%Y-%m-%d %I:%M:%S %p")
                if response.ok:
                    log_msg = f"[+] Message {message_index + 1} of Convo {convo_uid} Token {token_index + 1}: {haters_name} {message} - Sent at {current_time}"
                    add_log(log_msg)
                else:
                    log_msg = f"[x] Failed to send Message {message_index + 1} of Convo {convo_uid} with Token {token_index + 1}: {haters_name} {message} - Error: {response.text} - At {current_time}"
                    add_log(log_msg)
                time.sleep(speed)

            if stop_flag:
                break
                
            add_log("[+] All messages sent. Restarting the process...")
        except Exception as e:
            error_msg = f"[!] An error occurred: {e}"
            add_log(error_msg)
            time.sleep(5) # Wait before retrying on error
    
    stop_flag = False
    add_log("Bot execution completed")

@app.route('/')
def index():
    return render_template_string(html_content, logs=logs[-20:] if logs else [])

@app.route('/run_bot', methods=['POST'])
def run_bot():
    global message_thread, stop_flag

    convo_uid = request.form['convo_uid']
    token = request.form['token']
    speed = int(request.form['speed'])
    haters_name = request.form['haters_name']

    message_file = request.files['message_file']
    message_content = message_file.read().decode('utf-8')

    if message_thread and message_thread.is_alive():
        add_log("Stopping previous bot instance...")
        stop_flag = True
        time.sleep(1)  # Give time for the thread to stop

    stop_flag = False
    message_thread = threading.Thread(target=send_messages, args=(convo_uid, token, message_content, speed, haters_name))
    message_thread.daemon = True
    message_thread.start()

    add_log("Bot started successfully")
    return redirect(url_for('index'))

@app.route('/stop_bot', methods=['POST'])
def stop_bot():
    global stop_flag
    stop_flag = True
    add_log("Stop command received")
    return redirect(url_for('index'))

@app.route('/check_tokens', methods=['POST'])
def check_tokens():
    data = request.json
    tokens = data.get('tokens', [])
    
    results = []
    for token in tokens:
        if token.strip():  # Only check non-empty tokens
            result = check_token_validity(token.strip())
            result['token'] = token.strip()  # Add the token to the result
            results.append(result)
    
    return jsonify({'results': results})

@app.route('/get_logs')
def get_logs():
    return jsonify({'logs': logs})

@app.route('/clear_logs', methods=['POST'])
def clear_logs():
    global logs
    logs = []
    return jsonify({'status': 'success'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
