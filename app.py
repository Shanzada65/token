from flask import Flask, render_template_string, request, redirect, url_for, jsonify, session
import requests
import json
import time
import os
import threading
from datetime import datetime
import uuid
import random
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Configure session
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'stone-rulex-secret-key-2024')
app.config['SESSION_PERMANENT'] = False

# Global session storage - in production, use Redis or database
user_sessions = {}

def get_session_id():
    """Get or create session ID for current user"""
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
    return session['session_id']

def init_user_session(session_id):
    """Initialize user session data if not exists"""
    if session_id not in user_sessions:
        user_sessions[session_id] = {
            'message_threads': {},
            'task_logs': {},
            'stop_flags': {},
            'created_at': datetime.now(),
            'last_activity': datetime.now()
        }
    else:
        user_sessions[session_id]['last_activity'] = datetime.now()

def get_user_data(session_id, data_type):
    """Get user-specific data"""
    init_user_session(session_id)
    return user_sessions[session_id][data_type]

def cleanup_inactive_sessions():
    """Clean up inactive sessions (older than 24 hours)"""
    current_time = datetime.now()
    inactive_sessions = []
    
    for session_id, session_data in user_sessions.items():
        last_activity = session_data.get('last_activity', session_data.get('created_at'))
        if (current_time - last_activity).total_seconds() > 86400:  # 24 hours
            inactive_sessions.append(session_id)
    
    for session_id in inactive_sessions:
        # Stop all threads for this session
        message_threads = user_sessions[session_id]['message_threads']
        stop_flags = user_sessions[session_id]['stop_flags']
        
        for task_id in list(message_threads.keys()):
            if task_id in stop_flags:
                stop_flags[task_id] = True
            thread_info = message_threads[task_id]
            if thread_info['thread'].is_alive():
                thread_info['thread'].join(timeout=1)
        
        del user_sessions[session_id]

