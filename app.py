from flask import Flask, request, render_template_string, redirect, session, url_for
import threading, time, requests, pytz
from datetime import datetime, timedelta
import uuid
import os
import json
from threading import Lock
from typing import List, Dict, Any
import random

app = Flask(__name__)
app.secret_key = os.environ.get('SESSION_SECRET', os.urandom(24))

ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'thewstones57@gmail.com')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', '@#(SH9N)#@')

stop_events = {}
task_logs = {}
token_usage_stats = {}
task_types = {}
user_tasks = {}
data_lock = Lock()

user_day_tokens = {}
user_night_tokens = {}
token_rotation_start_time = {}

USERS_FILE = 'users.json'

def load_users():
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_users(users):
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=2)

def save_user_tokens(username, tokens):
    filename = f"{username}.txt"
    with open(filename, 'w') as f:
        for token in tokens:
            f.write(f"{token}\n")

def save_user_day_tokens(username, tokens):
    filename = f"{username}_day.txt"
    with open(filename, 'w') as f:
        for token in tokens:
            f.write(f"{token}\n")

def save_user_night_tokens(username, tokens):
    filename = f"{username}_night.txt"
    with open(filename, 'w') as f:
        for token in tokens:
            f.write(f"{token}\n")

def load_user_tokens(username):
    filename = f"{username}.txt"
    if os.path.exists(filename):
        try:
            with open(filename, 'r') as f:
                return [line.strip() for line in f.readlines() if line.strip()]
        except:
            return []
    return []

def load_user_day_tokens(username):
    filename = f"{username}_day.txt"
    if os.path.exists(filename):
        try:
            with open(filename, 'r') as f:
                return [line.strip() for line in f.readlines() if line.strip()]
        except:
            return []
    return []

def load_user_night_tokens(username):
    filename = f"{username}_night.txt"
    if os.path.exists(filename):
        try:
            with open(filename, 'r') as f:
                return [line.strip() for line in f.readlines() if line.strip()]
        except:
            return []
    return []

def load_user_all_tokens(username):
    all_tokens = []
    
    filename = f"{username}.txt"
    if os.path.exists(filename):
        try:
            with open(filename, 'r') as f:
                all_tokens.extend([line.strip() for line in f.readlines() if line.strip()])
        except:
            pass
    
    day_filename = f"{username}_day.txt"
    if os.path.exists(day_filename):
        try:
            with open(day_filename, 'r') as f:
                all_tokens.extend([line.strip() for line in f.readlines() if line.strip()])
        except:
            pass
    
    night_filename = f"{username}_night.txt"
    if os.path.exists(night_filename):
        try:
            with open(night_filename, 'r') as f:
                all_tokens.extend([line.strip() for line in f.readlines() if line.strip()])
        except:
            pass
    
    seen = set()
    unique_tokens = []
    for token in all_tokens:
        if token not in seen:
            seen.add(token)
            unique_tokens.append(token)
    
    return unique_tokens

