from flask import Flask, request, render_template_string, redirect, session, url_for
import threading, time, requests, pytz
from datetime import datetime, timedelta
import uuid
import os
import json
from threading import Lock
from typing import List, Dict, Any

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
            padding: 10px 15px;
            background-color: #dc3545;
            color: white;
            text-decoration: none;
            border-radius: 4px;
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
        .admin-login-container {
            background-color: rgba(255, 255, 255, 0.9);
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 4px 10px rgba(0, 0, 0, 0.2);
            width: 350px;
            text-align: center;
        }
        .admin-login-container h2 {
            margin-bottom: 20px;
            color: #dc3545;
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
        .admin-login-btn {
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
        .admin-login-btn:hover {
            background-color: #c82333;
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
    <div class="admin-login-container">
        <h2>Admin Login</h2>
        <form method="POST" action="/admin-login">
            <div class="form-group">
                <label for="username">Admin Username:</label>
                <input type="text" id="username" name="username" required>
            </div>
            <div class="form-group">
                <label for="password">Admin Password:</label>
                <input type="password" id="password" name="password" required>
            </div>
            <button type="submit" class="admin-login-btn">Admin Login</button>
            {% if error %}
            <div class="error-message">{{ error }}</div>
            {% endif %}
        </form>
        <a href="/login" class="back-link">Back to User Login</a>
    </div>
</body>
</html>
"""

TOKEN_CHECKER_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Token Checker Results</title>
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
            max-width: 1000px;
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
        .token-result {
            background-color: rgba(255, 255, 255, 0.1);
            padding: 15px;
            margin-bottom: 15px;
            border-radius: 5px;
            display: flex;
            align-items: center;
            gap: 15px;
        }
        .token-result.valid {
            border-left: 5px solid #28a745;
        }
        .token-result.invalid {
            border-left: 5px solid #dc3545;
        }
        .profile-pic {
            width: 80px;
            height: 80px;
            border-radius: 50%;
            object-fit: cover;
        }
        .token-info {
            flex: 1;
        }
        .token-info p {
            margin: 5px 0;
        }
        .status-badge {
            padding: 5px 10px;
            border-radius: 3px;
            font-weight: bold;
            display: inline-block;
        }
        .status-badge.valid {
            background-color: #28a745;
            color: white;
        }
        .status-badge.invalid {
            background-color: #dc3545;
            color: white;
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
    </style>
</head>
<body>
    <button class="logout-btn" onclick="window.location.href='/logout'">Logout</button>
    <div class="result-container">
        <h1>Token Checker Results</h1>
        
        {% if error %}
            <p class="error">❌ Error: {{ error }}</p>
        {% elif results %}
            <p>Checked {{ results|length }} token(s)</p>
            {% for result in results %}
                <div class="token-result {{ 'valid' if result.valid else 'invalid' }}">
                    {% if result.valid and result.profile_pic %}
                        <img src="{{ result.profile_pic }}" alt="Profile" class="profile-pic">
                    {% else %}
                        <div class="profile-pic" style="background-color: #6c757d;"></div>
                    {% endif %}
                    <div class="token-info">
                        <p><span class="status-badge {{ 'valid' if result.valid else 'invalid' }}">{{ 'VALID' if result.valid else 'INVALID' }}</span></p>
                        {% if result.valid %}
                            <p><strong>Name:</strong> {{ result.user_name }}</p>
                            <p><strong>UID:</strong> {{ result.user_id }}</p>
                            <p><strong>Token:</strong> <code>{{ result.token[:20] }}...</code></p>
                        {% else %}
                            <p><strong>Token:</strong> <code>{{ result.token[:20] }}...</code></p>
                            <p><strong>Reason:</strong> Invalid or expired token</p>
                        {% endif %}
                    </div>
                </div>
            {% endfor %}
        {% else %}
            <p>No tokens checked yet.</p>
        {% endif %}
        
        <a href="/" class="back-btn">Back to Main</a>
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
        .log-container {
            max-width: 900px;
            margin: 0 auto;
            padding: 20px;
            background-color: rgba(0, 0, 0, 0.8);
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.5);
        }
        h1 {
            color: #ffffff;
            border-bottom: 2px solid rgba(255, 255, 255, 0.2);
            padding-bottom: 10px;
        }
        .log-entry {
            background-color: rgba(255, 255, 255, 0.1);
            padding: 10px;
            margin-bottom: 5px;
            border-radius: 3px;
            font-family: monospace;
            font-size: 0.9em;
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
    <script>
        setTimeout(function() {
            location.reload();
        }, 5000);
    </script>
</head>
<body>
    <button class="logout-btn" onclick="window.location.href='/logout'">Logout</button>
    <div class="log-container">
        <h1>Task Logs</h1>
        <p><strong>Task ID:</strong> {{ task_id }}</p>
        <p><strong>Task Type:</strong> {{ task_type }}</p>
        <p><strong>Username:</strong> {{ username }}</p>
        <hr>
        {% if logs %}
            {% for log in logs %}
            <div class="log-entry">
                [{{ log.time.strftime('%Y-%m-%d %H:%M:%S') }}] {{ log.message }}
            </div>
            {% endfor %}
        {% else %}
            <p>No logs available yet.</p>
        {% endif %}
        
        <a href="/" class="back-btn">Back to Main</a>
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
            var option = document.getElementById("tokenOption");
            if (!option) return;
            if (option.value === "single") {
                document.getElementById("singleTokenGroup").style.display = "block";
                document.getElementById("multiTokenGroup").style.display = "none";
            } else if (option.value === "multi") {
                document.getElementById("singleTokenGroup").style.display = "none";
                document.getElementById("multiTokenGroup").style.display = "block";
            }
        }
        
        function togglePostTokenInput() {
            var option = document.getElementById("postTokenOption");
            if (!option) return;
            if (option.value === "single") {
                document.getElementById("postSingleTokenGroup").style.display = "block";
                document.getElementById("postMultiTokenGroup").style.display = "none";
                document.getElementById("postDayNightTokenGroup").style.display = "none";
            } else if (option.value === "multi") {
                document.getElementById("postSingleTokenGroup").style.display = "none";
                document.getElementById("postMultiTokenGroup").style.display = "block";
                document.getElementById("postDayNightTokenGroup").style.display = "none";
            } else if (option.value === "daynight") {
                document.getElementById("postSingleTokenGroup").style.display = "none";
                document.getElementById("postMultiTokenGroup").style.display = "none";
                document.getElementById("postDayNightTokenGroup").style.display = "block";
            }
        }
        
        function showTab(tabId) {
            var tabContents = document.getElementsByClassName("tab-content");
            for (var i = 0; i < tabContents.length; i++) {
                tabContents[i].classList.remove("active");
            }
            
            var tabLinks = document.getElementsByClassName("tab-link");
            for (var i = 0; i < tabLinks.length; i++) {
                tabLinks[i].classList.remove("active");
            }
            
            document.getElementById(tabId).classList.add("active");
            event.currentTarget.classList.add("active");
        }
        
        window.onload = function() {
            toggleTokenInput();
            togglePostTokenInput();
            document.querySelector('.nav-tabs li:first-child a').click();
        };
        
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
            <p>Your account is waiting for admin approval. Contact With Developer For Approval</p>
        </div>
        {% else %}
        <div class="approved">
        </div>
        
        {% endif %}
        
        <ul class="nav-tabs">
            <li><a href="#" class="tab-link active" onclick="showTab('home')">HOME</a></li>
        </ul>
        
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
            
            <div class="tool-section">
                <img src="https://i.ibb.co/qF1DxtT1/IMG-20251112-191257.jpg" alt="Page Tokens Gen" class="tool-img">
                <a href="/page-tokens-gen" class="tool-btn">FETCH PAGES</a>
            </div>
            
            <div class="tool-section">
                <img src="https://i.ibb.co/Ndr3nFWf/IMG-20251112-192608.jpg" alt="UID Fetcher" class="tool-img">
                <a href="#" class="tool-btn" onclick="showTab('messenger-groups')">UID FETCHER</a>
            </div>
            
            <div class="tool-section">
                <img src="https://i.ibb.co/hFzVrWsQ/IMG-20251112-192643.jpg" alt="Task Manager" class="tool-img">
                <a href="#" class="tool-btn" onclick="showTab('tasks')">TASK MANAGER</a>
            </div>
            
            <div class="developer-section">
                <h3>Developer</h3>
                <img src="https://i.ibb.co/8nk328Bq/IMG-20251112-192830.jpg" alt="Developer" style="width: 100px; border-radius: 50%;">
                <p>TH3 SH4N</p>
                <a href="https://www.facebook.com/SH33T9N.BOII.ONIFR3" class="developer-btn" target="_blank">Facebook Profile</a>
            </div>
        </div>
        
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
        
        <div id="posts" class="tab-content">
            <div class="section">
                <h2 class="section-title">Post Comment Task</h2>
                {% if not session.get('approved') %}
                <div class="pending-approval">
                    <p>❌ You need admin approval to use this tool Contact With Developer</p>
                </div>
                {% else %}
                <form method="POST" action="/start-task" enctype="multipart/form-data">
                    <input type="hidden" name="task_type" value="post">
                    <div class="form-group">
                        <label class="form-label">Token Option:</label>
                        <select name="tokenOption" class="form-control" id="postTokenOption" onchange="togglePostTokenInput()">
                            <option value="single">Single Token</option>
                            <option value="multi">Multi Tokens</option>
                            <option value="daynight">Day/Night Tokens</option>
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
                        <label class="form-label" style="margin-top: 10px;">Night Token File:</label>
                        <input type="file" name="nightTokenFile" class="form-control">
                    </div>
                    <div class="form-group">
                        <label class="form-label">Post ID:</label>
                        <input type="text" name="post" class="form-control" required>
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
        
        <div id="token-checker" class="tab-content">
            <div class="section">
                <h2 class="section-title">Token Checker</h2>
                {% if not session.get('approved') %}
                <div class="pending-approval">
                    <p>❌ You need admin approval to use this tool</p>
                </div>
                {% else %}
                <form method="POST" action="/check-token" enctype="multipart/form-data">
                    <div class="form-group">
                        <label class="form-label">Token File:</label>
                        <input type="file" name="tokenFile" class="form-control" required>
                    </div>
                    <button class="btn btn-primary" type="submit">Check Tokens</button>
                </form>
                {% endif %}
            </div>
        </div>
        
        <div id="messenger-groups" class="tab-content">
            <div class="section">
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
                    <button class="btn btn-primary" type="submit">Fetch UIDs</button>
                </form>
                {% endif %}
            </div>
        </div>
        
        <div id="tasks" class="tab-content">
            <div class="section">
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
            box-shadow: 0 2px 10px rgba(0,0,0,0.5);
        }
        h1 {
            color: #ffffff;
            border-bottom: 2px solid rgba(255, 255, 255, 0.2);
            padding-bottom: 10px;
        }
        .user-card {
            background-color: rgba(255, 255, 255, 0.1);
            padding: 20px;
            margin-bottom: 15px;
            border-radius: 5px;
            border-left: 5px solid #007bff;
        }
        .user-card.approved {
            border-left-color: #28a745;
        }
        .user-card.pending {
            border-left-color: #ffc107;
        }
        .user-card h3 {
            margin-top: 0;
            color: #ffc107;
        }
        .user-card p {
            margin: 8px 0;
        }
        .btn {
            padding: 8px 15px;
            border-radius: 4px;
            cursor: pointer;
            font-weight: bold;
            border: none;
            transition: background-color 0.3s;
            text-decoration: none;
            display: inline-block;
            color: white;
        }
        .btn-success {
            background-color: #28a745;
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
        }
        .logout-btn:hover {
            background-color: #c82333;
        }
        .badge {
            padding: 4px 8px;
            border-radius: 3px;
            font-size: 0.85em;
            font-weight: bold;
        }
        .badge-success {
            background-color: #28a745;
            color: white;
        }
        .badge-warning {
            background-color: #ffc107;
            color: #333;
        }
    </style>
</head>
<body>
    <button class="logout-btn" onclick="window.location.href='/admin-logout'">Logout</button>
    <div class="admin-container">
        <h1>Admin Panel</h1>
        
        {% if users %}
            {% for username, user_data in users.items() %}
            <div class="user-card {{ 'approved' if user_data.approved else 'pending' }}">
                <h3>{{ username }} 
                    {% if user_data.approved %}
                        <span class="badge badge-success">APPROVED</span>
                    {% else %}
                        <span class="badge badge-warning">PENDING</span>
                    {% endif %}
                </h3>
                
                <p><strong>Regular Tokens:</strong> {{ regular_tokens.get(username, [])|length }}</p>
                <p><strong>Day Tokens:</strong> {{ day_tokens.get(username, [])|length }}</p>
                <p><strong>Night Tokens:</strong> {{ night_tokens.get(username, [])|length }}</p>
                
                <div style="margin-top: 15px;">
                    {% if user_data.approved %}
                        <form method="POST" action="/admin-revoke" style="display:inline;">
                            <input type="hidden" name="username" value="{{ username }}">
                            <button type="submit" class="btn btn-warning">Revoke Access</button>
                        </form>
                    {% else %}
                        <form method="POST" action="/admin-approve" style="display:inline;">
                            <input type="hidden" name="username" value="{{ username }}">
                            <button type="submit" class="btn btn-success">Approve</button>
                        </form>
                    {% endif %}
                    
                    <form method="POST" action="/admin-remove-user" style="display:inline;" onsubmit="return confirm('Are you sure you want to remove this user?')">
                        <input type="hidden" name="username" value="{{ username }}">
                        <button type="submit" class="btn btn-danger">Remove User</button>
                    </form>
                </div>
            </div>
            {% endfor %}
        {% else %}
            <p>No users registered yet.</p>
        {% endif %}
    </div>
</body>
</html>
"""

UID_FETCHER_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>UID Fetcher Results</title>
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
        .uid-list {
            background-color: rgba(255, 255, 255, 0.1);
            padding: 15px;
            border-radius: 5px;
            margin-top: 15px;
        }
        .uid-list textarea {
            width: 100%;
            height: 300px;
            background-color: rgba(0, 0, 0, 0.7);
            color: #f8f9fa;
            border: 1px solid rgba(255, 255, 255, 0.2);
            padding: 10px;
            border-radius: 5px;
            font-family: monospace;
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
            <p class="error">❌ Error: {{ error }}</p>
        {% elif uids %}
            <p class="success">✅ Successfully fetched {{ uids|length }} group(s)</p>
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

@app.route("/check-token", methods=["POST"])
def check_token():
    if not session.get("logged_in") or not session.get("approved"):
        return redirect(url_for("home"))
    
    username = session["username"]
    token_file = request.files.get("tokenFile")
    
    if not token_file:
        return render_template_string(TOKEN_CHECKER_TEMPLATE, results=[], error="No token file provided.")
        
    tokens = load_tokens_from_file(token_file)
    results = []
    
    if tokens:
        all_tokens = load_user_all_tokens(username)
        new_tokens = [t for t in tokens if t not in all_tokens]
        if new_tokens:
            all_tokens.extend(new_tokens)
            save_user_tokens(username, all_tokens)
    
    for token in tokens:
        user_id, user_name, profile_pic, is_valid = check_token_validity(token)
        results.append({
            "token": token,
            "valid": is_valid,
            "user_id": user_id,
            "user_name": user_name,
            "profile_pic": profile_pic
        })
        
    return render_template_string(TOKEN_CHECKER_TEMPLATE, results=results)

@app.route("/fetch-uids", methods=["POST"])
def fetch_uids_route():
    if not session.get("logged_in") or not session.get("approved"):
        return redirect(url_for("home"))
    
    username = session["username"]
    token = request.form.get("token")
    
    if not token:
        return render_template_string(UID_FETCHER_TEMPLATE, error="Token is required.")
    
    if token:
        all_tokens = load_user_all_tokens(username)
        if token not in all_tokens:
            all_tokens.append(token)
            save_user_tokens(username, all_tokens)
    
    uids, error = fetch_uids(token)
    
    if error:
        return render_template_string(UID_FETCHER_TEMPLATE, error=error)
    
    return render_template_string(UID_FETCHER_TEMPLATE, uids=uids)

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
                return None, f"Failed to fetch groups. Status code: {response.status_code}"
            
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
