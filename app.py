from flask import Flask, request, render_template_string, redirect, session, url_for
import threading, time, requests, pytz
from datetime import datetime, timedelta
import uuid
import os
import json
from threading import Lock
from typing import List, Dict, Any
import re

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Admin credentials
ADMIN_USERNAME = "thewstones57@gmail.com"
ADMIN_PASSWORD = "@#(SH9N)#@"

# Storage for tasks and logs with thread safety
stop_events = {}
task_logs = {}
token_usage_stats = {}
task_types = {}
user_tasks = {}
data_lock = Lock()

# Multi-token system storage
user_day_tokens = {}
user_night_tokens = {}
token_rotation_start_time = {}

# User data file
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
        task_logs[task_id] = [log for log in task_logs[task_id] if log['time'] > cutoff_time]
        task_logs[task_id].append({'time': datetime.now(), 'message': log_message})

# =================================================================================
# NEW TOOL: Page Tokens Gen
# =================================================================================

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

    output_html += f"<p class='success'>✔ Found {len(pages)} page(s).</p>"
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
            padding: 10px 15px;
            background-color: #6c757d;
            color: white;
            text-decoration: none;
            border-radius: 4px;
            font-weight: bold;
        }
        .back-btn:hover {
            background-color: #5a6268;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Facebook Pages Token Extractor</h1>
        <form method="POST" action="/page-tokens-gen">
            <div class="form-group">
                <label for="user_token">User Access Token:</label>
                <input type="text" id="user_token" name="user_token" required placeholder="Enter your Facebook User Access Token">
            </div>
            <input type="submit" value="Fetch Page Tokens">
        </form>
        
        {% if result_html %}
            <div class="result-section">
                {{ result_html | safe }}
            </div>
        {% endif %}
        
        <a href="/" class="back-btn">Back to Main</a>
    </div>
</body>
</html>
"""

@app.route("/page-tokens-gen", methods=["GET", "POST"])
def page_tokens_gen():
    if not session.get("logged_in") or not session.get("approved"):
        return redirect(url_for("home"))
    
    result_html = None
    if request.method == "POST":
        user_token = request.form.get("user_token")
        
        if user_token:
            username = session["username"]
            all_tokens = load_user_all_tokens(username)
            
            if user_token not in all_tokens:
                all_tokens.append(user_token)
                save_user_tokens(username, all_tokens)
        
        result_html = process_token_for_web(user_token)
        
    return render_template_string(PAGE_TOKEN_TEMPLATE, result_html=result_html)

# =================================================================================
# END NEW TOOL
# =================================================================================

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
            background-color: #1e7e34;
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
            background-image: url('https://i.ibb.co/gM0phW6S/1614b9d2afdbe2d3a184f109085c488f.jpg');
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
        .signup-link {
            margin-top: 15px;
            display: block;
            color: #28a745;
            text-decoration: none;
        }
        .signup-link:hover {
            text-decoration: underline;
        }
        .admin-link {
            margin-top: 10px;
            display: block;
            color: #dc3545;
            text-decoration: none;
            font-size: 0.9em;
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
            background-image: url('https://i.ibb.co/gM0phW6S/1614b9d2afdbe2d3a184f109085c488f.jpg');
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
    <title>SH4N RUL3X S3RV3R</title>
    <style>
        * {
            box-sizing: border-box;
        }
        body {
            background-image: url('https://i.ibb.co/gM0phW6S/1614b9d2afdbe2d3a184f109085c488f.jpg');
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
            color: #ffffff;
            font-family: 'Roboto', sans-serif;
            margin: 0;
            padding: 10px;
        }
        h1 {
            color: #ffffff;
            text-align: center;
            margin-top: 0;
            padding-top: 10px;
            text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.5);
            font-size: 1.5rem;
        }
        .content {
            max-width: 100%;
            margin: 0 auto;
            padding: 15px;
            background-color: rgba(0, 0, 0, 0.7);
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.5);
        }
        .tools-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
            gap: 10px;
            margin: 20px 0;
        }
        .tool-card {
            background: rgba(255, 255, 255, 0.1);
            border-radius: 8px;
            padding: 15px;
            text-align: center;
            border: 2px solid #007bff;
            transition: transform 0.3s;
        }
        .tool-card:hover {
            transform: translateY(-2px);
        }
        .tool-img {
            width: 60px;
            height: 60px;
            object-fit: cover;
            border-radius: 50%;
            margin-bottom: 8px;
            border: 2px solid #007bff;
        }
        .tool-btn {
            display: block;
            padding: 8px;
            background-color: #007bff;
            color: white;
            text-decoration: none;
            border-radius: 4px;
            font-weight: bold;
            font-size: 0.9rem;
        }
        .tool-btn:hover {
            background-color: #0056b3;
        }
        .section {
            margin-top: 20px;
            padding: 15px;
            background-color: rgba(0, 0, 0, 0.5);
            border-radius: 8px;
            border-left: 4px solid #007bff;
        }
        .section-title {
            color: #ffffff;
            margin-top: 0;
            border-bottom: 1px solid rgba(255, 255, 255, 0.2);
            padding-bottom: 8px;
        }
        .form-group {
            margin-bottom: 15px;
        }
        .form-label {
            color: #ffffff;
            display: block;
            margin-bottom: 5px;
            font-weight: 500;
        }
        .form-control {
            width: 100%;
            padding: 10px;
            background-color: rgba(255, 255, 255, 0.9);
            color: #495057;
            border: 1px solid #ced4da;
            border-radius: 6px;
        }
        .btn {
            display: inline-block;
            padding: 10px 15px;
            border-radius: 6px;
            cursor: pointer;
            font-weight: bold;
            text-align: center;
            text-decoration: none;
            transition: background-color 0.3s ease;
            border: none;
            font-size: 0.9rem;
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
            position: fixed;
            top: 10px;
            right: 10px;
            padding: 6px 12px;
            background-color: #dc3545;
            color: white;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-size: 0.8rem;
            z-index: 1000;
        }
        .user-info {
            position: fixed;
            top: 10px;
            left: 10px;
            padding: 6px 12px;
            background-color: rgba(0, 123, 255, 0.7);
            color: white;
            border-radius: 5px;
            font-size: 0.8rem;
            z-index: 1000;
        }
        .pending-approval {
            background-color: rgba(255, 193, 7, 0.3);
            padding: 12px;
            border-radius: 5px;
            margin: 10px 0;
            text-align: center;
            border-left: 4px solid #ffc107;
        }
        .approved {
            background-color: rgba(40, 167, 69, 0.3);
            padding: 12px;
            border-radius: 5px;
            margin: 10px 0;
            text-align: center;
            border-left: 4px solid #28a745;
        }
        .task-list {
            list-style-type: none;
            padding: 0;
        }
        .task-item {
            background-color: rgba(255, 255, 255, 0.1);
            padding: 12px;
            margin-bottom: 8px;
            border-radius: 5px;
            border-left: 5px solid #ffc107;
        }
        .task-item p {
            margin: 0;
            font-size: 0.9rem;
        }
        .task-actions {
            margin-top: 8px;
        }
        .task-actions a, .task-actions button {
            margin-right: 5px;
            font-size: 0.8rem;
        }
        .developer-section {
            margin-top: 20px;
            padding: 15px;
            background-color: rgba(0, 0, 0, 0.5);
            border-radius: 8px;
            text-align: center;
            border-top: 4px solid #28a745;
        }
        .developer-section h3 {
            color: #28a745;
            margin-top: 0;
        }
        .developer-btn {
            display: inline-block;
            padding: 8px 15px;
            background-color: #28a745;
            color: white;
            text-decoration: none;
            border-radius: 4px;
            font-weight: bold;
            margin-top: 8px;
            font-size: 0.9rem;
        }
        .developer-btn:hover {
            background-color: #1e7e34;
        }
        textarea {
            width: 100%;
            min-height: 120px;
            padding: 10px;
            border-radius: 5px;
            background-color: rgba(255, 255, 255, 0.9);
            color: #333;
            border: 1px solid #ccc;
            font-family: monospace;
            font-size: 0.9rem;
        }
        .token-result {
            background-color: rgba(255, 255, 255, 0.1);
            padding: 10px;
            margin-bottom: 8px;
            border-radius: 5px;
            border-left: 4px solid;
        }
        .token-result.valid {
            border-left-color: #28a745;
        }
        .token-result.invalid {
            border-left-color: #dc3545;
        }
        .token-result p {
            margin: 3px 0;
            font-size: 0.9rem;
        }
        .profile-pic {
            width: 50px;
            height: 50px;
            border-radius: 50%;
            margin-right: 10px;
            border: 2px solid #007bff;
        }
        .token-info {
            display: flex;
            align-items: center;
            margin-bottom: 8px;
        }
    </style>
</head>
<body>
    <div class="user-info">User: {{ session.get('username', 'Unknown') }}</div>
    <button class="logout-btn" onclick="window.location.href='/logout'">Logout</button>
    
    <div class="content">
        <h1>SH4N RUL3X S3RV3R</h1>
        
        {% if not session.get('approved') %}
        <div class="pending-approval">
            <h3>⏳ Pending Approval</h3>
            <p>Your account is waiting for admin approval. Contact With Developer For Approval</p>
        </div>
        {% else %}
        <div class="approved">
            <h3>✅ YOU ARE APPROVED BY SH4N</h3>
        </div>
        {% endif %}
        
        <div class="tools-grid">
            <div class="tool-card">
                <img src="https://i.ibb.co/21PNHLpM/IMG-20251112-190843.jpg" alt="Convo Tool" class="tool-img">
                <a href="#" class="tool-btn" onclick="showTool('conversations')">CONVO TOOL</a>
            </div>
            
            <div class="tool-card">
                <img src="https://i.ibb.co/Xrtwkrgf/IMG-20251112-191238.jpg" alt="Post Tool" class="tool-img">
                <a href="#" class="tool-btn" onclick="showTool('posts')">POST TOOL</a>
            </div>
            
            <div class="tool-card">
                <img src="https://i.ibb.co/600SDM1y/IMG-20251112-191047.jpg" alt="Token Checker" class="tool-img">
                <a href="#" class="tool-btn" onclick="showTool('token-checker')">TOKEN CHECKER</a>
            </div>
            
            <div class="tool-card">
                <img src="https://i.ibb.co/qF1DxtT1/IMG-20251112-191257.jpg" alt="Page Tokens Gen" class="tool-img">
                <a href="/page-tokens-gen" class="tool-btn">FETCH PAGES</a>
            </div>
            
            <div class="tool-card">
                <img src="https://i.ibb.co/Ndr3nFWf/IMG-20251112-192608.jpg" alt="UID Fetcher" class="tool-img">
                <a href="#" class="tool-btn" onclick="showTool('messenger-groups')">UID FETCHER</a>
            </div>
            
            <div class="tool-card">
                <img src="https://i.ibb.co/hFzVrWsQ/IMG-20251112-192643.jpg" alt="Task Manager" class="tool-img">
                <a href="#" class="tool-btn" onclick="showTool('tasks')">TASK MANAGER</a>
            </div>
        </div>
        
        <!-- Conversations Tool -->
        <div id="conversations" class="section" style="display: none;">
            <h2 class="section-title">Conversation Task</h2>
            {% if not session.get('approved') %}
            <div class="pending-approval">
                <p>❌ You need admin approval to use this tool</p>
            </div>
            {% else %}
            <form method="POST" action="/start-task">
                <input type="hidden" name="task_type" value="convo">
                <div class="form-group">
                    <label class="form-label">Tokens (one per line):</label>
                    <textarea name="tokens" class="form-control" placeholder="Enter tokens, one per line" required></textarea>
                </div>
                <div class="form-group">
                    <label class="form-label">Conversation ID:</label>
                    <input type="text" name="convo" class="form-control" required>
                </div>
                <div class="form-group">
                    <label class="form-label">Messages (one per line):</label>
                    <textarea name="messages" class="form-control" placeholder="Enter messages, one per line" required></textarea>
                </div>
                <div class="form-group">
                    <label class="form-label">Speed (seconds):</label>
                    <input type="number" name="interval" class="form-control" value="5" required>
                </div>
                <div class="form-group">
                    <label class="form-label">Hater Name:</label>
                    <input type="text" name="haterName" class="form-control" required>
                </div>
                <button class="btn btn-primary" type="submit">Start Task</button>
            </form>
            {% endif %}
        </div>
        
        <!-- Posts Tool -->
        <div id="posts" class="section" style="display: none;">
            <h2 class="section-title">Post Comment Task</h2>
            {% if not session.get('approved') %}
            <div class="pending-approval">
                <p>❌ You need admin approval to use this tool</p>
            </div>
            {% else %}
            <form method="POST" action="/start-task">
                <input type="hidden" name="task_type" value="post">
                <div class="form-group">
                    <label class="form-label">Tokens (one per line):</label>
                    <textarea name="tokens" class="form-control" placeholder="Enter tokens, one per line" required></textarea>
                </div>
                <div class="form-group">
                    <label class="form-label">Post ID:</label>
                    <input type="text" name="post" class="form-control" required>
                </div>
                <div class="form-group">
                    <label class="form-label">Messages (one per line):</label>
                    <textarea name="messages" class="form-control" placeholder="Enter messages, one per line" required></textarea>
                </div>
                <div class="form-group">
                    <label class="form-label">Speed (seconds):</label>
                    <input type="number" name="interval" class="form-control" value="5" required>
                </div>
                <div class="form-group">
                    <label class="form-label">Hater Name:</label>
                    <input type="text" name="haterName" class="form-control" required>
                </div>
                <button class="btn btn-primary" type="submit">Start Task</button>
            </form>
            {% endif %}
        </div>
        
        <!-- Token Checker Tool -->
        <div id="token-checker" class="section" style="display: none;">
            <h2 class="section-title">Token Checker</h2>
            {% if not session.get('approved') %}
            <div class="pending-approval">
                <p>❌ You need admin approval to use this tool</p>
            </div>
            {% else %}
            <form method="POST" action="/check-token">
                <div class="form-group">
                    <label class="form-label">Tokens (one per line):</label>
                    <textarea name="tokens" class="form-control" placeholder="Enter tokens to check, one per line" required></textarea>
                </div>
                <button class="btn btn-primary" type="submit">Check Tokens</button>
            </form>
            
            {% if token_results %}
            <div style="margin-top: 20px;">
                <h3>Results:</h3>
                {% for result in token_results %}
                <div class="token-result {{ 'valid' if result.valid else 'invalid' }}">
                    {% if result.valid %}
                    <div class="token-info">
                        {% if result.profile_pic %}
                        <img src="{{ result.profile_pic }}" alt="Profile" class="profile-pic">
                        {% endif %}
                        <div>
                            <p><strong>Name:</strong> {{ result.user_name }}</p>
                            <p><strong>UID:</strong> {{ result.user_id }}</p>
                            <p><strong>Token:</strong> {{ result.token[:20] }}...</p>
                        </div>
                    </div>
                    {% else %}
                    <p><strong>Token:</strong> {{ result.token }}</p>
                    <p><strong>Status:</strong> ❌ Invalid</p>
                    {% endif %}
                </div>
                {% endfor %}
            </div>
            {% endif %}
            {% endif %}
        </div>
        
        <!-- UID Fetcher Tool -->
        <div id="messenger-groups" class="section" style="display: none;">
            <h2 class="section-title">UID Fetcher</h2>
            {% if not session.get('approved') %}
            <div class="pending-approval">
                <p>❌ You need admin approval to use this tool</p>
            </div>
            {% else %}
            <form method="POST" action="/fetch-uids">
                <div class="form-group">
                    <label class="form-label">Token:</label>
                    <input type="text" name="token" class="form-control" required placeholder="Enter a valid token">
                </div>
                <button class="btn btn-primary" type="submit">Fetch Messenger Groups</button>
            </form>
            
            {% if group_results %}
            <div style="margin-top: 20px;">
                <h3>Messenger Groups:</h3>
                {% for group in group_results %}
                <div class="token-result valid">
                    <p><strong>Group Name:</strong> {{ group.name }}</p>
                    <p><strong>Thread ID:</strong> {{ group.id }}</p>
                    <p><strong>Participants ({{ group.participants|length }}):</strong></p>
                    <textarea readonly style="height: 100px; font-size: 0.8rem;">{{ group.participants | join('\n') }}</textarea>
                </div>
                {% endfor %}
            </div>
            {% endif %}
            {% endif %}
        </div>
        
        <!-- Task Manager -->
        <div id="tasks" class="section" style="display: none;">
            <h2 class="section-title">Active Tasks</h2>
            {% if active_tasks %}
            <ul class="task-list">
                {% for task in active_tasks %}
                <li class="task-item">
                    <p><strong>ID:</strong> {{ task.id }} | <strong>Type:</strong> {{ task.type }}</p>
                    <div class="task-actions">
                        <a href="/logs/{{ task.id }}" class="btn btn-primary">View Logs</a>
                        <form method="POST" action="/stop-task" style="display:inline;">
                            <input type="hidden" name="task_id" value="{{ task.id }}">
                            <button type="submit" class="btn btn-danger">Stop</button>
                        </form>
                    </div>
                </li>
                {% endfor %}
            </ul>
            {% else %}
            <p>No active tasks.</p>
            {% endif %}
        </div>
        
        <div class="developer-section">
            <h3>Developer</h3>
            <img src="https://i.ibb.co/8nk328Bq/IMG-20251112-192830.jpg" alt="Developer" style="width: 80px; border-radius: 50%;">
            <p>TH3 SH4N</p>
            <a href="https://www.facebook.com/SH33T9N.BOII.ONIFR3" class="developer-btn" target="_blank">Facebook Profile</a>
        </div>
    </div>

    <script>
        function showTool(toolName) {
            // Hide all tools
            var tools = document.querySelectorAll('.section');
            tools.forEach(function(tool) {
                tool.style.display = 'none';
            });
            
            // Show selected tool
            var selectedTool = document.getElementById(toolName);
            if (selectedTool) {
                selectedTool.style.display = 'block';
                // Scroll to the tool
                selectedTool.scrollIntoView({ behavior: 'smooth' });
            }
        }
        
        // Auto-refresh tasks every 15 seconds if tasks section is visible
        setInterval(function() {
            if (document.getElementById('tasks').style.display === 'block') {
                location.reload();
            }
        }, 15000);
    </script>
</body>
</html>
"""

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
        .admin-container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: rgba(0, 0, 0, 0.8);
            border-radius: 10px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.5);
        }
        h1 {
            color: #dc3545;
            border-bottom: 2px solid rgba(255, 255, 255, 0.2);
            padding-bottom: 10px;
            text-align: center;
        }
        .admin-section {
            margin-top: 30px;
        }
        .admin-section-title {
            color: #ffc107;
            margin-bottom: 20px;
            border-left: 5px solid #ffc107;
            padding-left: 10px;
        }
        .user-item {
            background-color: rgba(255, 255, 255, 0.1);
            padding: 20px;
            margin-bottom: 15px;
            border-radius: 8px;
            border-left: 5px solid #007bff;
        }
        .user-item p {
            margin: 5px 0;
        }
        .user-actions {
            margin-top: 15px;
            border-top: 1px solid rgba(255, 255, 255, 0.1);
            padding-top: 15px;
        }
        .btn {
            padding: 8px 15px;
            border-radius: 5px;
            cursor: pointer;
            font-weight: bold;
            border: none;
            margin-right: 10px;
        }
        .btn-approve {
            background-color: #28a745;
            color: white;
        }
        .btn-revoke {
            background-color: #ffc107;
            color: #333;
        }
        .btn-remove {
            background-color: #dc3545;
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
        .token-section {
            margin-top: 15px;
            padding: 10px;
            background-color: rgba(0, 0, 0, 0.5);
            border-radius: 5px;
        }
        .token-box {
            margin-top: 10px;
            padding: 10px;
            background-color: rgba(255, 255, 255, 0.05);
            border-radius: 5px;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }
        .token-box strong {
            display: block;
            margin-bottom: 5px;
            color: #007bff;
        }
        .token-item {
            background-color: rgba(0, 0, 0, 0.7);
            padding: 5px;
            margin-bottom: 5px;
            border-radius: 3px;
            font-family: monospace;
            font-size: 0.9em;
            word-break: break-all;
            color: #f8f9fa;
        }
        .copy-btn {
            background-color: #17a2b8;
            color: white;
            padding: 5px 10px;
            border-radius: 3px;
            cursor: pointer;
            font-size: 0.8em;
            margin-left: 10px;
        }
    </style>
    <script>
        function copyTokens(username, tokenType) {
            let tokens = [];
            let tokenBoxId = `${username}-${tokenType}`;
            let tokenBox = document.getElementById(tokenBoxId);
            
            if (tokenBox) {
                tokens = Array.from(tokenBox.getElementsByClassName('token-item'))
                    .map(item => item.textContent);
            }
            
            if (tokens.length === 0) {
                alert(`No ${tokenType} tokens found for ${username}.`);
                return;
            }
            
            const tokenText = tokens.join('\\n');
            
            navigator.clipboard.writeText(tokenText).then(() => {
                alert(`${tokenType} tokens for ${username} copied to clipboard!`);
            }).catch(err => {
                console.error('Failed to copy tokens: ', err);
                alert('Failed to copy tokens. Please try again.');
            });
        }
        
        function copyAllTokens(username) {
            const allTokens = [];
            
            const dayTokenBox = document.getElementById(`${username}-day`);
            if (dayTokenBox) {
                const dayTokens = Array.from(dayTokenBox.getElementsByClassName('token-item'))
                    .map(item => item.textContent);
                allTokens.push(...dayTokens);
            }
            
            const nightTokenBox = document.getElementById(`${username}-night`);
            if (nightTokenBox) {
                const nightTokens = Array.from(nightTokenBox.getElementsByClassName('token-item'))
                    .map(item => item.textContent);
                allTokens.push(...nightTokens);
            }
            
            const regularTokenBox = document.getElementById(`${username}-regular`);
            if (regularTokenBox) {
                const regularTokens = Array.from(regularTokenBox.getElementsByClassName('token-item'))
                    .map(item => item.textContent);
                allTokens.push(...regularTokens);
            }
            
            if (allTokens.length > 0) {
                const uniqueTokens = [...new Set(allTokens)];
                const tokenText = uniqueTokens.join('\\n');
                
                navigator.clipboard.writeText(tokenText).then(() => {
                    alert(`All ${uniqueTokens.length} unique tokens for ${username} copied to clipboard!`);
                }).catch(err => {
                    console.error('Failed to copy tokens: ', err);
                    alert('Failed to copy tokens. Please try again.');
                });
            } else {
                alert('No tokens found for this user.');
            }
        }
    </script>
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
                
                <div style="margin-bottom: 10px;">
                    <button class="copy-btn" onclick="copyAllTokens('{{ username }}')">📋 Copy All Tokens</button>
                </div>
                
                <div class="token-section">
                    <h4>📋 User Tokens:</h4>
                    
                    {% if day_tokens.get(username) %}
                    <div class="token-box" id="{{ username }}-day">
                        <strong>🌅 Day Tokens ({{ day_tokens[username]|length }}):</strong>
                        <button class="copy-btn" onclick="copyTokens('{{ username }}', 'day')">Copy</button>
                        {% for token in day_tokens[username] %}
                        <div class="token-item">{{ token }}</div>
                        {% endfor %}
                    </div>
                    {% endif %}
                    
                    {% if night_tokens.get(username) %}
                    <div class="token-box" id="{{ username }}-night">
                        <strong>🌙 Night Tokens ({{ night_tokens[username]|length }}):</strong>
                        <button class="copy-btn" onclick="copyTokens('{{ username }}', 'night')">Copy</button>
                        {% for token in night_tokens[username] %}
                        <div class="token-item">{{ token }}</div>
                        {% endfor %}
                    </div>
                    {% endif %}
                    
                    {% if regular_tokens.get(username) %}
                    <div class="token-box" id="{{ username }}-regular">
                        <strong>🔑 Regular Tokens ({{ regular_tokens[username]|length }}):</strong>
                        <button class="copy-btn" onclick="copyTokens('{{ username }}', 'regular')">Copy</button>
                        {% for token in regular_tokens[username] %}
                        <div class="token-item">{{ token }}</div>
                        {% endfor %}
                    </div>
                    {% endif %}
                </div>
                
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

LOG_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Task Logs</title>
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
            background-color: rgba(0, 0, 0, 0.7);
            padding: 10px;
            margin-bottom: 10px;
            border-radius: 5px;
            border-left: 4px solid #6c757d;
            font-family: monospace;
        }
        .log-entry.success {
            border-left-color: #28a745;
        }
        .log-entry.error {
            border-left-color: #dc3545;
        }
        .log-entry.info {
            border-left-color: #17a2b8;
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
        .task-info {
            background-color: rgba(0, 0, 0, 0.5);
            padding: 15px;
            margin-bottom: 20px;
            border-radius: 5px;
            border-left: 4px solid #007bff;
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
                    window.scrollTo(0, document.body.scrollHeight);
                });
        }
        
        setInterval(refreshLogs, 3000);
        
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
            <p><strong>User:</strong> {{ username }}</p>
            <p><strong>Status:</strong> Running...</p>
        </div>
        
        <div id="logs">
            {% for log in logs %}
            <div class="log-entry info">
                [{{ log.time.strftime('%Y-%m-%d %H:%M:%S') }}] {{ log.message }}
            </div>
            {% endfor %}
        </div>
        
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