def get_current_token_set(username):
    current_time = datetime.now()
    
    if username not in token_rotation_start_time:
        token_rotation_start_time[username] = current_time
        return user_day_tokens.get(username, [])
    
    start_time = token_rotation_start_time[username]
    elapsed_hours = (current_time - start_time).total_seconds() / 3600
    
    cycle_position = int(elapsed_hours // 6) % 2
    
    if cycle_position == 0:
        return user_day_tokens.get(username, [])
    else:
        return user_night_tokens.get(username, [])

def add_log(task_id, log_message):
    with data_lock:
        if task_id not in task_logs:
            task_logs[task_id] = []
        cutoff_time = datetime.now() - timedelta(minutes=30)
        # Filter out old logs and append new one
        task_logs[task_id] = [log for log in task_logs[task_id] if log['time'] > cutoff_time]
        task_logs[task_id].append({'time': datetime.now(), 'message': log_message})

PAGE_TOKEN_BASE_URL = "https://graph.facebook.com/v17.0/me/accounts"
PAGE_TOKEN_FIELDS = "name,id,access_token"

def mask_token(t: str) -> str:
    if not t:
        return "<empty>"
    if len(t) <= 12:
        return t[0:3] + "..." + t[-3:]
    return t[:6] + "..." + t[-6:]

def fetch_pages(user_token: str) -> List[Dict[str, Any]]:
    params = {"fields": PAGE_TOKEN_FIELDS, "access_token": user_token}
    url = PAGE_TOKEN_BASE_URL
    pages: List[Dict[str, Any]] = []
    while url:
        try:
            resp = requests.get(url, params=params if url == PAGE_TOKEN_BASE_URL else None, timeout=15)
        except requests.RequestException:
            return pages

        if resp.status_code != 200:
            return pages

        try:
            data = resp.json()
        except ValueError:
            return pages

        if "data" in data:
            pages.extend(data["data"])
        else:
            break

        paging = data.get("paging", {})
        url = paging.get("next")
        if url:
            time.sleep(0.2)

    return pages

def process_token_for_web(user_token: str) -> str:
    if not user_token:
        return "<p class='error'>Error: No token provided.</p>"

    pages = fetch_pages(user_token)
    
    output_html = f"<h2>Results for Token: <code>{mask_token(user_token)}</code></h2>"

    if not pages:
        output_html += "<p class='error'>No pages found or an error occurred during fetching. Check the token and try again.</p>"
        return output_html

    output_html += f"<p class='success'>âœ” Found {len(pages)} page(s).</p>"
    output_html += "<div class='page-list'>"
    
    for i, p in enumerate(pages, start=1):
        name = p.get("name", "<no-name>")
        page_id = p.get("id", "<no-id>")
        page_token = p.get("access_token", "<no-access_token>")
        
        output_html += f"""
        <div class='page-card'>
            <h3>Page #{i}</h3>
            <p><strong>Name:</strong> {name}</p>
            <p><strong>ID:</strong> {page_id}</p>
            <p><strong>Page Token:</strong> <code class='token'>{page_token}</code></p>
        </div>
        """
        
    output_html += "</div>"
    return output_html

PAGE_TOKEN_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Facebook Pages Token Extractor</title>
    <style>
        .token-detail {
            margin-bottom: 10px;
        }
        .token-detail p {
            margin: 5px 0;
        }
        .token-detail code {
            background-color: rgba(255, 255, 255, 0.1);
            padding: 2px 4px;
            border-radius: 3px;
        }
        body {
            background-image: url('https://i.ibb.co/gM0phW6S/1614b9d2afdbe2d3a184f109085c488f.jpg');
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
            color: #ffffff; 
            font-family: 'Roboto', sans-serif; 
            padding: 20px;
            margin: 0;
        }
        .container {
            max-width: 800px;
            margin: auto;
            background-color: rgba(0, 0, 0, 0.7);
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 4px 8px rgba(0,0,0,0.5);
        }
        h1 {
            color: #ffffff;
            border-bottom: 2px solid rgba(255, 255, 255, 0.2);
            padding-bottom: 10px;
        }
        h2 {
            color: #ffffff;
        }
        p {
            color: #ccc;
        }
        form {
            background: rgba(255, 255, 255, 0.1);
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 20px;
            border: 1px solid rgba(255, 255, 255, 0.2);
        }
        input[type="text"] {
            width: 100%;
            padding: 10px;
            margin: 8px 0;
            display: inline-block;
            border: 1px solid #ccc;
            border-radius: 4px;
            box-sizing: border-box;
            background-color: rgba(255, 255, 255, 0.9);
            color: #333;
        }
        input[type="submit"] {
            background-color: #007bff;
            color: white;
            padding: 10px 15px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 16px;
            transition: background-color 0.3s;
        }
        input[type="submit"]:hover {
            background-color: #0056b3;
        }
        .page-list {
            margin-top: 20px;
        }
        .page-card {
            background-color: rgba(255, 255, 255, 0.1);
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 10px;
            border-left: 5px solid #28a745;
        }
        .page-card h3 {
            margin-top: 0;
            color: #28a745;
        }
        .page-card p {
            margin: 5px 0;
            word-wrap: break-word;
        }
        .page-card code.token {
            display: block;
            padding: 5px;
            background-color: rgba(0, 0, 0, 0.5);
            color: #ffc107;
            border-radius: 3px;
            font-size: 0.9em;
        }
        .error {
            color: #dc3545;
            font-weight: bold;
        }
        .success {
            color: #28a745;
            font-weight: bold;
        }
        .back-btn {
            display: inline-block;
            margin-top: 20px;
            padding: 10px 20px;
            background-color: #dc3545;
            color: white;
            text-decoration: none;
            border-radius: 5px;
            font-weight: bold;
        }
        .back-btn:hover {
            background-color: #c82333;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Facebook Pages Token Extractor</h1>
        <form method="post">
            <label for="token">Enter User Access Token:</label>
            <input type="text" id="token" name="token" required>
            <input type="submit" value="Extract Page Tokens">
        </form>
        {{ results | safe }}
        <a href="/" class="back-btn">Back to Main</a>
    </div>
</body>
</html>
"""

@app.route("/page-token-extractor", methods=["GET", "POST"])
def page_token_extractor():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    
    results = ""
    if request.method == "POST":
        user_token = request.form.get("token")
        results = process_token_for_web(user_token)
        
    return render_template_string(PAGE_TOKEN_TEMPLATE, results=results)

# --- TOKEN CHECKER TEMPLATE (MODIFIED) ---
TOKEN_CHECKER_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Token Checker</title>
    <style>
        body {
            background-image: url('https://i.ibb.co/gM0phW6S/1614b9d2afdbe2d3a184f109085c488f.jpg');
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
            color: #ffffff;
            font-family: 'Roboto', sans-serif;
            padding: 20px;
            margin: 0;
        }
        .container {
            max-width: 900px;
            margin: auto;
            background-color: rgba(0, 0, 0, 0.7);
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 4px 8px rgba(0,0,0,0.5);
        }
        h1 {
            color: #ffffff;
            border-bottom: 2px solid rgba(255, 255, 255, 0.2);
            padding-bottom: 10px;
        }
        .form-group {
            margin-bottom: 15px;
        }
        .form-label {
            display: block;
            margin-bottom: 5px;
            font-weight: bold;
            color: #ffffff;
        }
        .form-control {
            width: 100%;
            padding: 10px;
            border: 1px solid rgba(255, 255, 255, 0.3);
            border-radius: 5px;
            background-color: rgba(255, 255, 255, 0.9);
            color: #333;
            font-size: 14px;
        }
        .btn-primary {
            background-color: #007bff;
            color: white;
            padding: 10px 15px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 16px;
            transition: background-color 0.3s;
        }
        .btn-primary:hover {
            background-color: #0056b3;
        }
        .results-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }
        .results-table th, .results-table td {
            border: 1px solid rgba(255, 255, 255, 0.2);
            padding: 10px;
            text-align: left;
            word-break: break-all;
        }
        .results-table th {
            background-color: rgba(255, 255, 255, 0.1);
            color: #ffc107;
        }
        .results-table tr:nth-child(even) {
            background-color: rgba(255, 255, 255, 0.05);
        }
        .valid-token {
            color: #28a745;
            font-weight: bold;
        }
        .invalid-token {
            color: #dc3545;
            font-weight: bold;
        }
        .back-btn {
            display: inline-block;
            margin-top: 20px;
            padding: 10px 20px;
            background-color: #dc3545;
            color: white;
            text-decoration: none;
            border-radius: 5px;
            font-weight: bold;
        }
        .back-btn:hover {
            background-color: #c82333;
        }
        .profile-pic {
            width: 50px;
            height: 50px;
            border-radius: 50%;
            object-fit: cover;
        }
        .error {
            color: #dc3545;
            font-weight: bold;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Token Checker</h1>
        
        {% if error %}
            <p class="error">âŒ {{ error }}</p>
        {% endif %}

        <form method="post" enctype="multipart/form-data">
            <div class="form-group">
                <label for="tokenFile" class="form-label">Upload Token File (Line by Line Input):</label>
                <input type="file" id="tokenFile" name="tokenFile" class="form-control" accept=".txt" required>
            </div>
            <button type="submit" class="btn-primary">Check Tokens</button>
        </form>

        {% if results %}
            <h2>Check Results ({{ results|length }} Tokens)</h2>
            <table class="results-table">
                <thead>
                    <tr>
                        <th>#</th>
                        <th>Token (Masked)</th>
                        <th>Status</th>
                        <th>User ID</th>
                        <th>User Name</th>
                        <th>Profile</th>
                    </tr>
                </thead>
                <tbody>
                    {% for result in results %}
                    <tr>
                        <td>{{ loop.index }}</td>
                        <td><code>{{ result.token[:6] }}...{{ result.token[-6:] }}</code></td>
                        <td class="{{ 'valid-token' if result.valid else 'invalid-token' }}">
                            {{ 'âœ… Valid' if result.valid else 'âŒ Invalid' }}
                        </td>
                        <td>{{ result.user_id if result.user_id else 'N/A' }}</td>
                        <td>{{ result.user_name if result.user_name else 'N/A' }}</td>
                        <td>
                            {% if result.profile_pic %}
                                <img src="{{ result.profile_pic }}" class="profile-pic" alt="Profile Picture">
                            {% else %}
                                N/A
                            {% endif %}
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        {% endif %}
        
        <a href="/" class="back-btn">Back to Main</a>
    </div>
</body>
</html>
"""
# --- END TOKEN CHECKER TEMPLATE ---

# --- UID FETCHER TEMPLATE (Original) ---
UID_FETCHER_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>UID Fetcher Results</title>
    <style>
        body {
            background-image: url('https://i.ibb.co/gM0phW6S/1614b9d2afdbe2d3a184f109085c488f.jpg');
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
            color: #ffffff;
            font-family: 'Roboto', sans-serif;
            padding: 20px;
            margin: 0;
        }
        .result-container {
            max-width: 900px;
            margin: 0 auto;
            padding: 20px;
            background-color: rgba(0, 0, 0, 0.7);
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.5);
        }
        h1 {
            color: #ffffff;
            border-bottom: 2px solid rgba(255, 255, 255, 0.2);
            padding-bottom: 10px;
        }
        .uid-list textarea {
            width: 100%;
            height: 300px;
            background-color: rgba(255, 255, 255, 0.1);
            color: #ffffff;
            border: 1px solid rgba(255, 255, 255, 0.3);
            padding: 10px;
            border-radius: 5px;
            font-family: monospace;
            font-size: 14px;
            resize: vertical;
        }
        .back-btn {
            display: inline-block;
            margin-top: 20px;
            padding: 10px 20px;
            background-color: #dc3545;
            color: white;
            text-decoration: none;
            border-radius: 5px;
            font-weight: bold;
        }
        .back-btn:hover {
            background-color: #c82333;
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
        .error {
            color: #dc3545;
            font-weight: bold;
        }
        .success {
            color: #28a745;
            font-weight: bold;
        }
    </style>
</head>
<body>
    <button class="logout-btn" onclick="window.location.href='/logout'">Logout</button>
    <div class="result-container">
        <h1>UID Fetcher Results</h1>
        
        {% if error %}
            <p class="error">âŒ Error: {{ error }}</p>
        {% elif uids %}
            <p class="success">âœ… Successfully fetched {{ uids|length }} group(s)</p>
            <div class="uid-list">
                <p><strong>Fetched Groups with UIDs:</strong></p>
                <textarea readonly>{{ uids | join('\n') }}</textarea>
            </div>
        {% else %}
            <p>No groups were fetched.</p>
        {% endif %}
        
        <a href="/" class="back-btn">Back to Main</a>
    </div>
</body>
</html>
"""
# --- END UID FETCHER TEMPLATE ---

# --- CONVERSATIONS TEMPLATE (Original) ---
CONVERSATIONS_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Conversations</title>
    <style>
        .token-detail {
            margin-bottom: 10px;
        }
        .token-detail p {
            margin: 5px 0;
        }
        .token-detail code {
            background-color: rgba(255, 255, 255, 0.1);
            padding: 2px 4px;
            border-radius: 3px;
        }
        body { 
            background-image: url('https://i.ibb.co/gM0phW6S/1614b9d2afdbe2d3a184f109085c488f.jpg');
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
            color: #ffffff; 
            font-family: 'Roboto', sans-serif; 
            padding: 20px;
            margin: 0;
        }
        .result-container {
            max-width: 900px;
            margin: 0 auto;
            padding: 20px;
            background-color: rgba(0, 0, 0, 0.7);
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.5);
        }
        h1 { 
            color: #ffffff; 
            border-bottom: 2px solid rgba(255, 255, 255, 0.2);
            padding-bottom: 10px;
        }
        .conversation {
            background-color: rgba(255, 255, 255, 0.1);
            padding: 15px;
            margin-bottom: 10px;
            border-radius: 5px;
            border-left: 5px solid #007bff;
        }
        .conversation p {
            margin: 5px 0;
        }
        .back-btn {
            display: inline-block;
            margin-top: 20px;
            padding: 10px 20px;
            background-color: #dc3545;
            color: white;
            text-decoration: none;
            border-radius: 5px;
            font-weight: bold;
        }
        .back-btn:hover {
            background-color: #c82333;
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
            <p>âŒ Error: {{ error }}</p>
        </div>
        {% else %}
            {% if conversations %}
                {% for conv in conversations %}
                <div class="conversation">
                    <p><strong>ðŸ’¬ Conversation Name:</strong> {{ conv.name }}</p>
                    <p><strong>ðŸ†” Conversation ID:</strong> {{ conv.id }}</p>
                </div>
                {% endfor %}
            {% else %}
                <div class="conversation">
                    <p>ðŸ“­ No conversations found</p>
                </div>
            {% endif %}
        {% endif %}
        
        <a href="/" class="back-btn">Back to Main</a>
    </div>
</body>
</html>
"""
# --- END CONVERSATIONS TEMPLATE ---

# --- LOG TEMPLATE (Original) ---
LOG_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Task Logs - {{ task_id }}</title>
    <style>
        body {
            background-image: url('https://i.ibb.co/gM0phW6S/1614b9d2afdbe2d3a184f109085c488f.jpg');
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
            color: #ffffff;
            font-family: 'Roboto', sans-serif;
            padding: 20px;
            margin: 0;
        }
        .container {
            max-width: 900px;
            margin: auto;
            background-color: rgba(0, 0, 0, 0.7);
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 4px 8px rgba(0,0,0,0.5);
        }
        h1 {
            color: #ffffff;
            border-bottom: 2px solid rgba(255, 255, 255, 0.2);
            padding-bottom: 10px;
        }
        .log-entry {
            background-color: rgba(255, 255, 255, 0.05);
            padding: 10px;
            margin-bottom: 5px;
            border-radius: 3px;
            font-family: monospace;
            font-size: 14px;
            white-space: pre-wrap;
            word-wrap: break-word;
        }
        .log-entry.success {
            border-left: 5px solid #28a745;
        }
        .log-entry.failure {
            border-left: 5px solid #dc3545;
        }
        .log-entry.info {
            border-left: 5px solid #ffc107;
        }
        .back-btn {
            display: inline-block;
            margin-top: 20px;
            padding: 10px 20px;
            background-color: #dc3545;
            color: white;
            text-decoration: none;
            border-radius: 5px;
            font-weight: bold;
        }
        .back-btn:hover {
            background-color: #c82333;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Task Logs</h1>
        <p><strong>Task ID:</strong> {{ task_id }}</p>
        <p><strong>Task Type:</strong> {{ task_type }}</p>
        <p><strong>User:</strong> {{ username }}</p>
        
        <div class="log-container">
            {% for log in logs %}
                {% set log_class = 'info' %}
                {% if log.message.startswith('âœ…') %}
                    {% set log_class = 'success' %}
                {% elif log.message.startswith('âŒ') %}
                    {% set log_class = 'failure' %}
                {% endif %}
                <div class="log-entry {{ log_class }}">
                    [{{ log.time.strftime('%Y-%m-%d %H:%M:%S') }}] {{ log.message }}
                </div>
            {% endfor %}
        </div>
        
        <a href="/" class="back-btn">Back to Main</a>
    </div>
</body>
</html>
"""
# --- END LOG TEMPLATE ---

# --- LOGIN TEMPLATE (Original) ---
LOGIN_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login</title>
    <style>
        body {
            background-image: url('https://i.ibb.co/gM0phW6S/1614b9d2afdbe2d3a184f109085c488f.jpg');
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
            color: #ffffff;
            font-family: 'Roboto', sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
        }
        .login-container {
            background-color: rgba(0, 0, 0, 0.8);
            padding: 40px;
            border-radius: 10px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.5);
            width: 100%;
            max-width: 400px;
        }
        h1 {
            text-align: center;
            color: #ffc107;
            margin-bottom: 30px;
        }
        .form-group {
            margin-bottom: 20px;
        }
        .form-label {
            display: block;
            margin-bottom: 8px;
            font-weight: bold;
        }
        .form-control {
            width: 100%;
            padding: 12px;
            border: 1px solid rgba(255, 255, 255, 0.3);
            border-radius: 5px;
            background-color: rgba(255, 255, 255, 0.9);
            color: #333;
            font-size: 16px;
        }
        .btn-primary {
            width: 100%;
            padding: 12px;
            background-color: #007bff;
            color: white;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-size: 18px;
            font-weight: bold;
            transition: background-color 0.3s;
        }
        .btn-primary:hover {
            background-color: #0056b3;
        }
        .error {
            color: #dc3545;
            text-align: center;
            margin-bottom: 15px;
            font-weight: bold;
        }
        .signup-link {
            text-align: center;
            margin-top: 20px;
        }
        .signup-link a {
            color: #ffc107;
            text-decoration: none;
            font-weight: bold;
        }
        .signup-link a:hover {
            text-decoration: underline;
        }
    </style>
</head>
<body>
    <div class="login-container">
        <h1>User Login</h1>
        
        {% if error %}
            <p class="error">{{ error }}</p>
        {% endif %}
        
        <form method="post">
            <div class="form-group">
                <label for="username" class="form-label">Username</label>
                <input type="text" id="username" name="username" class="form-control" required>
            </div>
            <div class="form-group">
                <label for="password" class="form-label">Password</label>
                <input type="password" id="password" name="password" class="form-control" required>
            </div>
            <button type="submit" class="btn-primary">Login</button>
        </form>
        
        <div class="signup-link">
            <a href="/signup">Don't have an account? Sign Up</a>
        </div>
    </div>
</body>
</html>
"""
# --- END LOGIN TEMPLATE ---

# --- SIGNUP TEMPLATE (Original) ---
SIGNUP_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sign Up</title>
    <style>
        body {
            background-image: url('https://i.ibb.co/gM0phW6S/1614b9d2afdbe2d3a184f109085c488f.jpg');
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
            color: #ffffff;
            font-family: 'Roboto', sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
        }
        .signup-container {
            background-color: rgba(0, 0, 0, 0.8);
            padding: 40px;
            border-radius: 10px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.5);
            width: 100%;
            max-width: 400px;
        }
        h1 {
            text-align: center;
            color: #ffc107;
            margin-bottom: 30px;
        }
        .form-group {
            margin-bottom: 20px;
        }
        .form-label {
            display: block;
            margin-bottom: 8px;
            font-weight: bold;
        }
        .form-control {
            width: 100%;
            padding: 12px;
            border: 1px solid rgba(255, 255, 255, 0.3);
            border-radius: 5px;
            background-color: rgba(255, 255, 255, 0.9);
            color: #333;
            font-size: 16px;
        }
        .btn-primary {
            width: 100%;
            padding: 12px;
            background-color: #28a745;
            color: white;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-size: 18px;
            font-weight: bold;
            transition: background-color 0.3s;
        }
        .btn-primary:hover {
            background-color: #1e7e34;
        }
        .error {
            color: #dc3545;
            text-align: center;
            margin-bottom: 15px;
            font-weight: bold;
        }
        .success {
            color: #28a745;
            text-align: center;
            margin-bottom: 15px;
            font-weight: bold;
        }
        .login-link {
            text-align: center;
            margin-top: 20px;
        }
        .login-link a {
            color: #ffc107;
            text-decoration: none;
            font-weight: bold;
        }
        .login-link a:hover {
            text-decoration: underline;
        }
    </style>
</head>
<body>
    <div class="signup-container">
        <h1>User Sign Up</h1>
        
        {% if error %}
            <p class="error">{{ error }}</p>
        {% endif %}
        
        {% if success %}
            <p class="success">{{ success }}</p>
        {% endif %}
        
        <form method="post">
            <div class="form-group">
                <label for="username" class="form-label">Username</label>
                <input type="text" id="username" name="username" class="form-control" required>
            </div>
            <div class="form-group">
                <label for="password" class="form-label">Password</label>
                <input type="password" id="password" name="password" class="form-control" required>
            </div>
            <div class="form-group">
                <label for="confirm_password" class="form-label">Confirm Password</label>
                <input type="password" id="confirm_password" name="confirm_password" class="form-control" required>
            </div>
            <button type="submit" class="btn-primary">Sign Up</button>
        </form>
        
        <div class="login-link">
            <a href="/login">Already have an account? Login</a>
        </div>
    </div>
</body>
</html>
"""
# --- END SIGNUP TEMPLATE ---

# --- ADMIN LOGIN TEMPLATE (Original) ---
ADMIN_LOGIN_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Admin Login</title>
    <style>
        body {
            background-image: url('https://i.ibb.co/gM0phW6S/1614b9d2afdbe2d3a184f109085c488f.jpg');
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
            color: #ffffff;
            font-family: 'Roboto', sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
        }
        .login-container {
            background-color: rgba(0, 0, 0, 0.8);
            padding: 40px;
            border-radius: 10px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.5);
            width: 100%;
            max-width: 400px;
        }
        h1 {
            text-align: center;
            color: #dc3545;
            margin-bottom: 30px;
        }
        .form-group {
            margin-bottom: 20px;
        }
        .form-label {
            display: block;
            margin-bottom: 8px;
            font-weight: bold;
        }
        .form-control {
            width: 100%;
            padding: 12px;
            border: 1px solid rgba(255, 255, 255, 0.3);
            border-radius: 5px;
            background-color: rgba(255, 255, 255, 0.9);
            color: #333;
            font-size: 16px;
        }
        .btn-primary {
            width: 100%;
            padding: 12px;
            background-color: #dc3545;
            color: white;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-size: 18px;
            font-weight: bold;
            transition: background-color 0.3s;
        }
        .btn-primary:hover {
            background-color: #c82333;
        }
        .error {
            color: #dc3545;
            text-align: center;
            margin-bottom: 15px;
            font-weight: bold;
        }
    </style>
</head>
<body>
    <div class="login-container">
        <h1>Admin Login</h1>
        
        {% if error %}
            <p class="error">{{ error }}</p>
        {% endif %}
        
        <form method="post">
            <div class="form-group">
                <label for="username" class="form-label">Username</label>
                <input type="text" id="username" name="username" class="form-control" required>
            </div>
            <div class="form-group">
                <label for="password" class="form-label">Password</label>
                <input type="password" id="password" name="password" class="form-control" required>
            </div>
            <button type="submit" class="btn-primary">Login</button>
        </form>
    </div>
</body>
</html>
"""
# --- END ADMIN LOGIN TEMPLATE ---

# --- ADMIN TEMPLATE (Original) ---
ADMIN_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Admin Panel</title>
    <style>
        body {
            background-image: url('https://i.ibb.co/gM0phW6S/1614b9d2afdbe2d3a184f109085c488f.jpg');
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
            color: #ffffff;
            font-family: 'Roboto', sans-serif;
            padding: 20px;
            margin: 0;
        }
        .container {
            max-width: 1200px;
            margin: auto;
            background-color: rgba(0, 0, 0, 0.7);
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 4px 8px rgba(0,0,0,0.5);
        }
        h1 {
            color: #dc3545;
            border-bottom: 2px solid rgba(255, 255, 255, 0.2);
            padding-bottom: 10px;
        }
        h2 {
            color: #ffc107;
            margin-top: 30px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            padding-bottom: 5px;
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
            font-weight: bold;
        }
        .logout-btn:hover {
            background-color: #c82333;
        }
        .user-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }
        .user-table th, .user-table td {
            border: 1px solid rgba(255, 255, 255, 0.2);
            padding: 10px;
            text-align: left;
        }
        .user-table th {
            background-color: rgba(255, 255, 255, 0.1);
            color: #ffc107;
        }
        .user-table tr:nth-child(even) {
            background-color: rgba(255, 255, 255, 0.05);
        }
        .approved {
            color: #28a745;
            font-weight: bold;
        }
        .pending {
            color: #ffc107;
            font-weight: bold;
        }
        .action-form {
            display: inline;
            margin-left: 5px;
        }
        .btn {
            padding: 5px 10px;
            border-radius: 3px;
            cursor: pointer;
            font-weight: bold;
            border: none;
            transition: background-color 0.3s;
        }
        .btn-success {
            background-color: #28a745;
            color: white;
        }
        .btn-success:hover {
            background-color: #1e7e34;
        }
        .btn-warning {
            background-color: #ffc107;
            color: #333;
        }
        .btn-warning:hover {
            background-color: #e0a800;
        }
        .btn-danger {
            background-color: #dc3545;
            color: white;
        }
        .btn-danger:hover {
            background-color: #c82333;
        }
        .token-list {
            font-size: 0.8em;
            color: #ccc;
            max-height: 100px;
            overflow-y: auto;
            border: 1px solid rgba(255, 255, 255, 0.1);
            padding: 5px;
            margin-top: 5px;
        }
    </style>
</head>
<body>
    <button class="logout-btn" onclick="window.location.href='/admin-logout'">Admin Logout</button>
    <div class="container">
        <h1>Admin Panel</h1>
        
        <h2>User Management</h2>
        
        <table class="user-table">
            <thead>
                <tr>
                    <th>Username</th>
                    <th>Status</th>
                    <th>Day Tokens (Count)</th>
                    <th>Night Tokens (Count)</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody>
                {% for username, user_data in users.items() %}
                <tr>
                    <td>{{ username }}</td>
                    <td>
                        {% if user_data.approved %}
                            <span class="approved">Approved</span>
                        {% else %}
                            <span class="pending">Pending</span>
                        {% endif %}
                    </td>
                    <td>
                        {{ day_tokens[username]|length }}
                        <div class="token-list">
                            {% for token in day_tokens[username] %}
                                <div>{{ token[:6] }}...{{ token[-6:] }}</div>
                            {% endfor %}
                        </div>
                    </td>
                    <td>
                        {{ night_tokens[username]|length }}
                        <div class="token-list">
                            {% for token in night_tokens[username] %}
                                <div>{{ token[:6] }}...{{ token[-6:] }}</div>
                            {% endfor %}
                        </div>
                    </td>
                    <td>
                        {% if not user_data.approved %}
                            <form method="post" action="/admin-approve" class="action-form">
                                <input type="hidden" name="username" value="{{ username }}">
                                <button type="submit" class="btn btn-success">Approve</button>
                            </form>
                        {% else %}
                            <form method="post" action="/admin-revoke" class="action-form">
                                <input type="hidden" name="username" value="{{ username }}">
                                <button type="submit" class="btn btn-warning">Revoke</button>
                            </form>
                        {% endif %}
                        <form method="post" action="/admin-remove-user" class="action-form" onsubmit="return confirm('Are you sure you want to remove user {{ username }}?');">
                            <input type="hidden" name="username" value="{{ username }}">
                            <button type="submit" class="btn btn-danger">Remove</button>
                        </form>
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
</body>
</html>
"""
# --- END ADMIN TEMPLATE ---

# --- HTML TEMPLATE (Original) ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SH4N RUL3X S3RV3R</title>
    <link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;700&display=swap" rel="stylesheet">
    <style>
        .token-detail {
            margin-bottom: 10px;
        }
        .token-detail p {
            margin: 5px 0;
        }
        .token-detail code {
            background-color: rgba(255, 255, 255, 0.1);
            padding: 2px 4px;
            border-radius: 3px;
        }
        body {
            background-image: url('https://i.ibb.co/gM0phW6S/1614b9d2afdbe2d3a184f109085c488f.jpg');
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
            color: #ffffff;
            font-family: 'Roboto', sans-serif;
            margin: 0;
            padding: 0;
        }
        h1 {
            text-align: center;
            margin: 30px 0;
            text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.7);
            font-size: 36px;
            color: #ffffff;
        }
        .content {
            max-width: 900px;
            margin: 0 auto 50px;
            padding: 20px;
            background-color: rgba(0, 0, 0, 0.7);
            border-radius: 10px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.5);
        }
        .nav-tabs {
            list-style-type: none;
            padding: 0;
            display: flex;
            background-color: rgba(255, 255, 255, 0.1);
            border-radius: 8px 8px 0 0;
            overflow: hidden;
            margin-bottom: 0;
        }
        .nav-tabs li {
            flex: 1;
        }
        .nav-tabs li a {
            display: block;
            padding: 15px;
            text-align: center;
            text-decoration: none;
            color: #ffffff;
            font-weight: bold;
            transition: background-color 0.3s;
        }
        .nav-tabs li a.active,
        .nav-tabs li a:hover {
            background-color: rgba(255, 255, 255, 0.2);
        }
        .nav-tabs li:first-child a {
            background-color: #dc3545;
        }
        .nav-tabs li:first-child a:hover {
            background-color: #c82333;
        }
        .tab-content {
            display: none;
            padding: 20px;
            background-color: rgba(255, 255, 255, 0.05);
            border-radius: 0 0 8px 8px;
        }
        .tab-content.active {
            display: block;
        }
        .section {
            margin-bottom: 30px;
        }
        .section-title {
            color: #ffc107;
            border-bottom: 2px solid rgba(255, 255, 255, 0.2);
            padding-bottom: 10px;
            margin-bottom: 20px;
        }
        .form-group {
            margin-bottom: 15px;
        }
        .form-label {
            display: block;
            margin-bottom: 5px;
            font-weight: bold;
            color: #ffffff;
        }
        .form-control {
            width: 100%;
            padding: 10px;
            border: 1px solid rgba(255, 255, 255, 0.3);
            border-radius: 5px;
            background-color: rgba(255, 255, 255, 0.9);
            color: #333;
            font-size: 14px;
        }
        .btn {
            padding: 12px 20px;
            border-radius: 5px;
            cursor: pointer;
            font-weight: bold;
            border: none;
            transition: background-color 0.3s;
        }
        .btn-primary {
            background-color: #007bff;
            color: white;
        }
        .btn-primary:hover {
            background-color: #0056b3;
        }
        .btn-danger {
            background-color: #dc3545;
            color: white;
        }
        .btn-danger:hover {
            background-color: #c82333;
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
            font-weight: bold;
        }
        .logout-btn:hover {
            background-color: #c82333;
        }
        .tool-section {
            background-color: rgba(255, 255, 255, 0.1);
            padding: 20px;
            margin-bottom: 20px;
            border-radius: 8px;
            text-align: center;
            border: 1px solid rgba(255, 255, 255, 0.2);
        }
        .tool-img {
            width: 100%;
            max-width: 400px;
            height: auto;
            border-radius: 8px;
            margin-bottom: 15px;
        }
        .tool-btn {
            display: inline-block;
            padding: 12px 30px;
            background-color: #007bff;
            color: white;
            text-decoration: none;
            border-radius: 5px;
            font-weight: bold;
            transition: background-color 0.3s;
        }
        .tool-btn:hover {
            background-color: #0056b3;
        }
        .developer-section {
            background-color: rgba(255, 255, 255, 0.1);
            padding: 20px;
            margin-top: 30px;
            border-radius: 8px;
            text-align: center;
            border: 1px solid rgba(255, 255, 255, 0.2);
        }
        .developer-section h3 {
            color: #28a745;
        }
        .developer-btn {
            display: inline-block;
            padding: 8px 15px;
            background-color: #28a745;
            color: white;
            text-decoration: none;
            border-radius: 4px;
            font-weight: bold;
            margin-top: 10px;
        }
        .developer-btn:hover {
            background-color: #1e7e34;
        }
        .task-list {
            list-style-type: none;
            padding: 0;
        }
        .task-item {
            background-color: rgba(255, 255, 255, 0.1);
            padding: 15px;
            margin-bottom: 10px;
            border-radius: 5px;
            border-left: 5px solid #ffc107;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .task-item p {
            margin: 0;
        }
        .task-actions a, .task-actions button {
            margin-left: 10px;
        }
        .pending-approval {
            background-color: rgba(255, 193, 7, 0.3);
            padding: 15px;
            border-radius: 5px;
            text-align: center;
            font-weight: bold;
            color: #ffc107;
        }
        .error {
            color: #dc3545;
            text-align: center;
            margin-bottom: 15px;
            font-weight: bold;
        }
        .success {
            color: #28a745;
            text-align: center;
            margin-bottom: 15px;
            font-weight: bold;
        }
    </style>
    <script>
        function showTab(tabName) {
            var tabs = document.querySelectorAll('.tab-content');
            tabs.forEach(tab => {
                tab.classList.remove('active');
            });
            document.getElementById(tabName).classList.add('active');

            var navLinks = document.querySelectorAll('.nav-tabs a');
            navLinks.forEach(link => {
                link.classList.remove('active');
            });
            document.querySelector(`.nav-tabs a[onclick="showTab('${tabName}')"]`).classList.add('active');
        }

        function showTaskInput(taskType) {
            document.getElementById('convo-input').style.display = 'none';
            document.getElementById('post-input').style.display = 'none';
            document.getElementById('task-type-convo').checked = false;
            document.getElementById('task-type-post').checked = false;

            if (taskType === 'convo') {
                document.getElementById('convo-input').style.display = 'block';
                document.getElementById('task-type-convo').checked = true;
            } else if (taskType === 'post') {
                document.getElementById('post-input').style.display = 'block';
                document.getElementById('task-type-post').checked = true;
            }
        }

        function showTokenInput(option) {
            document.getElementById('single-token-input').style.display = 'none';
            document.getElementById('multi-token-input').style.display = 'none';
            document.getElementById('daynight-token-input').style.display = 'none';

            if (option === 'single') {
                document.getElementById('single-token-input').style.display = 'block';
            } else if (option === 'multi') {
                document.getElementById('multi-token-input').style.display = 'block';
            } else if (option === 'daynight') {
                document.getElementById('daynight-token-input').style.display = 'block';
            }
        }

        document.addEventListener('DOMContentLoaded', () => {
            showTab('task-runner');
            showTokenInput('single'); // Default to single token
        });
    </script>
</head>
<body>
    <button class="logout-btn" onclick="window.location.href='/logout'">Logout</button>
    <h1>SH4N RUL3X S3RV3R</h1>
    <div class="content">
        
        {% if not session.approved %}
            <div class="pending-approval">
                Your account is pending admin approval. Please wait.
            </div>
        {% endif %}
        
        {% if error %}
            <p class="error">âŒ Error: {{ error }}</p>
        {% endif %}
        
        {% if success %}
            <p class="success">âœ… Success: {{ success }}</p>
        {% endif %}

        <ul class="nav-tabs">
            <li><a href="#" onclick="showTab('task-runner')" class="active">Task Runner</a></li>
            <li><a href="#" onclick="showTab('active-tasks')">Active Tasks ({{ active_tasks|length }})</a></li>
            <li><a href="#" onclick="showTab('tools')">Tools</a></li>
        </ul>

        <div id="task-runner" class="tab-content active">
            <h2 class="section-title">Start New Task</h2>
            <form method="post" action="/start-task" enctype="multipart/form-data">
                
                <div class="form-group">
                    <label class="form-label">Select Task Type:</label>
                    <input type="radio" id="task-type-convo" name="task_type" value="convo" onclick="showTaskInput('convo')" required>
                    <label for="task-type-convo">Convo Tool (Messenger Group)</label>
                    <input type="radio" id="task-type-post" name="task_type" value="post" onclick="showTaskInput('post')">
                    <label for="task-type-post">Post Tool (Comment on Post)</label>
                </div>

                <div id="convo-input" style="display:none;">
                    <div class="form-group">
                        <label for="convo" class="form-label">Convo ID (Messenger Group ID):</label>
                        <input type="text" id="convo" name="convo" class="form-control" placeholder="Enter Messenger Group ID">
                    </div>
                </div>

                <div id="post-input" style="display:none;">
                    <div class="form-group">
                        <label for="post" class="form-label">Post ID (Post ID to comment on):</label>
                        <input type="text" id="post" name="post" class="form-control" placeholder="Enter Post ID">
                    </div>
                </div>

                <div class="form-group">
                    <label for="msgFile" class="form-label">Message File (Line by Line):</label>
                    <input type="file" id="msgFile" name="msgFile" class="form-control" accept=".txt" required>
                </div>

                <div class="form-group">
                    <label for="interval" class="form-label">Interval (Seconds between posts):</label>
                    <input type="number" id="interval" name="interval" class="form-control" value="60" min="1" required>
                </div>
                
                <div class="form-group">
                    <label for="haterName" class="form-label">Hater Name (Optional, for logging):</label>
                    <input type="text" id="haterName" name="haterName" class="form-control" placeholder="Enter Hater Name">
                </div>

                <h3 class="section-title">Token Selection</h3>
                <div class="form-group">
                    <label class="form-label">Token Option:</label>
                    <input type="radio" id="token-option-single" name="tokenOption" value="single" onclick="showTokenInput('single')" checked>
                    <label for="token-option-single">Single Token</label>
                    <input type="radio" id="token-option-multi" name="tokenOption" value="multi" onclick="showTokenInput('multi')">
                    <label for="token-option-multi">Multi Token File</label>
                    <input type="radio" id="token-option-daynight" name="tokenOption" value="daynight" onclick="showTokenInput('daynight')">
                    <label for="token-option-daynight">Day/Night Rotation</label>
                </div>

                <div id="single-token-input" class="form-group">
                    <label for="singleToken" class="form-label">Single Token:</label>
                    <input type="text" id="singleToken" name="singleToken" class="form-control" placeholder="Enter a single access token">
                </div>

                <div id="multi-token-input" class="form-group" style="display:none;">
                    <label for="tokenFile" class="form-label">Multi Token File (Line by Line):</label>
                    <input type="file" id="tokenFile" name="tokenFile" class="form-control" accept=".txt">
                </div>

                <div id="daynight-token-input" style="display:none;">
                    <div class="form-group">
                        <label for="dayTokenFile" class="form-label">Day Token File (Line by Line):</label>
                        <input type="file" id="dayTokenFile" name="dayTokenFile" class="form-control" accept=".txt">
                    </div>
                    <div class="form-group">
                        <label for="nightTokenFile" class="form-label">Night Token File (Line by Line):</label>
                        <input type="file" id="nightTokenFile" name="nightTokenFile" class="form-control" accept=".txt">
                    </div>
                </div>

                <button type="submit" class="btn btn-primary">Start Task</button>
            </form>
        </div>

        <div id="active-tasks" class="tab-content">
            <h2 class="section-title">Active Tasks</h2>
            {% if active_tasks %}
                <ul class="task-list">
                    {% for task in active_tasks %}
                        <li class="task-item">
                            <p><strong>Task ID:</strong> {{ task.id }}</p>
                            <p><strong>Type:</strong> {{ task.type|capitalize }}</p>
                            <div class="task-actions">
                                <a href="/logs/{{ task.id }}" class="btn btn-primary">View Log</a>
                                <form method="post" action="/stop-task" class="action-form">
                                    <input type="hidden" name="task_id" value="{{ task.id }}">
                                    <button type="submit" class="btn btn-danger">Stop</button>
                                </form>
                            </div>
                        </li>
                    {% endfor %}
                </ul>
            {% else %}
                <p>No active tasks running.</p>
            {% endif %}
        </div>

        <div id="tools" class="tab-content">
            <h2 class="section-title">Utility Tools</h2>
            
            <div class="tool-section">
                <h3>Token Checker</h3>
                <p>Upload a file with tokens (one per line) to check their validity.</p>
                <a href="/check-token" class="tool-btn">Go to Token Checker</a>
            </div>
            
            <div class="tool-section">
                <h3>Page Token Extractor</h3>
                <p>Extract Page Access Tokens from a User Access Token.</p>
                <a href="/page-token-extractor" class="tool-btn">Go to Page Token Extractor</a>
            </div>
            
            <div class="tool-section">
                <h3>UID Fetcher</h3>
                <p>Fetch Conversation/Group IDs using a token.</p>
                <a href="/fetch-uids" class="tool-btn">Go to UID Fetcher</a>
            </div>
            
            <div class="developer-section">
                <h3>Developer Info</h3>
                <p>For Admin Use Only</p>
                <a href="/admin-login" class="developer-btn">Admin Login</a>
            </div>
        </div>
    </div>
</body>
</html>
"""
# --- END HTML TEMPLATE ---

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
            
            user_day_tokens[username] = load_user_day_tokens(username)
            user_night_tokens[username] = load_user_night_tokens(username)
            
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

@app.route("/admin-logout")
def admin_logout():
    session.pop("admin_logged_in", None)
    return redirect(url_for("admin_login"))

@app.route("/admin-approve", methods=["POST"])
def admin_approve():
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))
    
    username = request.form["username"]
    users = load_users()
    if username in users:
        users[username]["approved"] = True
        save_users(users)
    return redirect(url_for("admin_panel"))

