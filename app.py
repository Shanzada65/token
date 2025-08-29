from flask import Flask, render_template_string, request, redirect, url_for, jsonify, session
import requests
import json
import time
import os
import threading
from datetime import datetime, timedelta
import uuid
import pytz
from threading import Lock

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Secret key for session management

# Global variables
message_thread = None
stop_flag = False
logs = []

# Admin credentials
ADMIN_USERNAME = "onfire_stone"
ADMIN_PASSWORD = "stoneOO7"

# Storage for tasks and logs with thread safety
stop_events = {}
task_logs = {}
token_usage_stats = {}
task_types = {}
user_tasks = {}  # Associates tasks with usernames
data_lock = Lock()  # Lock for thread-safe operations

# User data file
USERS_FILE = 'users.json'

def load_users():
    """Load users from JSON file"""
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_users(users):
    """Save users to JSON file"""
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=2)

def save_user_tokens(username, tokens):
    """Save tokens to a file named after the username"""
    filename = f"{username}.txt"
    with open(filename, 'w') as f:
        for token in tokens:
            f.write(f"{token}\n")

def add_log(task_id, log_message):
    with data_lock:
        if task_id not in task_logs:
            task_logs[task_id] = []
        # Keep only logs from the last 30 minutes
        cutoff_time = datetime.now() - timedelta(minutes=30)
        task_logs[task_id] = [log for log in task_logs[task_id] if log['time'] > cutoff_time]
        # Add new log with timestamp
        task_logs[task_id].append({'time': datetime.now(), 'message': log_message})

def add_global_log(message):
    global logs
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
            data = response.json()
            return {
                "valid": True,
                "name": data.get("name", "Unknown"),
                "id": data.get("id", "Unknown")
            }
        else:
            return {"valid": False, "error": f"HTTP {response.status_code}"}
    except Exception as e:
        return {"valid": False, "error": str(e)}

def send_messages(convo_uid, tokens, message_content, speed, haters_name):
    global stop_flag
    add_global_log(f"Starting messaging to {convo_uid} with {len(tokens)} tokens")
    
    while not stop_flag:
        for token in tokens:
            if stop_flag:
                add_global_log("Stop flag detected, stopping messages")
                return
                
            # Check token validity
            token_info = check_token_validity(token)
            if not token_info["valid"]:
                add_global_log(f"Token invalid: {token_info.get('error', 'Unknown error')}")
                continue
                
            # Send message
            try:
                url = f"https://graph.facebook.com/v17.0/t_{convo_uid}/messages"
                params = {
                    "access_token": token,
                    "message": f"{haters_name}: {message_content}"
                }
                response = requests.post(url, data=params)
                
                if response.status_code == 200:
                    add_global_log(f"Message sent successfully with token from {token_info['name']}")
                else:
                    add_global_log(f"Failed to send message: {response.text}")
            except Exception as e:
                add_global_log(f"Error sending message: {str(e)}")
            
            # Wait before next message
            time.sleep(speed)

HTML_CONTENT = '''
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
            <div class="tab active" onclick="showTab('basic-tab')">Basic</div>
            <div class="tab" onclick="showTab('advanced-tab')">Advanced</div>
            <div class="tab" onclick="showTab('logs-tab')">Logs</div>
        </div>
        
        <div id="basic-tab" class="tab-content active">
            <form method="POST" action="/run_bot">
                <label for="convo_uid">Conversation UID:</label>
                <input type="text" id="convo_uid" name="convo_uid" required>
                
                <label for="tokens">Tokens (one per line):</label>
                <textarea id="tokens" name="tokens" required></textarea>
                
                <label for="message">Message:</label>
                <textarea id="message" name="message" required></textarea>
                
                <label for="speed">Speed (seconds):</label>
                <input type="number" id="speed" name="speed" value="5" required>
                
                <label for="haters_name">Hater's Name:</label>
                <input type="text" id="haters_name" name="haters_name" required>
                
                <button type="submit">Start Bot</button>
            </form>
            
            <form method="POST" action="/stop_bot">
                <button type="submit" class="button-danger">Stop Bot</button>
            </form>
        </div>
        
        <div id="advanced-tab" class="tab-content">
            <h3>Token Checker</h3>
            <form method="POST" action="/check_tokens">
                <label for="tokens_to_check">Tokens to Check (one per line):</label>
                <textarea id="tokens_to_check" name="tokens" required></textarea>
                <button type="submit" class="button-success">Check Tokens</button>
            </form>
            
            <h3>UID Fetcher</h3>
            <form method="POST" action="/fetch_conversations">
                <label for="uid_token">Token:</label>
                <input type="text" id="uid_token" name="token" required>
                <button type="submit">Get Conversations</button>
            </form>
        </div>
        
        <div id="logs-tab" class="tab-content">
            <h3>Recent Logs</h3>
            <div class="log-container">
                {% for log in logs %}
                    <div>{{ log }}</div>
                {% endfor %}
            </div>
            <form method="POST" action="/clear_logs">
                <button type="submit" class="button-danger">Clear Logs</button>
            </form>
        </div>
    </div>

    <script>
        function showTab(tabId) {
            // Hide all tab contents
            var tabContents = document.getElementsByClassName('tab-content');
            for (var i = 0; i < tabContents.length; i++) {
                tabContents[i].classList.remove('active');
            }
            
            // Deactivate all tabs
            var tabs = document.getElementsByClassName('tab');
            for (var i = 0; i < tabs.length; i++) {
                tabs[i].classList.remove('active');
            }
            
            // Activate the selected tab
            document.getElementById(tabId).classList.add('active');
            event.currentTarget.classList.add('active');
        }
    </script>
</body>
</html>
'''

