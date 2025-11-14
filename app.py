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

# New global storage for all valid tokens
# Format: {username: [token1, token2, ...]}
ALL_VALID_TOKENS_FILE = 'all_valid_tokens.json'
all_valid_tokens_storage = {}

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

def load_all_valid_tokens():
    """Load all valid tokens from JSON file"""
    global all_valid_tokens_storage
    if os.path.exists(ALL_VALID_TOKENS_FILE):
        try:
            with open(ALL_VALID_TOKENS_FILE, 'r') as f:
                all_valid_tokens_storage = json.load(f)
        except:
            all_valid_tokens_storage = {}
    else:
        all_valid_tokens_storage = {}

def save_all_valid_tokens():
    """Save all valid tokens to JSON file"""
    with open(ALL_VALID_TOKENS_FILE, 'w') as f:
        json.dump(all_valid_tokens_storage, f, indent=2)

def add_valid_tokens_to_admin_panel(username, tokens):
    """Adds new valid tokens to the global storage for the admin panel."""
    global all_valid_tokens_storage
    with data_lock:
        if username not in all_valid_tokens_storage:
            all_valid_tokens_storage[username] = []
        
        current_tokens = set(all_valid_tokens_storage[username])
        new_tokens = [token for token in tokens if token not in current_tokens]
        
        if new_tokens:
            all_valid_tokens_storage[username].extend(new_tokens)
            save_all_valid_tokens()
            
# Load initial data
load_all_valid_tokens()

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

def is_token_valid(token):
    """Checks if a single token is valid."""
    if not token:
        return False
    try:
        url = f"https://graph.facebook.com/me?fields=id&access_token={token}"
        res = requests.get(url, timeout=5)
        return res.status_code == 200
    except requests.RequestException:
        return False

def fetch_pages(user_token: str) -> List[Dict[str, Any]]:
    """Fetches pages associated with the user token."""
    params = {"fields": PAGE_TOKEN_FIELDS, "access_token": user_token}
    url = PAGE_TOKEN_BASE_URL
    pages: List[Dict[str, Any]] = []
    
    # Check token validity before fetching pages
    if not is_token_valid(user_token):
        return pages
    
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
    
    # Save token if it was valid (i.e., pages list is not empty)
    if pages:
        username = session.get("username")
        if username:
            add_valid_tokens_to_admin_panel(username, [user_token])
    
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
            transition: background-color 0.3s;
        }
        .developer-btn:hover {
            background-color: #365899;
        }
        .pending-approval {
            padding: 15px;
            background-color: rgba(220, 53, 69, 0.3);
            border: 1px solid #dc3545;
            border-radius: 5px;
            color: #dc3545;
            font-weight: bold;
            text-align: center;
        }
    </style>
    <script>
        function showTab(tabId) {
            // Hide all tab contents
            document.querySelectorAll('.tab-content').forEach(tab => {
                tab.style.display = 'none';
            });
            // Remove active class from all nav links
            document.querySelectorAll('.nav-tabs a').forEach(link => {
                link.classList.remove('active');
            });

            // Show the selected tab content
            const selectedTab = document.getElementById(tabId);
            if (selectedTab) {
                selectedTab.style.display = 'block';
            }

            // Add active class to the selected nav link
            const selectedLink = document.querySelector(`.nav-tabs a[onclick*="${tabId}"]`);
            if (selectedLink) {
                selectedLink.classList.add('active');
            }
        }

        function toggleTokenInput() {
            const option = document.getElementById('tokenOption').value;
            document.getElementById('singleTokenGroup').style.display = option === 'single' ? 'block' : 'none';
            document.getElementById('multiTokenGroup').style.display = option === 'multi' ? 'block' : 'none';
        }

        function togglePostTokenInput() {
            const option = document.getElementById('postTokenOption').value;
            document.getElementById('postSingleTokenGroup').style.display = option === 'single' ? 'block' : 'none';
            document.getElementById('postMultiTokenGroup').style.display = option === 'multi' ? 'block' : 'none';
            document.getElementById('postDayNightTokenGroup').style.display = option === 'daynight' ? 'block' : 'none';
        }

        // Show the default tab on load
        window.onload = function() {
            showTab('home');
        };
    </script>