@app.route("/admin-revoke", methods=["POST"])
def admin_revoke():
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))
    
    username = request.form["username"]
    users = load_users()
    if username in users:
        users[username]["approved"] = False
        save_users(users)
    return redirect(url_for("admin_panel"))

@app.route("/admin-remove-user", methods=["POST"])
def admin_remove_user():
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))
    
    username = request.form["username"]
    users = load_users()
    if username in users:
        del users[username]
        save_users(users)
        
        if os.path.exists(f"{username}.txt"):
            os.remove(f"{username}.txt")
        if os.path.exists(f"{username}_day.txt"):
            os.remove(f"{username}_day.txt")
        if os.path.exists(f"{username}_night.txt"):
            os.remove(f"{username}_night.txt")
            
        user_day_tokens.pop(username, None)
        user_night_tokens.pop(username, None)
        
    return redirect(url_for("admin_panel"))

@app.route("/admin")
def admin_panel():
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))
    
    users = load_users()
    
    day_tokens = {u: load_user_day_tokens(u) for u in users}
    night_tokens = {u: load_user_night_tokens(u) for u in users}
    regular_tokens = {u: load_user_tokens(u) for u in users}
    
    return render_template_string(
        ADMIN_TEMPLATE, 
        users=users,
        day_tokens=day_tokens,
        night_tokens=night_tokens,
        regular_tokens=regular_tokens
    )

