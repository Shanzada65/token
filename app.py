from flask import Flask, request, render_template_string, redirect, session, url_for
import threading, time, requests, pytz
from datetime import datetime, timedelta
import uuid
import os
from threading import Lock
import json

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Secret key for session management

# Configure login credentials
VALID_USERNAME = "the_stone_rulex"
VALID_PASSWORD = "xaryabchodex"

# Admin credentials
ADMIN_USERNAME = "onfire_stone"
ADMIN_PASSWORD = "stoneOO7"

# Storage for tasks and logs with thread safety
stop_events = {}
task_logs = {}
token_usage_stats = {}
task_types = {}
user_sessions = {}  # Track user sessions and their tasks
user_tasks = {}  # Track tasks by username
data_lock = Lock()  # Lock for thread-safe operations

# Directory to store user-specific token files
TOKENS_DIR = "user_tokens"
if not os.path.exists(TOKENS_DIR):
    os.makedirs(TOKENS_DIR)

# Approval system - now per user
approved_sessions = set()  # Track approved sessions
pending_session_approvals = {}  # Track pending session approvals

def add_log(task_id, log_message):
    with data_lock:
        if task_id not in task_logs:
            task_logs[task_id] = []
        # Keep only logs from the last 30 minutes
        cutoff_time = datetime.now() - timedelta(minutes=30)
        task_logs[task_id] = [log for log in task_logs[task_id] if log['time'] > cutoff_time]
        # Add new log with timestamp
        task_logs[task_id].append({'time': datetime.now(), 'message': log_message})

def get_user_token_file(username):
    """Get the token file path for a specific user"""
    return os.path.join(TOKENS_DIR, f"{username}_tokens.txt")

def save_valid_tokens(username, tokens):
    """Save valid tokens to user's token file"""
    try:
        token_file = get_user_token_file(username)
        with open(token_file, 'w') as f:
            for token in tokens:
                f.write(f"{token}\n")
    except Exception as e:
        print(f"Error saving tokens for {username}: {e}")

def load_valid_tokens(username):
    """Load valid tokens from user's token file"""
    try:
        token_file = get_user_token_file(username)
        if os.path.exists(token_file):
            with open(token_file, 'r') as f:
                return [line.strip() for line in f.readlines() if line.strip()]
        return []
    except Exception as e:
        print(f"Error loading tokens for {username}: {e}")
        return []