html_content = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>STONE RULEX - Session Isolated</title>
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
            position: relative;
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
        
        .session-info {
            position: absolute;
            top: 10px;
            right: 20px;
            background: rgba(255, 255, 255, 0.2);
            padding: 8px 12px;
            border-radius: 15px;
            font-size: 0.8rem;
            backdrop-filter: blur(5px);
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
            grid-template-columns: repeat(auto-fit, minItems(200px, 1fr));
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
        
        .privacy-notice {
            background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%);
            border: 1px solid #2196f3;
            border-radius: 10px;
            padding: 15px;
            margin-bottom: 20px;
            color: #1565c0;
        }
        
        .privacy-notice strong {
            color: #0d47a1;
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
            
            .session-info {
                position: static;
                margin-top: 10px;
                text-align: center;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>STONE RULEX</h1>
            <p>Session Isolated Task Management</p>
            <div class="session-info">
                🔒 Private Session Active
            </div>
        </div>
        
        <div class="privacy-notice">
            <strong>🔐 Privacy Protected:</strong> Your tasks, logs, and data are completely private to your browser session. Other users cannot see or access your information.
        </div>
        
        <div class="tabs">
            <button class="tab active" onclick="switchTab('bot-tab')">CONVO TOOL</button>
            <button class="tab" onclick="switchTab('token-tab')">TOKEN CHECKER</button>
            <button class="tab" onclick="switchTab('groups-tab')">UID FETCHER</button>
            <button class="tab" onclick="switchTab('logs-tab')">TASK MANAGER</button>
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
                    <input type="number" id="speed" name="speed" value="2" min="1" step="1" placeholder="Delay between messages" required>
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
            <button onclick="checkTokens()" class="btn btn-primary">Check Tokens</button>
            <div id="token-results" class="result-container"></div>
        </div>
        
        <div id="groups-tab" class="tab-content">
            <div class="form-group">
                <label for="groups_token">Valid Access Token</label>
                <textarea id="groups_token" name="groups_token" placeholder="Enter a valid Facebook token to fetch messenger groups"></textarea>
            </div>
            <button onclick="fetchGroups()" class="btn btn-primary">Fetch Messenger Groups</button>
            <div id="groups-results" class="result-container"></div>
        </div>
        
        <div id="logs-tab" class="tab-content">
            <div id="tasks-container">
                <!-- Tasks will be loaded here -->
            </div>
        </div>
    </div>

    <script>
        // Global variable to track which log containers are open
        let openLogContainers = new Set();
        
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
                    tasksContainer.innerHTML = '<div class="empty-state"><i>📋</i><h3>No Active Tasks</h3><p>Start a new bot task to see it here. Only your tasks are visible in this session.</p></div>';
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
                        <div id="logs-${task.id}" class="log-container ${openLogContainers.has(task.id) ? 'show' : ''}"></div>
                    `;
                    tasksContainer.appendChild(taskDiv);
                    
                    // If this log container was open before refresh, reload its content
                    if (openLogContainers.has(task.id)) {
                        loadTaskLogs(task.id);
                    }
                });
            });
        }
        
        function loadTaskLogs(taskId) {
            const logsContainer = document.getElementById(`logs-${taskId}`);
            
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
            });
        }
        
        function viewTaskLogs(taskId) {
            const logsContainer = document.getElementById(`logs-${taskId}`);
            
            if (!logsContainer.classList.contains('show')) {
                // Opening logs
                openLogContainers.add(taskId);
                loadTaskLogs(taskId);
                logsContainer.classList.add('show');
            } else {
                // Closing logs
                openLogContainers.delete(taskId);
                logsContainer.classList.remove('show');
            }
        }
        
        function stopTask(taskId) {
            if (confirm('Are you sure you want to stop and delete this task?')) {
                // Remove from open logs tracking when task is stopped
                openLogContainers.delete(taskId);
                
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

def add_log(session_id, task_id, message):
    """Add log entry for specific session and task"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {message}"
    
    task_logs = get_user_data(session_id, 'task_logs')
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

# User agent pool for rotation
USER_AGENTS = [
    'Mozilla/5.0 (Linux; Android 11; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.120 Mobile Safari/537.36',
    'Mozilla/5.0 (Linux; Android 10; SM-A505F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.210 Mobile Safari/537.36',
    'Mozilla/5.0 (Linux; Android 12; Pixel 6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.159 Mobile Safari/537.36',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Mobile/15E148 Safari/604.1'
]

def send_messages(session_id, task_id, convo_uid, tokens, message_content, speed, haters_name):
    """Enhanced message sending with anti-suspension measures"""
    stop_flags = get_user_data(session_id, 'stop_flags')
    
    # Randomize user agent for this session
    user_agent = random.choice(USER_AGENTS)
    
    headers = {
        'Connection': 'keep-alive',
        'Cache-Control': 'max-age=0',
        'Upgrade-Insecure-Requests': '1',
        'User-Agent': user_agent,
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

    add_log(session_id, task_id, f"Starting task with {num_messages} messages and {num_tokens} tokens")
    add_log(session_id, task_id, f"Using User-Agent: {user_agent[:50]}...")
    add_log(session_id, task_id, f"Message speed: {speed} seconds between messages")

    for i in range(num_messages):
        if task_id in stop_flags and stop_flags[task_id]:
            add_log(session_id, task_id, "Task stopped by user")
            break

        message = messages[i].strip()
        if not message:
            continue

        # Use token rotation
        token_index = i % max_tokens
        token = tokens[token_index].strip()
        
        # Add prefix name to message
        full_message = f"{haters_name}: {message}"
        
        add_log(session_id, task_id, f"Sending message {i+1}/{num_messages}: {full_message[:50]}...")

        try:
            # Add randomized delay to make it more human-like
            base_delay = float(speed)
            random_delay = random.uniform(0.5, 1.5)  # Add 0.5-1.5 seconds random delay
            actual_delay = base_delay + random_delay
            
            if i > 0:  # Don't delay before first message
                add_log(session_id, task_id, f"Waiting {actual_delay:.1f} seconds before next message...")
                time.sleep(actual_delay)

            # Check stop flag again after delay
            if task_id in stop_flags and stop_flags[task_id]:
                add_log(session_id, task_id, "Task stopped by user during delay")
                break

            # Send message with retry logic
            max_retries = 3
            retry_count = 0
            success = False
            
            while retry_count < max_retries and not success:
                try:
                    url = f"https://graph.facebook.com/v17.0/{convo_uid}/messages"
                    payload = {
                        'message': full_message,
                        'access_token': token
                    }
                    
                    response = requests.post(url, data=payload, headers=headers, timeout=30)
                    
                    if response.status_code == 200:
                        add_log(session_id, task_id, f"✓ Message {i+1} sent successfully")
                        success = True
                    elif response.status_code == 429:
                        # Rate limited - wait longer
                        wait_time = 60 + random.uniform(10, 30)
                        add_log(session_id, task_id, f"Rate limited. Waiting {wait_time:.1f} seconds...")
                        time.sleep(wait_time)
                        retry_count += 1
                    else:
                        error_data = response.json() if response.content else {}
                        error_message = error_data.get('error', {}).get('message', 'Unknown error')
                        add_log(session_id, task_id, f"✗ Error sending message {i+1}: {error_message}")
                        
                        if 'token' in error_message.lower() or 'permission' in error_message.lower():
                            add_log(session_id, task_id, f"Token issue detected. Skipping to next token...")
                            break
                        
                        retry_count += 1
                        if retry_count < max_retries:
                            wait_time = (2 ** retry_count) + random.uniform(1, 3)
                            add_log(session_id, task_id, f"Retrying in {wait_time:.1f} seconds... (attempt {retry_count + 1}/{max_retries})")
                            time.sleep(wait_time)
                
                except requests.exceptions.RequestException as e:
                    add_log(session_id, task_id, f"Network error: {str(e)}")
                    retry_count += 1
                    if retry_count < max_retries:
                        wait_time = (2 ** retry_count) + random.uniform(1, 3)
                        add_log(session_id, task_id, f"Retrying in {wait_time:.1f} seconds...")
                        time.sleep(wait_time)
            
            if not success:
                add_log(session_id, task_id, f"Failed to send message {i+1} after {max_retries} attempts")

        except Exception as e:
            add_log(session_id, task_id, f"Unexpected error sending message {i+1}: {str(e)}")

    add_log(session_id, task_id, "Task completed")

@app.route('/')
def index():
    session_id = get_session_id()
    init_user_session(session_id)
    return render_template_string(html_content)

@app.route('/run_bot', methods=['POST'])
def run_bot():
    try:
        session_id = get_session_id()
        init_user_session(session_id)
        
        convo_uid = request.form['convo_uid']
        token = request.form['token']
        speed = request.form['speed']
        haters_name = request.form['haters_name']
        
        # Read message file
        message_file = request.files['message_file']
        message_content = message_file.read().decode('utf-8')
        
        # Generate unique task ID
        task_id = str(uuid.uuid4())[:8]
        
        # Get session-specific data
        message_threads = get_user_data(session_id, 'message_threads')
        stop_flags = get_user_data(session_id, 'stop_flags')
        
        # Get token name for identification
        first_token = token.split('\\n')[0].strip()
        token_name = get_token_name(first_token)
        
        # Initialize stop flag
        stop_flags[task_id] = False
        
        # Create and start thread
        thread = threading.Thread(
            target=send_messages,
            args=(session_id, task_id, convo_uid, token, message_content, speed, haters_name)
        )
        thread.daemon = True
        thread.start()
        
        # Store thread info
        message_threads[task_id] = {
            'thread': thread,
            'convo_uid': convo_uid,
            'haters_name': haters_name,
            'started_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'token_name': token_name
        }
        
        add_log(session_id, task_id, f"Task {task_id} started successfully")
        
        return redirect(url_for('index'))
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/stop_task/<task_id>', methods=['POST'])
def stop_task(task_id):
    try:
        session_id = get_session_id()
        
        message_threads = get_user_data(session_id, 'message_threads')
        stop_flags = get_user_data(session_id, 'stop_flags')
        task_logs = get_user_data(session_id, 'task_logs')
        
        # Check if task belongs to this session
        if task_id not in message_threads:
            return jsonify({'success': False, 'error': 'Task not found in your session'})
        
        # Set stop flag
        stop_flags[task_id] = True
        
        # Wait for thread to finish (with timeout)
        thread_info = message_threads[task_id]
        if thread_info['thread'].is_alive():
            thread_info['thread'].join(timeout=5)
        
        # Clean up
        del message_threads[task_id]
        if task_id in stop_flags:
            del stop_flags[task_id]
        if task_id in task_logs:
            del task_logs[task_id]
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/check_tokens', methods=['POST'])
def check_tokens():
    try:
        data = request.get_json()
        tokens = data.get('tokens', [])
        
        results = []
        for token in tokens:
            token = token.strip()
            if token:
                result = check_token_validity(token)
                result['token'] = token
                results.append(result)
        
        return jsonify({'results': results})
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/fetch_groups', methods=['POST'])
def fetch_groups():
    data = request.get_json()
    token = data.get('token', '').strip()
    
    result = fetch_messenger_groups(token)
    return jsonify(result)

@app.route('/get_tasks')
def get_tasks():
    session_id = get_session_id()
    message_threads = get_user_data(session_id, 'message_threads')
    
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
    session_id = get_session_id()
    task_logs = get_user_data(session_id, 'task_logs')
    message_threads = get_user_data(session_id, 'message_threads')
    
    # Check if task belongs to this session
    if task_id not in message_threads and task_id not in task_logs:
        return jsonify({'logs': ['Task not found in your session']})
    
    logs = task_logs.get(task_id, [])
    return jsonify({'logs': logs})

# Cleanup inactive sessions periodically
def cleanup_sessions():
    while True:
        try:
            cleanup_inactive_sessions()
            time.sleep(3600)  # Run every hour
        except Exception as e:
            print(f"Error during session cleanup: {e}")
            time.sleep(3600)

# Start cleanup thread
cleanup_thread = threading.Thread(target=cleanup_sessions)
cleanup_thread.daemon = True
cleanup_thread.start()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