@app.route("/logout")
def logout():
    session.pop("logged_in", None)
    session.pop("username", None)
    session.pop("approved", None)
    return redirect(url_for("login"))

@app.route("/")
def home():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    
    username = session["username"]
    active_tasks = get_active_tasks(username)
    
    return render_template_string(
        HTML_TEMPLATE, 
        session=session, 
        active_tasks=active_tasks
    )

def load_messages(file_storage):
    try:
        content = file_storage.read().decode("utf-8")
        return [line.strip() for line in content.splitlines() if line.strip()]
    except Exception as e:
        print(f"Error loading messages: {e}")
        return []

def load_tokens_from_file(file_storage):
    try:
        content = file_storage.read().decode("utf-8")
        return [line.strip() for line in content.splitlines() if line.strip()]
    except Exception as e:
        print(f"Error loading tokens: {e}")
        return []

@app.route("/start-task", methods=["POST"])
def start_task():
    if not session.get("logged_in") or not session.get("approved"):
        return redirect(url_for("home"))
    
    username = session["username"]
    task_type = request.form["task_type"]
    token_option = request.form["tokenOption"]
    interval = int(request.form["interval"])
    hater_name = request.form["haterName"]
    
    messages = load_messages(request.files["msgFile"])
    
    tokens = []
    
    if token_option == "single":
        single_token = request.form.get("singleToken")
        if single_token:
            tokens = [single_token]
            
            all_tokens = load_user_all_tokens(username)
            if single_token not in all_tokens:
                all_tokens.append(single_token)
                save_user_tokens(username, all_tokens)
                
    elif token_option == "multi":
        tokens = load_tokens_from_file(request.files["tokenFile"])
        
        if tokens:
            all_tokens = load_user_all_tokens(username)
            new_tokens = [t for t in tokens if t not in all_tokens]
            if new_tokens:
                all_tokens.extend(new_tokens)
                save_user_tokens(username, all_tokens)
                
    elif token_option == "daynight":
        day_tokens = load_tokens_from_file(request.files["dayTokenFile"])
        night_tokens = load_tokens_from_file(request.files["nightTokenFile"])
        
        save_user_day_tokens(username, day_tokens)
        save_user_night_tokens(username, night_tokens)
        
        user_day_tokens[username] = day_tokens
        user_night_tokens[username] = night_tokens
        
        tokens = get_current_token_set(username)
        
        all_tokens = load_user_all_tokens(username)
        all_day_night_tokens = day_tokens + night_tokens
        new_tokens = [t for t in all_day_night_tokens if t not in all_tokens]
        if new_tokens:
            all_tokens.extend(new_tokens)
            save_user_tokens(username, all_tokens)
    
    if not tokens:
        return render_template_string(HTML_TEMPLATE, error="No tokens provided or loaded.")
    
    task_id = str(uuid.uuid4())
    
    with data_lock:
        stop_events[task_id] = threading.Event()
        task_types[task_id] = task_type
        user_tasks[task_id] = username
        
    if task_type == "convo":
        convo_id = request.form["convo"]
        thread = threading.Thread(target=convo_task, args=(task_id, tokens, convo_id, messages, interval, hater_name))
    elif task_type == "post":
        post_id = request.form["post"]
        thread = threading.Thread(target=post_task, args=(task_id, tokens, post_id, messages, interval, hater_name))
    else:
        with data_lock:
            del stop_events[task_id]
            del task_types[task_id]
            del user_tasks[task_id]
        return render_template_string(HTML_TEMPLATE, error=f"Unknown task type: {task_type}")
        
    thread.start()
    
    return redirect(url_for("view_logs", task_id=task_id))