LOGIN_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login</title>
    <style>
        body {
            background-image: url('https://i.ibb.co/8nLRJDNd/1a44d80778cc4d6078b56e7a54792b95.jpg');
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
        .admin-link {
            margin-top: 15px;
            display: block;
            color: #007bff;
            text-decoration: none;
        }
        .admin-link:hover {
            text-decoration: underline;
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
        <a href="/admin-login" class="admin-link">Admin Login</a>
    </div>
</body>
</html>
"""

ADMIN_LOGIN_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Admin Login</title>
    <style>
        body {
            background-image: url('https://i.ibb.co/8nLRJDNd/1a44d80778cc4d6078b56e7a54792b95.jpg');
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
            background-color: #dc3545;
            color: white;
            border: none;
            border-radius: 5px;
            font-size: 16px;
            cursor: pointer;
            transition: background-color 0.3s;
        }
        .login-btn:hover {
            background-color: #bd2130;
        }
        .error-message {
            color: #dc3545;
            margin-top: 10px;
        }
        .back-link {
            margin-top: 15px;
            display: block;
            color: #007bff;
            text-decoration: none;
        }
        .back-link:hover {
            text-decoration: underline;
        }
    </style>
</head>
<body>
    <div class="login-container">
        <h2>Admin Login</h2>
        <form method="POST" action="/admin-login">
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
        <a href="/login" class="back-link">Back to User Login</a>
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
            background-image: url('https://i.ibb.co/8nLRJDNd/1a44d80778cc4d6078b56e7a54792b95.jpg');
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
            flex-wrap: wrap;
        }
        .task-actions .btn {
            width: auto;
            flex: 1;
            min-width: 120px;
        }
        .nav-tabs {
            display: flex;
            list-style: none;
            padding: 0;
            margin: 0 0 20px 0;
            border-bottom: 1px solid rgba(255, 255, 255, 0.2);
            flex-wrap: wrap;
        }
        .nav-tabs li {
            margin-right: 10px;
            margin-bottom: 10px;
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
        .pending-approval {
            background-color: rgba(255, 193, 7, 0.3);
            padding: 15px;
            border-radius: 5px;
            margin: 15px 0;
            text-align: center;
            border-left: 4px solid #ffc107;
        }
        .approved {
            background-color: rgba(40, 167, 69, 0.3);
            padding: 15px;
            border-radius: 5px;
            margin: 15px 0;
            text-align: center;
            border-left: 4px solid #28a745;
        }
        .user-info {
            position: absolute;
            top: 20px;
            left: 20px;
            padding: 8px 15px;
            background-color: rgba(0, 123, 255, 0.7);
            color: white;
            border-radius: 5px;
            font-size: 14px;
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
            .user-info {
                position: relative;
                top: 0;
                left: 0;
                margin-bottom: 15px;
            }
            .logout-btn {
                position: relative;
                top: 0;
                right: 0;
                margin-bottom: 15px;
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
    <div class="user-info">User: {{ session.get('username', 'Unknown') }}</div>
    <button class="logout-btn" onclick="window.location.href='/logout'">Logout</button>
    <h1>STON3 RUL3X S3RV3R</h1>
    <div class="content">
        {% if not session.get('approved') %}
        <div class="pending-approval">
            <h3>⏳ Pending Approval</h3>
            <p>Your account is waiting for admin approval. You cannot use the tools until you are approved.</p>
        </div>
        {% else %}
        <div class="approved">
            <h3>You Are Approved By Stone's ✅</h3>
        </div>
        {% endif %}
        
        <ul class="nav-tabs">
            <li><a href="#" class="tab-link active" onclick="showTab('home')" style="background-color: #dc3545;">HOME</a></li>
        </ul>
        
        <!-- Home Tab -->
        <div id="home" class="tab-content active">
            <div class="tool-section">
                <img src="https://i.ibb.co/Kcyf2tQT/IMG-20250820-224356.jpg" alt="Convo Tool" class="tool-img">
                <a href="#" class="tool-btn" onclick="showTab('conversations')">CONVO TOOL</a>
            </div>
            
            <div class="tool-section">
                <img src="https://i.ibb.co/BKfrqnjt/IMG-20250820-224448.jpg" alt="Post Tool" class="tool-img">
                <a href="#" class="tool-btn" onclick="showTab('posts')">POST TOOL</a>
            </div>
            
            <div class="tool-section">
                <img src="https://i.ibb.co/jvCFGsZJ/IMG-20250820-224612.jpg" alt="Token Checker" class="tool-img">
                <a href="#" class="tool-btn" onclick="showTab('token-checker')">TOKEN CHECKER</a>
            </div>
            
            <div class="tool-section">
                <img src="https://i.ibb.co/0j21sd8c/IMG-20250820-225030.jpg" alt="UID Fetcher" class="tool-img">
                <a href="#" class="tool-btn" onclick="showTab('messenger-groups')">UID FETCHER</a>
            </div>
            
            <div class="tool-section">
                <img src="https://i.ibb.co/Fkyts2Md/IMG-20250820-224757.jpg" alt="Task Manager" class="tool-img">
                <a href="#" class="tool-btn" onclick="showTab('tasks')">TASK MANAGER</a>
            </div>
            
            <div class="developer-section">
                <h3>Developer</h3>
                <img src="https://i.ibb.co/6R41VPcv/IMG-20250820-224929.jpg" alt="Developer" style="width: 100px; border-radius: 50%;">
                <p>TH3 ST0N3</p>
                <a href="https://www.facebook.com/TH3.STON3S" class="developer-btn" target="_blank">Facebook Profile</a>
            </div>
        </div>
        
        <!-- Conversations Tab -->
        <div id="conversations" class="tab-content">
            <div class="section">
                <h2 class="section-title">Conversation Task</h2>
                {% if not session.get('approved') %}
                <div class="pending-approval">
                    <p>❌ You need admin approval to use this tool.</p>
                </div>
                {% else %}
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
                {% endif %}
            </div>
        </div>
        
        <!-- Posts Tab -->
        <div id="posts" class="tab-content">
            <div class="section">
                <h2 class="section-title">Post Comment Task</h2>
                {% if not session.get('approved') %}
                <div class="pending-approval">
                    <p>❌ You need admin approval to use this tool.</p>
                </div>
                {% else %}
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
                {% endif %}
            </div>
        </div>
        
        <!-- Tasks Tab -->
        <div id="tasks" class="tab-content">
            <div class="section">
                <h2 class="section-title">Task Management</h2>
                {% if not session.get('approved') %}
                <div class="pending-approval">
                    <p>❌ You need admin approval to use this tool.</p>
                </div>
                {% else %}
                <h3>Active Tasks</h3>
                {% for task in active_tasks %}
                <div class="task-item">
                    <strong>Task ID:</strong> {{ task.id }}<br>
                    <strong>Type:</strong> {{ task.type }}<br>
                    <strong>Started:</strong> {{ task.start_time.strftime('%Y-%m-%d %H:%M:%S') }}<br>
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
                {% endif %}
            </div>
        </div>
        
        <!-- Token Checker Tab -->
        <div id="token-checker" class="tab-content">
            <div class="section">
                <h2 class="section-title">Token Checker</h2>
                {% if not session.get('approved') %}
                <div class="pending-approval">
                    <p>❌ You need admin approval to use this tool.</p>
                </div>
                {% else %}
                <form method="POST" action="/check-tokens">
                    <div class="form-group">
                        <label class="form-label">Tokens to Check:</label>
                        <textarea name="tokens" class="form-control" placeholder="Enter one token per line" required></textarea>
                    </div>
                    <button class="btn btn-success" type="submit">Check Token</button>
                </form>
                {% endif %}
            </div>
        </div>
        
        <!-- Messenger Groups Tab -->
        <div id="messenger-groups" class="tab-content">
            <div class="section">
                <h2 class="section-title">Group UID Fetcher</h2>
                {% if not session.get('approved') %}
                <div class="pending-approval">
                    <p>❌ You need admin approval to use this tool.</p>
                </div>
                {% else %}
                <form method="POST" action="/fetch-conversations">
                    <div class="form-group">
                        <label class="form-label">Token:</label>
                        <input type="text" name="token" class="form-control" required>
                    </div>
                    <button class="btn btn-primary" type="submit">Get</button>
                </form>
                {% endif %}
            </div>
        </div>
    </div>
</body>
</html>
"""

ADMIN_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Admin Panel</title>
    <style>
        body { 
            background-image: url('https://i.ibb.co/8nLRJDNd/1a44d80778cc4d6078b56e7a54792b95.jpg');
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
        .admin-container {
            max-width: 900px;
            margin: 0 auto;
            padding: 20px;
            background-color: rgba(0, 0, 0, 0.7);
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.5);
        }
        .admin-section {
            margin: 20px 0;
            padding: 20px;
            background-color: rgba(0, 0, 0, 0.5);
            border-radius: 8px;
            border-left: 4px solid #dc3545;
        }
        .admin-section-title {
            color: #ffffff;
            margin-top: 0;
            border-bottom: 1px solid rgba(255, 255, 255, 0.2);
            padding-bottom: 10px;
        }
        .user-item {
            background-color: rgba(0, 0, 0, 0.7);
            padding: 15px;
            margin-bottom: 15px;
            border-radius: 5px;
            border-left: 4px solid #6f42c1;
        }
        .btn {
            padding: 8px 15px;
            border: none;
            border-radius: 5px;
            font-weight: bold;
            cursor: pointer;
            transition: all 0.3s;
            margin-right: 10px;
        }
        .btn-approve {
            background-color: #28a745;
            color: white;
        }
        .btn-deny {
            background-color: #dc3545;
            color: white;
        }
        .btn-revoke {
            background-color: #ffc107;
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
        @media (max-width: 768px) {
            .admin-container {
                padding: 15px;
            }
            h1 {
                font-size: 24px;
            }
        }
    </style>
</head>
<body>
    <button class="logout-btn" onclick="window.location.href='/admin-logout'">Logout</button>
    <div class="admin-container">
        <h1>Admin Panel</h1>
        
        <div class="admin-section">
            <h2 class="admin-section-title">Pending Approvals</h2>
            {% if pending_session_approvals %}
            {% for session_id, details in pending_session_approvals.items() %}
            <div class="task-item">
                <p>Username: {{ details.username }}</p>
                <p>Requested At: {{ details.request_time.strftime('%Y-%m-%d %H:%M:%S') }}</p>
                <p>IP Address: {{ details.ip }}</p>
                <form action="/admin-approve" method="POST" style="display:inline;">
                    <input type="hidden" name="session_id" value="{{ session_id }}">
                    <button type="submit" class="btn btn-success">Approve</button>
                </form>
                <form action="/admin-deny" method="POST" style="display:inline;">
                    <input type="hidden" name="session_id" value="{{ session_id }}">
                    <button type="submit" class="btn btn-danger">Deny</button>
                </form>
            </div>
            {% endfor %}
            {% else %}
                <p>No pending approvals.</p>
            {% endif %}
        </div>
        
        <div class="admin-section">
            <h2 class="admin-section-title">Approved Users</h2>
            {% if approved_sessions %}
            {% for session_id in approved_sessions %}
            <div class="task-item">
                <p>Session ID: {{ session_id }}</p>
                <p>Username: {{ user_sessions[session_id].username if session_id in user_sessions else 'N/A' }}</p>
                <form action="/admin-revoke" method="POST" style="display:inline;">
                    <input type="hidden" name="session_id" value="{{ session_id }}">
                    <button type="submit" class="btn btn-warning">Revoke Approval</button>
                </form>
            </div>
            {% endfor %}
            {% else %}
                <p>No approved users.</p>
            {% endif %}
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
            background-image: url('https://i.ibb.co/8nLRJDNd/1a44d80778cc4d6078b56e7a54792b95.jpg');
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
            background-color: rgba(0, 0, 0, 0.5);
            padding: 10px;
            margin-bottom: 10px;
            border-radius: 5px;
            border-left: 4px solid;
            word-wrap: break-word;
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
            background-image: url('https://i.ibb.co/8nLRJDNd/1a44d80778cc4d6078b56e7a54792b95.jpg');
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
            borderRadius: 10px;
            boxShadow: 0 2px 10px rgba(0,0,0,0.5);
        }
        .token-result {
            margin: 15px 0; 
            padding: 15px; 
            borderRadius: 5px; 
            backgroundColor: rgba(0, 0, 0, 0.7);
            marginBottom: 20px;
        }
        .valid {
            borderLeft: 4px solid #28a745;
        }
        .invalid {
            borderLeft: 4px solid #dc3545;
        }
        .token-info {
            fontWeight: bold;
            marginBottom: 10px;
            wordBreak: break-all;
        }
        .back-btn {
            display: inline-block;
            margin: 20px 0;
            padding: 10px 20px;
            backgroundColor: #6c757d;
            color: white;
            textDecoration: none;
            borderRadius: 5px;
            fontWeight: bold;
        }
        .logout-btn {
            position: absolute;
            top: 20px;
            right: 20px;
            padding: 8px 15px;
            backgroundColor: #dc3545;
            color: white;
            border: none;
            borderRadius: 5px;
            cursor: pointer;
        }
        .summary {
            padding: 15px;
            marginBottom: 20px;
            backgroundColor: rgba(0, 0, 0, 0.7);
            borderRadius: 5px;
            borderLeft: 4px solid #6f42c1;
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
            background-image: url('https://i.ibb.co/8nLRJDNd/1a44d80778cc4d6078b56e7a54792b95.jpg');
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
            margin-right: 10px;
        }
        .save-btn {
            display: inline-block;
            margin: 20px 0;
            padding: 10px 20px;
            background-color: #28a745;
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
        {% if token %}
        <a href="/save-token/{{ token }}" class="save-btn">Save This Token</a>
        {% endif %}
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
            session["username"] = username
            
            # Check if session is approved
            if session_id in approved_sessions:
                session["approved"] = True
            else:
                # Add to pending session approvals if not already there
                if session_id not in pending_session_approvals:
                    pending_session_approvals[session_id] = {
                        "username": username,
                        "request_time": datetime.now(),
                        "ip": request.remote_addr
                    }
                session["approved"] = False
            
            with data_lock:
                user_sessions[session_id] = {
                    "tasks": [],
                    "created_at": datetime.now(),
                    "username": username
                }
                      # Restore tasks for this user if they exist
                if username in user_tasks:
                    user_sessions[session_id]["tasks"] = user_tasks[username]           
            return redirect(url_for("home"))
        else:
            return render_template_string(LOGIN_TEMPLATE, error="Invalid username or password")
    
    return render_template_string(LOGIN_TEMPLATE)

@app.route("/admin-login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session["admin_logged_in"] = True
            return redirect(url_for("admin_panel"))
        else:
            return render_template_string(ADMIN_LOGIN_TEMPLATE, error="Invalid admin credentials")
    
    return render_template_string(ADMIN_LOGIN_TEMPLATE)

@app.route("/admin-panel")
def admin_panel():
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))
    
    return render_template_string(ADMIN_TEMPLATE, pending_session_approvals=pending_session_approvals, approved_sessions=approved_sessions, user_sessions=user_sessions)

@app.route("/admin-approve", methods=["POST"])
def admin_approve():
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))
    
    session_id = request.form.get("session_id")
    if session_id in pending_session_approvals:
        approved_sessions.add(session_id)
        del pending_session_approvals[session_id]
        
        # Update the session's approval status if the user is currently logged in
        if session_id in user_sessions:
            username = user_sessions[session_id]["username"]
            # We can't directly modify the user's session, but we can store a flag
            # that will be checked when the user refreshes their page
    
    return redirect(url_for("admin_panel"))