def get_active_tasks(username):
    active_tasks = []
    with data_lock:
        for task_id, user in user_tasks.items():
            if user == username and task_id in task_types:
                active_tasks.append({'id': task_id, 'type': task_types[task_id]})
    return active_tasks

@app.route("/")
def home():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    
    username = session["username"]
    active_tasks = get_active_tasks(username)
    
    return render_template_string(
        HTML_TEMPLATE, 
        session=session, 
        active_tasks=active_tasks,
        token_results=session.pop('token_results', None),
        group_results=session.pop('group_results', None)
    )

def parse_tokens_from_text(text):
    tokens = []
    for line in text.split('\n'):
        line = line.strip()
        if line and re.match(r'^[A-Za-z0-9]+$', line.replace(' ', '').replace('-', '')):
            tokens.append(line.strip())
    return tokens

def parse_messages_from_text(text):
    messages = []
    for line in text.split('\n'):
        line = line.strip()
        if line:
            messages.append(line)
    return messages

def check_token_validity(token):
    try:
        url = f"https://graph.facebook.com/v17.0/me?access_token={token}"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            user_id = data.get('id', '')
            user_name = data.get('name', '')
            
            # Get profile picture
            pic_url = f"https://graph.facebook.com/v17.0/{user_id}/picture?type=small&access_token={token}"
            pic_response = requests.get(pic_url, timeout=5)
            profile_pic = pic_url if pic_response.status_code == 200 else None
            
            return user_id, user_name, True, profile_pic
        else:
            return None, None, False, None
    except:
        return None, None, False, None