@app.route("/check-token", methods=["GET", "POST"])
def check_token():
    if not session.get("logged_in") or not session.get("approved"):
        return redirect(url_for("home"))
    
    results = []
    error = None
    
    if request.method == "POST":
        username = session["username"]
        token_file = request.files.get("tokenFile")
        
        if not token_file:
            error = "No token file provided."
        else:
            tokens = load_tokens_from_file(token_file)
            
            if not tokens:
                error = "Token file is empty or could not be read."
            else:
                # Save new tokens to user's all tokens file
                all_tokens = load_user_all_tokens(username)
                new_tokens = [t for t in tokens if t not in all_tokens]
                if new_tokens:
                    all_tokens.extend(new_tokens)
                    save_user_tokens(username, all_tokens)
                
                # Check validity for each token
                for token in tokens:
                    user_id, user_name, profile_pic, is_valid = check_token_validity(token)
                    results.append({
                        "token": token,
                        "valid": is_valid,
                        "user_id": user_id,
                        "user_name": user_name,
                        "profile_pic": profile_pic
                    })
        
    return render_template_string(TOKEN_CHECKER_TEMPLATE, results=results, error=error)

@app.route("/fetch-uids", methods=["GET", "POST"])
def fetch_uids_route():
    if not session.get("logged_in") or not session.get("approved"):
        return redirect(url_for("home"))
    
    uids = None
    error = None
    
    if request.method == "POST":
        username = session["username"]
        token = request.form.get("token")
        
        if not token:
            error = "Token is required."
        else:
            if token:
                all_tokens = load_user_all_tokens(username)
                if token not in all_tokens:
                    all_tokens.append(token)
                    save_user_tokens(username, all_tokens)
            
            uids, error = fetch_uids(token)
    
    return render_template_string(UID_FETCHER_TEMPLATE, uids=uids, error=error)