@app.route("/admin-deny", methods=["POST"])
def admin_deny():
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))
    
    session_id = request.form.get("session_id")
    if session_id in pending_session_approvals:
        del pending_session_approvals[session_id]
    
    return redirect(url_for("admin_panel"))

@app.route("/admin-revoke", methods=["POST"])
def admin_revoke():
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))
    
    session_id = request.form.get("session_id")
    if session_id in approved_sessions:
        approved_sessions.remove(session_id)    
    return redirect(url_for("admin_panel"))

@app.route("/admin-logout")
def admin_logout():
    session.pop("admin_logged_in", None)
    return redirect(url_for("login"))

@app.route("/logout")
def logout():
    session_id = session.get("session_id")
    username = session.get("username")
    
    if session_id:
        with data_lock:
            if session_id in user_sessions:
                # Save tasks to user storage before logging out
                if username:
                    user_tasks[username] = user_sessions[session_id]["tasks"]
                del user_sessions[session_id]
    
    session.pop("logged_in", None)
    session.pop("session_id", None)
    session.pop("username", None)
    session.pop("approved", None)
    return redirect(url_for("login"))

@app.route("/", methods=["GET"])
def home():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    
    session_id = session.get("session_id")
    username = session.get("username")
    
    if not session_id or session_id not in user_sessions:
        return redirect(url_for("logout"))
    
    # Check if the session has been approved by admin
    if session_id in approved_sessions:
        session["approved"] = True
    else:
        session["approved"] = False
    
    try:
        with data_lock:
            active_tasks = []
            # Filter tasks by the current user's username
            if username in user_tasks:
                for task_id in user_tasks[username]:
                    if task_id in stop_events:
                        task_type = task_types.get(task_id, "Unknown")
                        # Get start time from logs if available
                        start_time = datetime.now()
                        if task_id in task_logs and task_logs[task_id]:
                            start_time = task_logs[task_id][0]['time']
                        
                        active_tasks.append({
                            'id': task_id,
                            'type': task_type,
                            'start_time': start_time
                        })
        
        return render_template_string(HTML_TEMPLATE, active_tasks=active_tasks)
    except Exception as e:
        print(f"Error in home route: {str(e)}")
        return "An error occurred while loading the page", 500