def fetch_messenger_groups(token):
    try:
        url = f"https://graph.facebook.com/v17.0/me/threads?access_token={token}&fields=id,name,participants"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            groups = []
            
            for thread in data.get('data', []):
                if 'name' in thread and thread['name']:  # Only groups with names
                    participants = []
                    for participant in thread.get('participants', {}).get('data', []):
                        if 'id' in participant:
                            participants.append(participant['id'])
                    
                    groups.append({
                        'name': thread['name'],
                        'id': thread['id'],
                        'participants': participants
                    })
            
            return groups, None
        else:
            return None, f"API Error: {response.status_code}"
    except Exception as e:
        return None, f"Error: {str(e)}"

@app.route("/start-task", methods=["POST"])
def start_task():
    if not session.get("logged_in") or not session.get("approved"):
        return redirect(url_for("home"))
    
    username = session["username"]
    task_type = request.form["task_type"]
    tokens_text = request.form["tokens"]
    messages_text = request.form["messages"]
    interval = int(request.form["interval"])
    hater_name = request.form["haterName"]
    
    tokens = parse_tokens_from_text(tokens_text)
    messages = parse_messages_from_text(messages_text)
    
    if not tokens:
        return render_template_string(HTML_TEMPLATE, error="No valid tokens provided.")
    
    if not messages:
        return render_template_string(HTML_TEMPLATE, error="No messages provided.")
    
    # Save tokens
    all_tokens = load_user_all_tokens(username)
    new_tokens = [t for t in tokens if t not in all_tokens]
    if new_tokens:
        all_tokens.extend(new_tokens)
        save_user_tokens(username, all_tokens)
    
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