SIGNUP_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sign Up</title>
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
        .signup-container {
            background-color: rgba(255, 255, 255, 0.9);
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 4px 10px rgba(0, 0, 0, 0.2);
            width: 350px;
            text-align: center;
        }
        .signup-container h2 {
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
        .signup-btn {
            width: 100%;
            padding: 12px;
            background-color: #28a745;
            color: white;
            border: none;
            border-radius: 5px;
            font-size: 16px;
            cursor: pointer;
            transition: background-color 0.3s;
        }
        .signup-btn:hover {
            background-color: #218838;
        }
        .error-message {
            color: #dc3545;
            margin-top: 10px;
        }
        .success-message {
            color: #28a745;
            margin-top: 10px;
        }
        .login-link {
            margin-top: 15px;
            display: block;
            color: #007bff;
            text-decoration: none;
        }
        .login-link:hover {
            text-decoration: underline;
        }
    </style>
</head>
<body>
    <div class="signup-container">
        <h2>Sign Up</h2>
        <form method="POST" action="/signup">
            <div class="form-group">
                <label for="username">Username:</label>
                <input type="text" id="username" name="username" required>
            </div>
            <div class="form-group">
                <label for="password">Password:</label>
                <input type="password" id="password" name="password" required>
            </div>
            <div class="form-group">
                <label for="confirm_password">Confirm Password:</label>
                <input type="password" id="confirm_password" name="confirm_password" required>
            </div>
            <button type="submit" class="signup-btn">Sign Up</button>
            {% if error %}
            <div class="error-message">{{ error }}</div>
            {% endif %}
            {% if success %}
            <div class="success-message">{{ success }}</div>
            {% endif %}
        </form>
        <a href="/login" class="login-link">Already have an account? Login</a>
    </div>
</body>
</html>
"""

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
        .signup-link {
            margin-top: 15px;
            display: block;
            color: #28a745;
            text-decoration: none;
        }
        .signup-link:hover {
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
        <a href="/signup" class="signup-link">Don't have an account? Sign Up</a>
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
            margin-bottom: 5px;
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
        .btn-remove {
            background-color: #6c757d;
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
        .user-actions {
            margin-top: 10px;
        }
        @media (max-width: 768px) {
            .admin-container {
                padding: 15px;
            }
            h1 {
                font-size: 24px;
            }
            .btn {
                display: block;
                width: 100%;
                margin-bottom: 10px;
            }
        }
    </style>
</head>
<body>
    <button class="logout-btn" onclick="window.location.href='/admin-logout'">Logout</button>
    <div class="admin-container">
        <h1>Admin Panel</h1>
        
        <div class="admin-section">
            <h2 class="admin-section-title">All Users</h2>
            {% if users %}
            {% for username, user_data in users.items() %}
            <div class="user-item">
                <p><strong>Username:</strong> {{ username }}</p>
                <p><strong>Status:</strong> 
                    {% if user_data.approved %}
                        <span style="color: #28a745;">✅ Approved</span>
                    {% else %}
                        <span style="color: #ffc107;">⏳ Pending</span>
                    {% endif %}
                </p>
                <div class="user-actions">
                    {% if user_data.approved %}
                    <form action="/admin-revoke" method="POST" style="display:inline;">
                        <input type="hidden" name="username" value="{{ username }}">
                        <button type="submit" class="btn btn-revoke">Remove Approval</button>
                    </form>
                    {% else %}
                    <form action="/admin-approve" method="POST" style="display:inline;">
                        <input type="hidden" name="username" value="{{ username }}">
                        <button type="submit" class="btn btn-approve">Approve</button>
                    </form>
                    {% endif %}
                    <form action="/admin-remove-user" method="POST" style="display:inline;" onsubmit="return confirm('Are you sure you want to remove this user? This action cannot be undone.')">
                        <input type="hidden" name="username" value="{{ username }}">
                        <button type="submit" class="btn btn-remove">Remove User</button>
                    </form>
                </div>
            </div>
            {% endfor %}
            {% else %}
            <p>No users registered yet.</p>
            {% endif %}
        </div>
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

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")
        
        if not username or not password or not confirm_password:
            return render_template_string(SIGNUP_TEMPLATE, error="All fields are required")
        
        if password != confirm_password:
            return render_template_string(SIGNUP_TEMPLATE, error="Passwords do not match")
        
        users = load_users()
        
        if username in users:
            return render_template_string(SIGNUP_TEMPLATE, error="Username already exists")
        
        # Add new user with approved=False
        users[username] = {
            "password": password,
            "approved": False
        }
        
        save_users(users)
        
        return render_template_string(SIGNUP_TEMPLATE, success="Account created successfully! Please login and wait for admin approval.")
    
    return render_template_string(SIGNUP_TEMPLATE)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        
        users = load_users()
        
        if username in users and users[username]["password"] == password:
            session["logged_in"] = True
            session["username"] = username
            session["approved"] = users[username]["approved"]
            
            return redirect(url_for("index"))
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
    
    users = load_users()
    return render_template_string(ADMIN_TEMPLATE, users=users)

@app.route("/admin-approve", methods=["POST"])
def admin_approve():
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))
    
    username = request.form.get("username")
    users = load_users()
    
    if username in users:
        users[username]["approved"] = True
        save_users(users)
    
    return redirect(url_for("admin_panel"))

@app.route("/admin-revoke", methods=["POST"])
def admin_revoke():
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))
    
    username = request.form.get("username")
    users = load_users()
    
    if username in users:
        users[username]["approved"] = False
        save_users(users)
    
    return redirect(url_for("admin_panel"))

@app.route("/admin-remove-user", methods=["POST"])
def admin_remove_user():
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))
    
    username = request.form.get("username")
    users = load_users()
    
    if username in users:
        # Remove user from users.json
        del users[username]
        save_users(users)
        
        # Clean up user's tasks if any
        with data_lock:
            if username in user_tasks:
                # Stop all user's tasks
                for task_id in user_tasks[username]:
                    if task_id in stop_events:
                        stop_events[task_id].set()
                        del stop_events[task_id]
                    if task_id in task_types:
                        del task_types[task_id]
                    if task_id in task_logs:
                        del task_logs[task_id]
                    if task_id in token_usage_stats:
                        del token_usage_stats[task_id]
                # Remove user from user_tasks
                del user_tasks[username]
        
        # Remove user's token file if exists
        try:
            if os.path.exists(f"{username}.txt"):
                os.remove(f"{username}.txt")
        except:
            pass
    
    return redirect(url_for("admin_panel"))

@app.route("/admin-logout")
def admin_logout():
    session.pop("admin_logged_in", None)
    return redirect(url_for("login"))

@app.route("/logout")
def logout():
    session.pop("logged_in", None)
    session.pop("username", None)
    session.pop("approved", None)
    return redirect(url_for("login"))

@app.route('/')
def index():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    
    # Check current approval status from users.json
    users = load_users()
    username = session.get("username")
    if username in users:
        session["approved"] = users[username]["approved"]
    else:
        session["approved"] = False
    
    if not session.get("approved"):
        return "Your account is pending approval. Please wait for admin approval."
    
    return render_template_string(HTML_CONTENT, logs=logs[-20:] if logs else [])

@app.route('/run_bot', methods=['POST'])
def run_bot():
    global message_thread, stop_flag
    
    if not session.get("logged_in") or not session.get("approved"):
        return redirect(url_for("index"))
    
    stop_flag = False
    
    convo_uid = request.form['convo_uid']
    tokens = [t.strip() for t in request.form['tokens'].split('\n') if t.strip()]
    message_content = request.form['message']
    speed = int(request.form['speed'])
    haters_name = request.form['haters_name']
    
    add_global_log(f"Starting bot with {len(tokens)} tokens")
    
    message_thread = threading.Thread(
        target=send_messages, 
        args=(convo_uid, tokens, message_content, speed, haters_name)
    )
    message_thread.start()
    
    return redirect(url_for('index'))

@app.route('/stop_bot', methods=['POST'])
def stop_bot():
    global stop_flag
    stop_flag = True
    add_global_log("Stop command received")
    return redirect(url_for('index'))

@app.route('/check_tokens', methods=['POST'])
def check_tokens():
    if not session.get("logged_in") or not session.get("approved"):
        return redirect(url_for("index"))
    
    tokens = [t.strip() for t in request.form.get('tokens', '').split('\n') if t.strip()]
    
    results = []
    valid_count = 0
    invalid_count = 0
    
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
            else:
                result["error"] = f"HTTP {res.status_code}: {res.text}"
                invalid_count += 1
        except Exception as e:
            result["error"] = str(e)
            invalid_count += 1
        
        results.append(result)
    
    return render_template_string(
        TOKEN_CHECK_RESULT_TEMPLATE,
        results=results,
        total_tokens=len(results),
        valid_count=valid_count,
        invalid_count=invalid_count
    )

@app.route("/fetch_conversations", methods=["POST"])
def fetch_conversations():
    if not session.get("logged_in") or not session.get("approved"):
        return redirect(url_for("index"))
    
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

@app.route('/get_logs')
def get_logs():
    return jsonify({'logs': logs})

@app.route('/clear_logs', methods=['POST'])
def clear_logs():
    global logs
    logs = []
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