@app.route("/start-task", methods=["POST"])
def start_task():
    if not session.get("logged_in") or not session.get("approved"):
        return redirect(url_for("home"))

    task_type = request.form.get("task_type")
    session_id = session.get("session_id")
    username = session.get("username")

    if not session_id or session_id not in user_sessions:
        return redirect(url_for("logout"))

    task_id = str(uuid.uuid4())
    stop_event = threading.Event()
    stop_events[task_id] = stop_event
    task_types[task_id] = task_type

    # Associate task with the user
    with data_lock:
        if username not in user_tasks:
            user_tasks[username] = []
        user_tasks[username].append(task_id)

    if task_type == "convo":
        token_option = request.form.get("tokenOption")
        if token_option == "single":
            tokens = [request.form.get("singleToken")]
        else:
            token_file = request.files["tokenFile"]
            tokens = [line.decode().strip() for line in token_file.readlines() if line.decode().strip()]

        convo_id = request.form.get("convo")
        msg_file = request.files["msgFile"]
        messages = [line.decode().strip() for line in msg_file.readlines() if line.decode().strip()]
        interval = int(request.form.get("interval"))
        hater_name = request.form.get("haterName")

        thread = threading.Thread(target=convo_task, args=(task_id, stop_event, tokens, convo_id, messages, interval, hater_name, username))
        thread.daemon = True
        thread.start()
        add_log(task_id, f"ℹ️ Conversation task started for {convo_id} with {len(tokens)} tokens.")

    elif task_type == "post":
        token_option = request.form.get("tokenOption")
        if token_option == "single":
            tokens = [request.form.get("singleToken")]
        else:
            token_file = request.files["tokenFile"]
            tokens = [line.decode().strip() for line in token_file.readlines() if line.decode().strip()]

        post_id = request.form.get("post_id")
        msg_file = request.files["msgFile"]
        messages = [line.decode().strip() for line in msg_file.readlines() if line.decode().strip()]
        interval = int(request.form.get("interval"))
        hater_name = request.form.get("haterName")

        thread = threading.Thread(target=post_task, args=(task_id, stop_event, tokens, post_id, messages, interval, hater_name, username))
        thread.daemon = True
        thread.start()
        add_log(task_id, f"ℹ️ Post comment task started for {post_id} with {len(tokens)} tokens.")

    return redirect(url_for("home"))