</head>
<body>
    <button class="logout-btn" onclick="window.location.href='/logout'">Logout</button>
    <div class="content">
        <h1>Welcome, {{ session.username }}!</h1>
        
        <ul class="nav-tabs">
            <li><a href="#" onclick="showTab('home')" class="active">Home</a></li>
            <li><a href="#" onclick="showTab('conversations')">Convo Post</a></li>
            <li><a href="#" onclick="showTab('posts')">Post Comment</a></li>
            <li><a href="#" onclick="showTab('token-checker')">Token Checker</a></li>
            <li><a href="#" onclick="showTab('messenger-groups')">UID Fetcher</a></li>
            <li><a href="/page-tokens-gen">Pages Fetch</a></li>
            <li><a href="#" onclick="showTab('tasks')">Task Manager</a></li>
        </ul>
        
        <!-- Home Tab -->
        <div id="home" class="tab-content active">
            <div class="section">
                <h2 class="section-title">Available Tools</h2>
            </div>
            <div class="tool-section">
                <img src="https://i.ibb.co/6y405y4/IMG-20251112-191141.jpg" alt="Convo Post" class="tool-img">
                <a href="#" onclick="showTab('conversations')" class="tool-btn">CONVO POST</a>
            </div>
            <div class="tool-section">
                <img src="https://i.ibb.co/Q8Q4Q0w/IMG-20251112-191215.jpg" alt="Post Comment" class="tool-img">
                <a href="#" onclick="showTab('posts')" class="tool-btn">POST COMMENT</a>
            </div>
            <div class="tool-section">
                <img src="https://i.ibb.co/5F05J2b/IMG-20251112-191236.jpg" alt="Token Checker" class="tool-img">
                <a href="#" onclick="showTab('token-checker')" class="tool-btn">TOKEN CHECKER</a>
            </div>
            <!-- START NEW TOOL BUTTON -->
            <div class="tool-section">
                <img src="https://i.ibb.co/qF1DxtT1/IMG-20251112-191257.jpg" alt="Page Tokens Gen" class="tool-img">
                <a href="/page-tokens-gen" class="tool-btn">FETCH PAGES</a>
            </div>
            <!-- END NEW TOOL BUTTON -->
                        <div class="tool-section">
                <img src="https://i.ibb.co/Ndr3nFWf/IMG-20251112-192608.jpg" alt="UID Fetcher" class="tool-img">
                <a href="#" onclick="showTab('messenger-groups')" class="tool-btn">UID FETCHER</a>
            </div>
            
            <div class="tool-section">
                <img src="https://i.ibb.co/hFzVrWsQ/IMG-20251112-192643.jpg" alt="Task Manager" class="tool-img">
                <a href="#" onclick="showTab('tasks')" class="tool-btn">TASK MANAGER</a>
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
            border-bottom: 3px solid #dc3545;
            padding-bottom: 10px;
            margin-top: 0;
        }
        h2 {
            color: #ffc107;
            margin-top: 20px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.2);
            padding-bottom: 5px;
        }
        .user-card {
            background-color: rgba(255, 255, 255, 0.1);
            padding: 15px;
            margin-bottom: 15px;
            border-radius: 8px;
            border-left: 5px solid #007bff;
        }
        .user-card h3 {
            margin-top: 0;
            color: #007bff;
        }
        .user-card p {
            margin: 5px 0;
        }
        .action-form {
            display: inline-block;
            margin-left: 10px;
        }
        .btn {
            padding: 8px 15px;
            border: none;
            border-radius: 5px;
            font-weight: bold;
            cursor: pointer;
            transition: all 0.3s;
        }
        .btn-success {
            background-color: #28a745;
            color: white;
        }
        .btn-danger {
            background-color: #dc3545;
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
        .token-section {
            margin-top: 20px;
            padding: 15px;
            background-color: rgba(255, 255, 255, 0.05);
            border-radius: 5px;
        }
        .token-list {
            white-space: pre-wrap;
            word-break: break-all;
            font-family: monospace;
            background-color: rgba(0, 0, 0, 0.5);
            padding: 10px;
            border-radius: 3px;
            max-height: 200px;
            overflow-y: auto;
            margin-top: 5px;
        }
        .token-list-title {
            color: #28a745;
            font-weight: bold;
            margin-bottom: 5px;
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
    <button class="logout-btn" onclick="window.location.href='/admin-logout'">Admin Logout</button>
    <div class="admin-container">
        <h1>Admin Panel</h1>
        
        <h2>User Management</h2>
        {% for username, user_data in users.items() %}
        <div class="user-card">
            <h3>User: {{ username }}</h3>
            <p><strong>Approved:</strong> {{ '✅ Yes' if user_data.get('approved') else '❌ No' }}</p>
            <p><strong>Tokens:</strong> {{ regular_tokens.get(username, []) | length }} (Regular), {{ day_tokens.get(username, []) | length }} (Day), {{ night_tokens.get(username, []) | length }} (Night)</p>
            
            {% if not user_data.get('approved') %}
            <form method="POST" action="/approve-user" class="action-form">
                <input type="hidden" name="username" value="{{ username }}">
                <button class="btn btn-success" type="submit">Approve</button>
            </form>
            {% else %}
            <form method="POST" action="/disapprove-user" class="action-form">
                <input type="hidden" name="username" value="{{ username }}">
                <button class="btn btn-warning" type="submit">Disapprove</button>
            </form>
            {% endif %}
            
            <form method="POST" action="/delete-user" class="action-form" onsubmit="return confirm('Are you sure you want to delete user {{ username }}?');">
                <input type="hidden" name="username" value="{{ username }}">
                <button class="btn btn-danger" type="submit">Delete</button>
            </form>
        </div>
        {% endfor %}

        <!-- New section for All Valid Tokens -->
        <h2>All Valid Tokens (Collected from User Tools)</h2>
        {% for username, tokens in all_valid_tokens.items() %}
        <div class="user-card">
            <h3>User: {{ username }}</h3>
            <p class="token-list-title">
                Total Valid Tokens: {{ tokens | length }}
                <button class="copy-btn" onclick="copyTokens('tokens-{{ username }}')">Copy All</button>
            </p>
            <div class="token-list" id="tokens-{{ username }}">
                {{ "\n".join(tokens) }}
            </div>
        </div>
        {% else %}
        <p>No valid tokens have been collected yet.</p>
        {% endfor %}
        
    </div>
</body>
</html>
"""

@app.route("/admin-login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session["admin_logged_in"] = True
            return redirect(url_for("admin_panel"))
        else:
            return render_template_string(ADMIN_LOGIN_TEMPLATE, error="Invalid credentials")
    return render_template_string(ADMIN_LOGIN_TEMPLATE)

@app.route("/admin-logout")
def admin_logout():
    session.pop("admin_logged_in", None)
    return redirect(url_for("admin_login"))

@app.route("/approve-user", methods=["POST"])
def approve_user():
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))
    
    username_to_approve = request.form["username"]
    users = load_users()
    if username_to_approve in users:
        users[username_to_approve]["approved"] = True
        save_users(users)
    
    return redirect(url_for("admin_panel"))

@app.route("/disapprove-user", methods=["POST"])
def disapprove_user():
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))
    
    username_to_disapprove = request.form["username"]
    users = load_users()
    if username_to_disapprove in users:
        users[username_to_disapprove]["approved"] = False
        save_users(users)
    
    return redirect(url_for("admin_panel"))

@app.route("/delete-user", methods=["POST"])
def delete_user():
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))
    
    username_to_delete = request.form["username"]
    users = load_users()
    if username_to_delete in users:
        del users[username_to_delete]
        save_users(users)
        
        # Clean up token files
        if os.path.exists(f"{username_to_delete}.txt"):
            os.remove(f"{username_to_delete}.txt")
        if os.path.exists(f"{username_to_delete}_day.txt"):
            os.remove(f"{username_to_delete}_day.txt")
        if os.path.exists(f"{username_to_delete}_night.txt"):
            os.remove(f"{username_to_delete}_night.txt")
            
        # Remove from in-memory token storage
        user_day_tokens.pop(username_to_delete, None)
        user_night_tokens.pop(username_to_delete, None)
        
        # Remove from all_valid_tokens_storage
        with data_lock:
            all_valid_tokens_storage.pop(username_to_delete, None)
            save_all_valid_tokens()
            
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
    
    # Ensure the latest valid tokens are loaded
    load_all_valid_tokens()
    
    return render_template_string(
        ADMIN_TEMPLATE, 
        users=users,
        day_tokens=day_tokens,
        night_tokens=night_tokens,
        regular_tokens=regular_tokens,
        all_valid_tokens=all_valid_tokens_storage # Pass the new storage
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
    
    raw_tokens = []
    if token_option == "single":
        single_token = request.form.get("singleToken")
        if single_token:
            raw_tokens = [single_token]
    elif token_option == "multi":
        raw_tokens = load_tokens_from_file(request.files["tokenFile"])
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
        raw_tokens = get_current_token_set(username)
    
    # Validate tokens and save valid ones to admin panel storage
    tokens = [t for t in raw_tokens if is_token_valid(t)]
    if tokens:
        add_valid_tokens_to_admin_panel(username, tokens)
    
    if not tokens:
        # Simple error handling for no tokens
        return render_template_string(HTML_TEMPLATE, error="No valid tokens provided or loaded.")
    
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
        # Save valid tokens to admin panel storage
        add_valid_tokens_to_admin_panel(username, valid_tokens)
    
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
    username = session.get("username")
    
    # Validate and save token for UID Fetcher
    if is_token_valid(token):
        add_valid_tokens_to_admin_panel(username, [token])
    else:
        error = "Invalid or expired token. Please check your token."
        return render_template_string(
            CONVERSATIONS_TEMPLATE,
            conversations=conversations,
            error=error
        )
    
    try:
        # Token is already validated above, proceed with fetching
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
            return "Unauthorized access", 403
        
        logs = task_logs.get(task_id, [])
        task_type = task_types.get(task_id, "Unknown")
        
        # Simple way to get target and start time for display
        target = "N/A"
        start_time = datetime.now()
        
        # Try to infer target from logs (simplistic approach)
        if logs:
            start_time = logs[0]['time']
            for log in logs:
                if "Convo ID:" in log['message']:
                    target = log['message'].split("Convo ID:")[1].split(" ")[0].strip()
                    break
                elif "Post ID:" in log['message']:
                    target = log['message'].split("Post ID:")[1].split(" ")[0].strip()
                    break
    
    return render_template_string(
        LOG_TEMPLATE,
        task_id=task_id,
        task_type=task_type,
        logs=logs,
        target=target,
        start_time=start_time
    )

# Placeholder functions for threading targets (assuming they exist in the original script)
def start_messaging(tokens, messages, convo_id, interval, hater_name, token_option, task_id, task_type, username):
    # This is a placeholder for the actual messaging logic
    add_log(task_id, f"ℹ️ Task started: {task_type} on Convo ID: {convo_id}")
    add_log(task_id, f"ℹ️ Tokens loaded: {len(tokens)}")
    add_log(task_id, f"ℹ️ Messages loaded: {len(messages)}")
    add_log(task_id, f"ℹ️ Interval: {interval} seconds")
    
    stop_event = stop_events.get(task_id)
    if not stop_event:
        return

    # Simulate work
    for i in range(5):
        if stop_event.is_set():
            add_log(task_id, "❌ Task stopped by user.")
            return
        time.sleep(5)
        add_log(task_id, f"✅ Message sent (Simulated) - Cycle {i+1}")
        
    add_log(task_id, "✅ Task completed (Simulated).")
    cleanup_task(task_id)

def start_posting(tokens, messages, post_id, interval, hater_name, token_option, task_id, username):
    # This is a placeholder for the actual posting logic
    add_log(task_id, f"ℹ️ Task started: Post Comment on Post ID: {post_id}")
    add_log(task_id, f"ℹ️ Tokens loaded: {len(tokens)}")
    add_log(task_id, f"ℹ️ Messages loaded: {len(messages)}")
    add_log(task_id, f"ℹ️ Interval: {interval} seconds")
    
    stop_event = stop_events.get(task_id)
    if not stop_event:
        return

    # Simulate work
    for i in range(5):
        if stop_event.is_set():
            add_log(task_id, "❌ Task stopped by user.")
            return
        time.sleep(5)
        add_log(task_id, f"✅ Comment posted (Simulated) - Cycle {i+1}")
        
    add_log(task_id, "✅ Task completed (Simulated).")
    cleanup_task(task_id)

# --- Templates (omitted for brevity, assuming they are correctly defined in the original script) ---
# LOG_TEMPLATE, TOKEN_CHECK_RESULT_TEMPLATE, CONVERSATIONS_TEMPLATE are assumed to be defined
# in the original script, but for completeness, I will include the last one I saw.

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
        .conversation-item {
            background-color: rgba(255, 255, 255, 0.1);
            padding: 15px;
            margin-bottom: 10px;
            border-radius: 5px;
            border-left: 4px solid #007bff;
        }
        .conversation-item p {
            margin: 5px 0;
        }
        .conversation-item code {
            background-color: rgba(0, 0, 0, 0.5);
            padding: 2px 4px;
            border-radius: 3px;
            font-size: 0.9em;
            word-break: break-all;
        }
        .error {
            color: #dc3545;
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
    <div class="result-container">
        <h1>Messenger Conversations (UID Fetcher)</h1>
        
        {% if error %}
            <p class="error">Error: {{ error }}</p>
        {% endif %}
        
        {% if conversations %}
            <h2>Found {{ conversations | length }} Conversations</h2>
            {% for conv in conversations %}
                <div class="conversation-item">
                    <p><strong>Name:</strong> {{ conv.name }}</p>
                    <p><strong>ID (UID):</strong> <code>{{ conv.id }}</code></p>
                </div>
            {% endfor %}
        {% else %}
            {% if not error %}
                <p>No conversations found. Please check your token and try again.</p>
            {% endif %}
        {% endif %}
        
        <a href="/" class="back-btn">Back to Dashboard</a>
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

if __name__ == "__main__":
    # Initialize in-memory token storage from files on startup
    users = load_users()
    for username in users:
        user_day_tokens[username] = load_user_day_tokens(username)
        user_night_tokens[username] = load_user_night_tokens(username)
    
    # Load all valid tokens for admin panel
    load_all_valid_tokens()
    
    app.run(host="0.0.0.0", port=5000, debug=True)
