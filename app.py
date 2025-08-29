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
    <title>Enhanced Task Manager</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
            max-width: 1200px;
            margin: 0 auto;
            overflow: hidden;
        }
        
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }
        
        .header h1 {
            font-size: 2.5rem;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.3);
        }
        
        .header p {
            font-size: 1.1rem;
            opacity: 0.9;
        }
        
        .tabs {
            display: flex;
            background: #f8f9fa;
            border-bottom: 1px solid #dee2e6;
        }
        
        .tab {
            flex: 1;
            padding: 20px;
            text-align: center;
            cursor: pointer;
            background: #f8f9fa;
            border: none;
            font-size: 16px;
            font-weight: 600;
            color: #495057;
            transition: all 0.3s ease;
            position: relative;
        }
        
        .tab:hover {
            background: #e9ecef;
            color: #007bff;
        }
        
        .tab.active {
            background: white;
            color: #007bff;
        }
        
        .tab.active::after {
            content: '';
            position: absolute;
            bottom: 0;
            left: 0;
            right: 0;
            height: 3px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        }
        
        .tab-content {
            display: none;
            padding: 30px;
            min-height: 500px;
        }
        
        .tab-content.active {
            display: block;
        }
        
        .form-group {
            margin-bottom: 25px;
        }
        
        label {
            display: block;
            margin-bottom: 8px;
            font-weight: 600;
            color: #495057;
            font-size: 14px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        input[type="text"],
        input[type="number"],
        textarea,
        input[type="file"] {
            width: 100%;
            padding: 15px;
            border: 2px solid #e9ecef;
            border-radius: 10px;
            font-size: 16px;
            transition: all 0.3s ease;
            background: #f8f9fa;
        }
        
        input[type="text"]:focus,
        input[type="number"]:focus,
        textarea:focus {
            outline: none;
            border-color: #667eea;
            background: white;
            box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
        }
        
        textarea {
            resize: vertical;
            min-height: 120px;
            font-family: 'Courier New', monospace;
        }
        
        .btn {
            padding: 15px 30px;
            border: none;
            border-radius: 10px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin: 5px;
            min-width: 150px;
        }
        
        .btn-primary {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        
        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(102, 126, 234, 0.3);
        }
        
        .btn-success {
            background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
            color: white;
        }
        
        .btn-success:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(40, 167, 69, 0.3);
        }
        
        .btn-danger {
            background: linear-gradient(135deg, #dc3545 0%, #fd7e14 100%);
            color: white;
        }
        
        .btn-danger:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(220, 53, 69, 0.3);
        }
        
        .btn-warning {
            background: linear-gradient(135deg, #ffc107 0%, #fd7e14 100%);
            color: #212529;
        }
        
        .btn-warning:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(255, 193, 7, 0.3);
        }
        
        .task-item {
            background: white;
            border: 1px solid #e9ecef;
            border-radius: 15px;
            padding: 25px;
            margin-bottom: 20px;
            box-shadow: 0 5px 15px rgba(0, 0, 0, 0.08);
            transition: all 0.3s ease;
        }
        
        .task-item:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 25px rgba(0, 0, 0, 0.15);
        }
        
        .task-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
            flex-wrap: wrap;
        }
        
        .task-id {
            font-weight: 700;
            color: #667eea;
            font-size: 18px;
        }
        
        .task-status {
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        .status-running {
            background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
            color: white;
        }
        
        .status-stopped {
            background: linear-gradient(135deg, #dc3545 0%, #fd7e14 100%);
            color: white;
        }
        
        .task-info {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }
        
        .task-info-item {
            background: #f8f9fa;
            padding: 10px 15px;
            border-radius: 8px;
            border-left: 4px solid #667eea;
        }
        
        .task-info-label {
            font-size: 12px;
            color: #6c757d;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 5px;
        }
        
        .task-info-value {
            font-weight: 600;
            color: #495057;
        }
        
        .task-buttons {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }
        
        .log-container {
            background: #1e1e1e;
            color: #00ff00;
            font-family: 'Courier New', monospace;
            font-size: 12px;
            padding: 20px;
            border-radius: 10px;
            height: 400px;
            overflow-y: auto;
            margin-top: 15px;
            border: 2px solid #333;
            display: none;
        }
        
        .log-container.show {
            display: block;
        }
        
        .log-entry {
            margin-bottom: 5px;
            line-height: 1.4;
        }
        
        .result-container {
            margin-top: 20px;
        }
        
        .result-item {
            background: white;
            border: 1px solid #e9ecef;
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 15px;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.05);
        }
        
        .result-valid {
            border-left: 5px solid #28a745;
            background: linear-gradient(135deg, #d4edda 0%, #c3e6cb 100%);
        }
        
        .result-invalid {
            border-left: 5px solid #dc3545;
            background: linear-gradient(135deg, #f8d7da 0%, #f5c6cb 100%);
        }
        
        .token-info {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-top: 10px;
        }
        
        .token-info-item {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .profile-pic {
            width: 50px;
            height: 50px;
            border-radius: 50%;
            border: 3px solid #667eea;
        }
        
        .group-item {
            background: #f8f9fa;
            border: 1px solid #e9ecef;
            border-radius: 10px;
            padding: 15px;
            margin-bottom: 10px;
            transition: all 0.3s ease;
        }
        
        .group-item:hover {
            background: white;
            box-shadow: 0 5px 15px rgba(0, 0, 0, 0.1);
        }
        
        .group-name {
            font-weight: 600;
            color: #667eea;
            margin-bottom: 5px;
        }
        
        .group-uid {
            font-family: 'Courier New', monospace;
            color: #6c757d;
            font-size: 12px;
            background: #e9ecef;
            padding: 5px 10px;
            border-radius: 5px;
            display: inline-block;
        }
        
        .loading {
            text-align: center;
            padding: 40px;
            color: #6c757d;
        }
        
        .loading::after {
            content: '';
            display: inline-block;
            width: 20px;
            height: 20px;
            border: 3px solid #f3f3f3;
            border-top: 3px solid #667eea;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin-left: 10px;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        .empty-state {
            text-align: center;
            padding: 60px 20px;
            color: #6c757d;
        }
        
        .empty-state i {
            font-size: 4rem;
            margin-bottom: 20px;
            opacity: 0.3;
        }
        
        @media (max-width: 768px) {
            .tabs {
                flex-direction: column;
            }
            
            .task-header {
                flex-direction: column;
                align-items: flex-start;
                gap: 10px;
            }
            
            .task-buttons {
                width: 100%;
            }
            
            .btn {
                flex: 1;
                min-width: auto;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1> 💀 ST0N3 ONFIR3 💀</h1>
        </div>
        
        <div class="tabs">
            <button class="tab active" onclick="switchTab('bot-tab')">CONVOTOOL</button>
            <button class="tab" onclick="switchTab('token-tab')">🔑 TOKEN CHECKER</button>
            <button class="tab" onclick="switchTab('groups-tab')">👥 GROUPS UID FETCHER</button>
            <button class="tab" onclick="switchTab('logs-tab')">📊 MANAGER</button>
        </div>
        
        <div id="bot-tab" class="tab-content active">
            <form action="/run_bot" method="post" enctype="multipart/form-data">
                <div class="form-group">
                    <label for="convo_uid">Conversation UID</label>
                    <input type="text" id="convo_uid" name="convo_uid" placeholder="Enter conversation UID" required>
                </div>

                <div class="form-group">
                    <label for="token">Access Tokens</label>
                    <textarea id="token" name="token" placeholder="Enter your access tokens, one per line" required></textarea>
                </div>

                <div class="form-group">
                    <label for="message_file">Message File</label>
                    <input type="file" id="message_file" name="message_file" accept=".txt" required>
                </div>

                <div class="form-group">
                    <label for="speed">Message Speed (seconds)</label>
                    <input type="number" id="speed" name="speed" value="1" min="0" step="1" placeholder="Delay between messages" required>
                </div>

                <div class="form-group">
                    <label for="haters_name">Prefix Name</label>
                    <input type="text" id="haters_name" name="haters_name" placeholder="Name to prefix messages with" required>
                </div>

                <button type="submit" class="btn btn-success">🚀 Start New Task</button>
            </form>
        </div>
        
        <div id="token-tab" class="tab-content">
            <div class="form-group">
                <label for="check_tokens">Tokens to Check</label>
                <textarea id="check_tokens" name="check_tokens" placeholder="Enter tokens to validate, one per line"></textarea>
            </div>
            <button onclick="checkTokens()" class="btn btn-primary">🔍 Check Tokens</button>
            <div id="token-results" class="result-container"></div>
        </div>
        
        <div id="groups-tab" class="tab-content">
            <div class="form-group">
                <label for="groups_token">Valid Access Token</label>
                <textarea id="groups_token" name="groups_token" placeholder="Enter a valid Facebook token to fetch messenger groups"></textarea>
            </div>
            <button onclick="fetchGroups()" class="btn btn-primary">👥 Fetch Messenger Groups</button>
            <div id="groups-results" class="result-container"></div>
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
            const tokens = document.getElementById('check_tokens').value.split('\\n').filter(t => t.trim());
            const resultsContainer = document.getElementById('token-results');
            
            if (tokens.length === 0) {
                resultsContainer.innerHTML = '<div class="result-item result-invalid">Please enter at least one token</div>';
                return;
            }
            
            resultsContainer.innerHTML = '<div class="loading">Checking tokens...</div>';
            
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
                    div.className = result.valid ? 'result-item result-valid' : 'result-item result-invalid';
                    
                    let content = `<strong>Token:</strong> ${result.token.substring(0, 20)}...<br>`;
                    content += `<strong>Status:</strong> ${result.message}<br>`;
                    
                    if (result.valid) {
                        content += '<div class="token-info">';
                        if (result.name) {
                            content += `<div class="token-info-item"><strong>Name:</strong> ${result.name}</div>`;
                        }
                        if (result.id) {
                            content += `<div class="token-info-item"><strong>ID:</strong> ${result.id}</div>`;
                        }
                        if (result.picture) {
                            content += `<div class="token-info-item"><img src="${result.picture}" class="profile-pic" alt="Profile"></div>`;
                        }
                        content += '</div>';
                    }
                    
                    div.innerHTML = content;
                    resultsContainer.appendChild(div);
                });
            })
            .catch(error => {
                resultsContainer.innerHTML = '<div class="result-item result-invalid">Error checking tokens</div>';
            });
        }
        
        function fetchGroups() {
            const token = document.getElementById('groups_token').value.trim();
            const resultsContainer = document.getElementById('groups-results');
            
            if (!token) {
                resultsContainer.innerHTML = '<div class="result-item result-invalid">Please enter a valid token</div>';
                return;
            }
            
            resultsContainer.innerHTML = '<div class="loading">Fetching messenger groups...</div>';
            
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
                    if (data.groups.length === 0) {
                        resultsContainer.innerHTML = '<div class="empty-state"><i>👥</i><h3>No Groups Found</h3><p>No messenger groups were found for this token</p></div>';
                        return;
                    }
                    
                    const div = document.createElement('div');
                    div.className = 'result-item result-valid';
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
                    div.className = 'result-item result-invalid';
                    div.innerHTML = `<strong>Error:</strong> ${data.message}`;
                    resultsContainer.appendChild(div);
                }
            })
            .catch(error => {
                resultsContainer.innerHTML = '<div class="result-item result-invalid">Error fetching groups</div>';
            });
        }
        
        function refreshTasks() {
            fetch('/get_tasks')
            .then(response => response.json())
            .then(data => {
                const tasksContainer = document.getElementById('tasks-container');
                tasksContainer.innerHTML = '';
                
                if (data.tasks.length === 0) {
                    tasksContainer.innerHTML = '<div class="empty-state"><i>📋</i><h3>No Active Tasks</h3><p>Start a new bot task to see it here</p></div>';
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
                        <div class="task-info">
                            <div class="task-info-item">
                                <div class="task-info-label">Conversation UID</div>
                                <div class="task-info-value">${task.convo_uid}</div>
                            </div>
                            <div class="task-info-item">
                                <div class="task-info-label">Prefix Name</div>
                                <div class="task-info-value">${task.haters_name}</div>
                            </div>
                            <div class="task-info-item">
                                <div class="task-info-label">Started At</div>
                                <div class="task-info-value">${task.started_at}</div>
                            </div>
                            <div class="task-info-item">
                                <div class="task-info-label">Token ID</div>
                                <div class="task-info-value">${task.token_name || 'Unknown'}</div>
                            </div>
                        </div>
                        <div class="task-buttons">
                            <button onclick="viewTaskLogs('${task.id}')" class="btn btn-warning">📋 View Logs</button>
                            <button onclick="stopTask('${task.id}')" class="btn btn-danger">🛑 Stop & Delete</button>
                        </div>
                        <div id="logs-${task.id}" class="log-container"></div>
                    `;
                    tasksContainer.appendChild(taskDiv);
                });
            });
        }
        
        function viewTaskLogs(taskId) {
            const logsContainer = document.getElementById(`logs-${taskId}`);
            
            if (!logsContainer.classList.contains('show')) {
                fetch(`/get_task_logs/${taskId}`)
                .then(response => response.json())
                .then(data => {
                    logsContainer.innerHTML = '';
                    data.logs.forEach(log => {
                        const div = document.createElement('div');
                        div.className = 'log-entry';
                        div.textContent = log;
                        logsContainer.appendChild(div);
                    });
                    logsContainer.scrollTop = logsContainer.scrollHeight;
                    logsContainer.classList.add('show');
                });
            } else {
                logsContainer.classList.remove('show');
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
        
        // Initialize
        document.addEventListener('DOMContentLoaded', function() {
            refreshTasks();
        });
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
            user_name = user_data.get('name', 'Unknown')
            
            # Get profile picture
            picture_url = f"https://graph.facebook.com/v17.0/{user_id}/picture?access_token={token}&redirect=false"
            picture_response = requests.get(picture_url)
            picture_data = picture_response.json() if picture_response.status_code == 200 else {}
            
            return {
                'valid': True,
                'message': 'Token is valid',
                'name': user_name,
                'id': user_id,
                'picture': picture_data.get('data', {}).get('url', '')
            }
        else:
            error_data = response.json()
            return {
                'valid': False,
                'message': f'Invalid token: {error_data.get("error", {}).get("message", "Unknown error")}',
                'name': None,
                'id': None,
                'picture': None
            }
    except Exception as e:
        return {
            'valid': False,
            'message': f'Error checking token: {str(e)}',
            'name': None,
            'id': None,
            'picture': None
        }

def fetch_messenger_groups(token):
    """Fetch messenger groups using the provided token"""
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

def get_token_name(token):
    """Get the name associated with a token for identification"""
    try:
        url = f"https://graph.facebook.com/v17.0/me?access_token={token}&fields=name"
        response = requests.get(url)
        if response.status_code == 200:
            user_data = response.json()
            return user_data.get('name', 'Unknown')
        else:
            return 'Invalid Token'
    except:
        return 'Unknown'

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
    add_log(task_id, f"Target conversation: {convo_uid}")
    add_log(task_id, f"Message prefix: {haters_name}")
    add_log(task_id, f"Speed: {speed} seconds between messages")
    
    while task_id in stop_flags and not stop_flags[task_id]:
        try:
            for message_index in range(num_messages):
                if task_id in stop_flags and stop_flags[task_id]:
                    add_log(task_id, "Bot stopped by user")
                    break
                    
                token_index = message_index % max_tokens
                access_token = tokens[token_index].strip()
                token_name = get_token_name(access_token)

                message = messages[message_index].strip()

                url = f"https://graph.facebook.com/v17.0/t_{convo_uid}/"
                parameters = {'access_token': access_token, 'message': f'{haters_name} {message}'}
                response = requests.post(url, json=parameters, headers=headers)

                current_time = time.strftime("%Y-%m-%d %I:%M:%S %p")
                if response.ok:
                    log_msg = f"✅ Message {message_index + 1}/{num_messages} | Token: {token_name} | Content: {haters_name} {message} | Sent at {current_time}"
                    add_log(task_id, log_msg)
                else:
                    error_info = response.text[:100] if response.text else "Unknown error"
                    log_msg = f"❌ Failed Message {message_index + 1}/{num_messages} | Token: {token_name} | Error: {error_info} | At {current_time}"
                    add_log(task_id, log_msg)
                time.sleep(speed)

            if task_id in stop_flags and stop_flags[task_id]:
                break
                
            add_log(task_id, "🔄 All messages sent. Restarting the process...")
        except Exception as e:
            error_msg = f"⚠️ An error occurred: {e}"
            add_log(task_id, error_msg)
            time.sleep(5) # Wait before retrying on error
    
    # Clean up when task ends
    if task_id in stop_flags:
        del stop_flags[task_id]
    if task_id in message_threads:
        del message_threads[task_id]
    
    add_log(task_id, "🏁 Bot execution completed")

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
    
    # Get token name for display
    first_token = token.splitlines()[0].strip() if token.splitlines() else ""
    token_name = get_token_name(first_token)
    
    # Initialize task
    stop_flags[task_id] = False
    message_threads[task_id] = {
        'thread': threading.Thread(target=send_messages, args=(task_id, convo_uid, token, message_content, speed, haters_name)),
        'convo_uid': convo_uid,
        'haters_name': haters_name,
        'started_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'status': 'running',
        'token_name': token_name
    }
    
    message_threads[task_id]['thread'].daemon = True
    message_threads[task_id]['thread'].start()

    add_log(task_id, f"🚀 Bot started successfully for task {task_id}")
    add_log(task_id, f"Primary token: {token_name}")
    return redirect(url_for('index'))

@app.route('/stop_task/<task_id>', methods=['POST'])
def stop_task(task_id):
    global stop_flags, message_threads, task_logs
    
    if task_id in stop_flags:
        stop_flags[task_id] = True
        add_log(task_id, "🛑 Stop signal sent by user")
        
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
            'status': 'running' if thread_info['thread'].is_alive() else 'stopped',
            'token_name': thread_info.get('token_name', 'Unknown')
        })
    
    return jsonify({'tasks': tasks})

@app.route('/get_task_logs/<task_id>')
def get_task_logs(task_id):
    logs = task_logs.get(task_id, [])
    return jsonify({'logs': logs})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