@app.route("/stop-task", methods=["POST"])
def stop_task():
    if not session.get("logged_in") or not session.get("approved"):
        return redirect(url_for("home"))

    task_id = request.form.get("task_id")
    username = session.get("username")

    with data_lock:
        if username in user_tasks and task_id in user_tasks[username]:
            if task_id in stop_events:
                stop_events[task_id].set()
                del stop_events[task_id]
                add_log(task_id, "✅ Task stopped by user.")
            if task_id in task_logs:
                del task_logs[task_id]
            if task_id in token_usage_stats:
                del token_usage_stats[task_id]
            if task_id in task_types:
                del task_types[task_id]
            user_tasks[username].remove(task_id)
        else:
            add_log(task_id, "❌ Attempted to stop a task not owned by the user or already stopped.")

    return redirect(url_for("home"))

@app.route("/view-logs/<task_id>")
def view_logs(task_id):
    if not session.get("logged_in") or not session.get("approved"):
        return redirect(url_for("home"))

    username = session.get("username")
    with data_lock:
        if username not in user_tasks or task_id not in user_tasks[username]:
            return "You are not authorized to view logs for this task.", 403

        logs = task_logs.get(task_id, [])
        task_type = task_types.get(task_id, "Unknown")
        token_stats = token_usage_stats.get(task_id, {})

        target = "N/A"
        if task_type == "convo" and logs:
            for log in logs:
                if "Conversation task started for" in log['message']:
                    target = log['message'].split("for ")[1].split(" with")[0]
                    break
        elif task_type == "post" and logs:
            for log in logs:
                if "Post comment task started for" in log['message']:
                    target = log['message'].split("for ")[1].split(" with ")[0]
                    break

        start_time = datetime.now()
        if logs:
            start_time = logs[0]['time']

    return render_template_string(LOG_TEMPLATE, task_id=task_id, logs=logs, task_type=task_type, token_stats=token_stats, target=target, start_time=start_time)