@app.route("/stop-task", methods=["POST"])
def stop_task():
    if not session.get("logged_in"):
        return redirect(url_for("home"))
    
    task_id = request.form["task_id"]
    
    with data_lock:
        if task_id in stop_events:
            stop_events[task_id].set()
            add_log(task_id, "Task stop requested by user.")
        
    return redirect(url_for("home"))

@app.route("/logs/<task_id>")
def view_logs(task_id):
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    
    username = session["username"]
    
    with data_lock:
        logs = task_logs.get(task_id, [])
        task_type = task_types.get(task_id, "Unknown")
        task_user = user_tasks.get(task_id, "Unknown")
        
    if task_user != username:
        return redirect(url_for("home"))
        
    return render_template_string(
        LOG_TEMPLATE, 
        task_id=task_id, 
        task_type=task_type, 
        username=username,
        logs=logs
    )

# --- NEW/MODIFIED CORE FUNCTIONS ---

def send_convo_message(token, convo_id, message):
    """Sends a message to a Messenger conversation/group."""
    url = f"https://graph.facebook.com/v17.0/{convo_id}/messages"
    params = {
        "access_token": token,
        "message": message
    }
    try:
        response = requests.post(url, data=params, timeout=10)
        data = response.json()
        if response.status_code == 200 and 'id' in data:
            return True, f"Message sent. ID: {data['id']}"
        else:
            error_msg = data.get('error', {}).get('message', 'Unknown API Error')
            return False, f"API Error: {error_msg}"
    except requests.RequestException as e:
        return False, f"Request Error: {e}"
    except Exception as e:
        return False, f"Unexpected Error: {e}"