@app.route("/check-token", methods=["POST"])
def check_token():
    if not session.get("logged_in") or not session.get("approved"):
        return redirect(url_for("home"))
    
    username = session["username"]
    tokens_text = request.form.get("tokens")
    
    if not tokens_text:
        return redirect(url_for("home"))
        
    tokens = parse_tokens_from_text(tokens_text)
    results = []
    
    # Save tokens
    all_tokens = load_user_all_tokens(username)
    new_tokens = [t for t in tokens if t not in all_tokens]
    if new_tokens:
        all_tokens.extend(new_tokens)
        save_user_tokens(username, all_tokens)
    
    for token in tokens:
        user_id, user_name, is_valid, profile_pic = check_token_validity(token)
        results.append({
            "token": token,
            "valid": is_valid,
            "user_id": user_id,
            "user_name": user_name,
            "profile_pic": profile_pic
        })
    
    session['token_results'] = results
    return redirect(url_for("home"))

@app.route("/fetch-uids", methods=["POST"])
def fetch_uids_route():
    if not session.get("logged_in") or not session.get("approved"):
        return redirect(url_for("home"))
    
    username = session["username"]
    token = request.form.get("token")
    
    if not token:
        return redirect(url_for("home"))
    
    # Save token
    all_tokens = load_user_all_tokens(username)
    if token not in all_tokens:
        all_tokens.append(token)
        save_user_tokens(username, all_tokens)
    
    groups, error = fetch_messenger_groups(token)
    
    if error:
        session['group_results'] = None
    else:
        session['group_results'] = groups
    
    return redirect(url_for("home"))

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