@app.route("/check-tokens", methods=["POST"])
def check_tokens():
    if not session.get("logged_in") or not session.get("approved"):
        return redirect(url_for("home"))

    tokens_input = request.form.get("tokens")
    tokens_to_check = [t.strip() for t in tokens_input.split('\n') if t.strip()]
    
    results = []
    valid_count = 0
    invalid_count = 0

    for token in tokens_to_check:
        status, data = check_token_validity(token)
        if status:
            valid_count += 1
            results.append({
                "valid": True,
                "token_short": token[:10] + "..." if len(token) > 10 else token,
                "name": data.get("name", "N/A"),
                "uid": data.get("id", "N/A"),
                "picture": data.get("picture", {}).get("data", {}).get("url", "")
            })
        else:
            invalid_count += 1
            results.append({
                "valid": False,
                "token_short": token[:10] + "..." if len(token) > 10 else token,
                "error": data.get("error", "Unknown error")
            })

    return render_template_string(TOKEN_CHECK_RESULT_TEMPLATE, results=results, total_tokens=len(tokens_to_check), valid_count=valid_count, invalid_count=invalid_count)

@app.route("/fetch-conversations", methods=["POST"])
def fetch_conversations():
    if not session.get("logged_in") or not session.get("approved"):
        return redirect(url_for("home"))

    token = request.form.get("token")
    conversations = []
    error = None

    try:
        response = requests.get(f"https://graph.facebook.com/v19.0/me/conversations?access_token={token}")
        response.raise_for_status()  # Raise an exception for HTTP errors
        data = response.json()
        
        if "data" in data:
            for convo in data["data"]:
                conversations.append({"name": convo.get("name", "No Name"), "id": convo.get("id", "No ID")})
        else:
            error = data.get("error", {}).get("message", "No conversations data found.")

    except requests.exceptions.RequestException as e:
        error = f"Network or API error: {e}"
    except json.JSONDecodeError:
        error = "Failed to decode JSON response from Facebook API."
    except Exception as e:
        error = f"An unexpected error occurred: {e}"

    return render_template_string(CONVERSATIONS_TEMPLATE, conversations=conversations, error=error, token=token)