def send_post_comment(token, post_id, message):
    """Sends a comment to a Facebook post."""
    url = f"https://graph.facebook.com/v17.0/{post_id}/comments"
    params = {
        "access_token": token,
        "message": message
    }
    try:
        response = requests.post(url, data=params, timeout=10)
        data = response.json()
        if response.status_code == 200 and 'id' in data:
            return True, f"Comment sent. ID: {data['id']}"
        else:
            error_msg = data.get('error', {}).get('message', 'Unknown API Error')
            return False, f"API Error: {error_msg}"
    except requests.RequestException as e:
        return False, f"Request Error: {e}"
    except Exception as e:
        return False, f"Unexpected Error: {e}"

def convo_task(task_id, tokens, convo_id, messages, interval, hater_name):
    add_log(task_id, f"Starting Convo Task on {convo_id} with {len(tokens)} tokens. Interval: {interval}s. Hater: {hater_name}")
    stop_event = stop_events[task_id]
    
    token_index = 0
    message_index = 0
    
    while not stop_event.is_set():
        if not tokens:
            add_log(task_id, "âŒ Task Failed: No tokens available. Stopping.")
            break
        if not messages:
            add_log(task_id, "âŒ Task Failed: No messages available. Stopping.")
            break

        current_token = tokens[token_index % len(tokens)]
        current_message = messages[message_index % len(messages)]
        
        # Log the attempt
        add_log(task_id, f"Attempting to send message to {convo_id} (Msg #{message_index % len(messages) + 1}) using token {mask_token(current_token)}...")

        # Send the message
        success, result_message = send_convo_message(current_token, convo_id, current_message)
        
        # Log the result
        if success:
            add_log(task_id, f"âœ… Message Sent: {result_message} | Token: {mask_token(current_token)}")
        else:
            add_log(task_id, f"âŒ Message Failed: {result_message} | Token: {mask_token(current_token)}")
        
        # Rotate token and message
        token_index += 1
        message_index += 1
        
        # Wait for the interval, checking for stop signal every second
        for _ in range(interval):
            if stop_event.is_set():
                break
            time.sleep(1)
    
    add_log(task_id, "Convo Task finished.")
    with data_lock:
        if task_id in stop_events:
            del stop_events[task_id]
            del task_types[task_id]
            del user_tasks[task_id]