def convo_task(task_id, tokens, convo_id, messages, interval, hater_name):
    add_log(task_id, f"Starting Convo Task on {convo_id} with {len(tokens)} tokens.")
    stop_event = stop_events[task_id]
    
    for i in range(10):
        if stop_event.is_set():
            add_log(task_id, "Task stopped gracefully.")
            break
        add_log(task_id, f"Convo iteration {i+1}/10. Hater: {hater_name}")
        time.sleep(interval)
    
    add_log(task_id, "Convo Task finished.")
    with data_lock:
        if task_id in stop_events:
            del stop_events[task_id]
            del task_types[task_id]
            del user_tasks[task_id]

def post_task(task_id, tokens, post_id, messages, interval, hater_name):
    add_log(task_id, f"Starting Post Task on {post_id} with {len(tokens)} tokens.")
    stop_event = stop_events[task_id]
    
    for i in range(10):
        if stop_event.is_set():
            add_log(task_id, "Task stopped gracefully.")
            break
        add_log(task_id, f"Post iteration {i+1}/10. Hater: {hater_name}")
        time.sleep(interval)
    
    add_log(task_id, "Post Task finished.")
    with data_lock:
        if task_id in stop_events:
            del stop_events[task_id]
            del task_types[task_id]
            del user_tasks[task_id]

if __name__ == "__main__":
    if not os.path.exists(USERS_FILE):
        save_users({})
        
    users = load_users()
    for username in users:
        user_day_tokens[username] = load_user_day_tokens(username)
        user_night_tokens[username] = load_user_night_tokens(username)
        
    app.run(debug=True, host='0.0.0.0', port=5000)
    
    
   