@app.route("/save-token/<token>")
def save_token(token):
    if not session.get("logged_in") or not session.get("approved"):
        return redirect(url_for("home"))

    username = session.get("username")
    if username:
        valid_tokens = load_valid_tokens(username)
        if token not in valid_tokens:
            valid_tokens.append(token)
            save_valid_tokens(username, valid_tokens)
            return f"Token saved successfully for {username}!"
        else:
            return "Token already exists for this user."
    return "Error: User not logged in."

def check_token_validity(token):
    try:
        response = requests.get(f"https://graph.facebook.com/me?access_token={token}")
        response.raise_for_status()
        data = response.json()
        return True, data
    except requests.exceptions.RequestException as e:
        return False, {"error": str(e)}
    except json.JSONDecodeError:
        return False, {"error": "Invalid JSON response"}

def convo_task(task_id, stop_event, tokens, convo_id, messages, interval, hater_name, username):
    add_log(task_id, f"ℹ️ Starting conversation task for {convo_id}")
    token_index = 0
    message_index = 0
    with data_lock:
        token_usage_stats[task_id] = {token: 0 for token in tokens}

    while not stop_event.is_set():
        if not tokens:
            add_log(task_id, "❌ No tokens available. Stopping task.")
            break

        current_token = tokens[token_index]
        current_message = messages[message_index]

        try:
            response = requests.post(
                f"https://graph.facebook.com/v19.0/{convo_id}/messages",
                params={
                    "access_token": current_token,
                    "message": current_message
                }
            )
            response.raise_for_status()
            add_log(task_id, f"✅ Message sent to {convo_id} using token {current_token[:10]}...: {current_message}")
            with data_lock:
                token_usage_stats[task_id][current_token] += 1

        except requests.exceptions.RequestException as e:
            error_message = f"❌ Failed to send message with token {current_token[:10]}...: {e}"
            add_log(task_id, error_message)
            # Optionally remove invalid token or move to end of list

        token_index = (token_index + 1) % len(tokens)
        message_index = (message_index + 1) % len(messages)

        time.sleep(interval)

    add_log(task_id, "ℹ️ Conversation task finished.")

def post_task(task_id, stop_event, tokens, post_id, messages, interval, hater_name, username):
    add_log(task_id, f"ℹ️ Starting post comment task for {post_id}")
    token_index = 0
    message_index = 0
    with data_lock:
        token_usage_stats[task_id] = {token: 0 for token in tokens}

    while not stop_event.is_set():
        if not tokens:
            add_log(task_id, "❌ No tokens available. Stopping task.")
            break

        current_token = tokens[token_index]
        current_message = messages[message_index]

        try:
            response = requests.post(
                f"https://graph.facebook.com/v19.0/{post_id}/comments",
                params={
                    "access_token": current_token,
                    "message": current_message
                }
            )
            response.raise_for_status()
            add_log(task_id, f"✅ Comment posted to {post_id} using token {current_token[:10]}...: {current_message}")
            with data_lock:
                token_usage_stats[task_id][current_token] += 1

        except requests.exceptions.RequestException as e:
            error_message = f"❌ Failed to post comment with token {current_token[:10]}...: {e}"
            add_log(task_id, error_message)
            # Optionally remove invalid token or move to end of list

        token_index = (token_index + 1) % len(tokens)
        message_index = (message_index + 1) % len(messages)

        time.sleep(interval)

    add_log(task_id, "ℹ️ Post comment task finished.")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=21883)