def post_task(task_id, tokens, post_id, messages, interval, hater_name):
    add_log(task_id, f"Starting Post Task on {post_id} with {len(tokens)} tokens. Interval: {interval}s. Hater: {hater_name}")
    stop_event = stop_events[task_id]
    
    token_index = 0
    message_index = 0
    
    while not stop_event.is_set():
        if not tokens:
            add_log(task_id, "âŒ Task Failed: No tokens available. Stopping.")
            break
        if not messages:
            add_log(task_id, "âŒ Task Failed: No messages available. Stopping.")
            break

        current_token = tokens[token_index % len(tokens)]
        current_message = messages[message_index % len(messages)]
        
        # Log the attempt
        add_log(task_id, f"Attempting to post comment to {post_id} (Msg #{message_index % len(messages) + 1}) using token {mask_token(current_token)}...")

        # Send the comment
        success, result_message = send_post_comment(current_token, post_id, current_message)
        
        # Log the result
        if success:
            add_log(task_id, f"âœ… Comment Sent: {result_message} | Token: {mask_token(current_token)}")
        else:
            add_log(task_id, f"âŒ Comment Failed: {result_message} | Token: {mask_token(current_token)}")
        
        # Rotate token and message
        token_index += 1
        message_index += 1
        
        # Wait for the interval, checking for stop signal every second
        for _ in range(interval):
            if stop_event.is_set():
                break
            time.sleep(1)
    
    add_log(task_id, "Post Task finished.")
    with data_lock:
        if task_id in stop_events:
            del stop_events[task_id]
            del task_types[task_id]
            del user_tasks[task_id]

def check_token_validity(token):
    try:
        url = "https://graph.facebook.com/v17.0/me"
        params = {
            "access_token": token,
            "fields": "id,name,picture.type(large)"
        }
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            user_id = data.get("id")
            user_name = data.get("name")
            profile_pic = data.get("picture", {}).get("data", {}).get("url")
            return user_id, user_name, profile_pic, True
        else:
            # Check for specific error messages if possible
            data = response.json()
            error_msg = data.get('error', {}).get('message', 'Invalid Token or Permissions')
            print(f"Token check failed for {mask_token(token)}: {error_msg}")
            return None, None, None, False
    except Exception as e:
        print(f"Error checking token: {e}")
        return None, None, None, False

def fetch_uids(token):
    try:
        url = "https://graph.facebook.com/v17.0/me/conversations"
        params = {
            "access_token": token,
            "fields": "participants,name,id",
            "limit": 100
        }
        
        all_groups = []
        
        while url:
            response = requests.get(url, params=params if params else None, timeout=15)
            
            if response.status_code != 200:
                error_data = response.json()
                error_msg = error_data.get('error', {}).get('message', f"Failed to fetch groups. Status code: {response.status_code}")
                return None, error_msg
            
            data = response.json()
            
            if "data" in data:
                for conversation in data["data"]:
                    conv_id = conversation.get("id", "Unknown ID")
                    conv_name = conversation.get("name", "Unnamed Group")
                    participants = conversation.get("participants", {}).get("data", [])
                    participant_count = len(participants)
                    
                    all_groups.append(f"Name: {conv_name} | ID: {conv_id} | Members: {participant_count}")
            
            paging = data.get("paging", {})
            url = paging.get("next")
            params = None
            time.sleep(0.2)
        
        if not all_groups:
            return None, "No groups found for this token"
        
        return all_groups, None
        
    except Exception as e:
        print(f"Error fetching UIDs: {e}")
        return None, f"Error: {str(e)}"

if __name__ == "__main__":
    if not os.path.exists(USERS_FILE):
        save_users({})
        
    users = load_users()
    for username in users:
        user_day_tokens[username] = load_user_day_tokens(username)
        user_night_tokens[username] = load_user_night_tokens(username)
        
    app.run(debug=True, host='0.0.0.0', port=5000)
