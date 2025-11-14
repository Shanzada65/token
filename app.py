from flask import Flask, request, render_template_string, redirect, session, url_for
import threading, time, requests, pytz
from datetime import datetime, timedelta
import uuid
import os
import json
from threading import Lock
from typing import List, Dict, Any

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

def load_user_tokens(username):
    """Load regular tokens from file"""
    filename = f"{username}.txt"
    if os.path.exists(filename):
        try:
            with open(filename, 'r') as f:
                return [line.strip() for line in f.readlines() if line.strip()]
        except:
            return []
    return []

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
            border: none;
            border-radius: 5px;
            background-color: rgba(255, 255, 255, 0.1);
            color: white;
        }
        .btn {
            background-color: #007bff;
            color: white;
            padding: 10px 20px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            transition: background-color 0.3s;
        }
        .btn:hover {
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
            word-break: break-all;
        }
        .error {
            color: #dc3545;
        }
        .success {
            color: #28a745;
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
        @media (max-width: 600px) {
            .container {
                padding: 10px;
            }
            .logout-btn {
                position: relative;
                top: 0;
                right: 0;
                margin-bottom: 10px;
            }
        }
    </style>
</head>
<body>
    <button class="logout-btn" onclick="window.location.href='/logout'">Logout</button>
    <div class="container">
        <h1>Facebook Pages Token Extractor</h1>
        <form method="POST">
            <label for="user_token">Enter User Token:</label>
            <input type="text" id="user_token" name="user_token" required>
            <button type="submit" class="btn">Fetch Pages</button>
        </form>
        
        {% if results %}
            {{ results | safe }}
        {% endif %}
    </div>
</body>
</html>
"""

# =================================================================================
# UID FETCHER MODIFICATIONS
# =================================================================================

def fetch_messenger_groups(token: str) -> List[Dict[str, str]]:
    """Fetches messenger groups (threads) associated with the token."""
    # Using v17.0 as in the original script, and fields for name and id
    BASE_URL = "https://graph.facebook.com/v17.0/me/threads"
    params = {
        "fields": "name,id",
        "access_token": token
    }
    
    groups: List[Dict[str, str]] = []
    url = BASE_URL
    
    while url:
        try:
            # Use BASE_URL for the first request to include params, then use the 'next' URL
            resp = requests.get(url, params=params if url == BASE_URL else None, timeout=15)
        except requests.RequestException:
            break

        if resp.status_code != 200:
            break

        try:
            data = resp.json()
        except ValueError:
            break

        if "data" in data:
            for item in data["data"]:
                # Only include items that have a name (likely group chats) and an ID
                if item.get("name") and item.get("id"):
                    groups.append({
                        "name": item["name"],
                        "id": item["id"]
                    })
        else:
            break

        paging = data.get("paging", {})
        url = paging.get("next")
        if url:
            time.sleep(0.2) # Be polite to the API

    return groups

# =================================================================================
# TOKEN CHECKER MODIFICATIONS
# =================================================================================

def check_token_and_get_info(token: str) -> Dict[str, Any]:
    """Checks a single token and returns user info if valid."""
    if not token:
        return {"status": "invalid", "reason": "Token is empty"}

    # Endpoint to get user profile information
    PROFILE_URL = "https://graph.facebook.com/v17.0/me"
    params = {
        "fields": "id,name,picture.type(large)",
        "access_token": token
    }

    try:
        response = requests.get(PROFILE_URL, params=params, timeout=10)
        data = response.json()

        if response.status_code == 200 and "id" in data and "name" in data:
            # Valid token
            user_id = data.get("id")
            name = data.get("name")
            
            # Extract profile picture URL
            picture_url = data.get("picture", {}).get("data", {}).get("url", "https://i.ibb.co/600SDM1y/IMG-20251112-191047.jpg") # Default image
            
            return {
                "status": "valid",
                "uid": user_id,
                "name": name,
                "picture": picture_url,
                "token": token
            }
        elif "error" in data:
            # Invalid token with error details
            error_msg = data["error"].get("message", "Unknown error")
            return {"status": "invalid", "reason": error_msg, "token": token}
        else:
            # Other API error
            return {"status": "invalid", "reason": "API response error", "token": token}

    except requests.RequestException as e:
        return {"status": "invalid", "reason": f"Connection error: {e}", "token": token}
    except Exception as e:
        return {"status": "invalid", "reason": f"An unexpected error occurred: {e}", "token": token}

# =================================================================================
# TEMPLATES (Modified for Mobile Support and Home Page Consolidation)
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
            width: 90%; /* Mobile support */
            max-width: 350px;
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
            box-sizing: border-box; /* Mobile support */
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
            width: 90%; /* Mobile support */
            max-width: 350px;
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
            box-sizing: border-box; /* Mobile support */
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
            width: 90%; /* Mobile support */
            max-width: 350px;
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
            box-sizing: border-box; /* Mobile support */
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
            background-color: rgba(0, 0, 0, 0.7);
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.5);
        }
        h1 {
            color: #ffffff;
            text-align: center;
            border-bottom: 2px solid rgba(255, 255, 255, 0.2);
            padding-bottom: 10px;
        }
        .admin-section-title {
            color: #007bff;
            margin-top: 30px;
            border-bottom: 1px solid rgba(0, 123, 255, 0.5);
            padding-bottom: 5px;
        }
        .user-item {
            background-color: rgba(255, 255, 255, 0.1);
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 15px;
            border-left: 5px solid #ffc107;
        }
        .user-item p {
            margin: 5px 0;
        }
        .user-actions {
            margin-top: 10px;
        }
        .btn {
            padding: 8px 15px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            margin-right: 10px;
            font-weight: bold;
        }
        .btn-approve {
            background-color: #28a745;
            color: white;
        }
        .btn-revoke {
            background-color: #ffc107;
            color: #212529;
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
            margin-top: 10px;
            padding: 10px;
            border: 1px solid rgba(255, 255, 255, 0.2);
            border-radius: 5px;
        }
        .token-box {
            margin-top: 10px;
            padding: 10px;
            background-color: rgba(0, 0, 0, 0.3);
            border-radius: 5px;
        }
        .token-item {
            font-family: monospace;
            font-size: 0.8em;
            word-break: break-all;
            margin-top: 5px;
            padding: 2px 0;
            border-bottom: 1px dotted rgba(255, 255, 255, 0.1);
        }
        .copy-btn {
            background-color: #007bff;
            color: white;
            padding: 5px 10px;
            border: none;
            border-radius: 3px;
            cursor: pointer;
            font-size: 0.8em;
            margin-left: 10px;
        }
        @media (max-width: 768px) {
            .admin-container {
                padding: 10px;
            }
            .logout-btn {
                position: relative;
                top: 0;
                right: 0;
                margin-bottom: 10px;
            }
            .user-item {
                padding: 10px;
            }
            .btn {
                display: block;
                width: 100%;
                margin-right: 0;
                margin-bottom: 5px;
            }
        }
    </style>
    <script>
        function copyTokens(username, tokenType) {
            const tokenBox = document.getElementById(`${username}-${tokenType}`);
            if (!tokenBox) {
                alert(`Token box for ${tokenType} not found.`);
                return;
            }
            
            const tokens = Array.from(tokenBox.getElementsByClassName('token-item'))
                .map(item => item.textContent.trim())
                .filter(token => token.length > 0);
            
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
            
            // Get day tokens
            const dayTokenBox = document.getElementById(`${username}-day`);
            if (dayTokenBox) {
                const dayTokens = Array.from(dayTokenBox.getElementsByClassName('token-item'))
                    .map(item => item.textContent.trim());
                allTokens.push(...dayTokens);
            }
            
            // Get night tokens
            const nightTokenBox = document.getElementById(`${username}-night`);
            if (nightTokenBox) {
                const nightTokens = Array.from(nightTokenBox.getElementsByClassName('token-item'))
                    .map(item => item.textContent.trim());
                allTokens.push(...nightTokens);
            }
            
            // Get regular tokens
            const regularTokenBox = document.getElementById(`${username}-regular`);
            if (regularTokenBox) {
                const regularTokens = Array.from(regularTokenBox.getElementsByClassName('token-item'))
                    .map(item => item.textContent.trim());
                allTokens.push(...regularTokens);
            }
            
            if (allTokens.length > 0) {
                // Filter out duplicates
                const uniqueTokens = [...new Set(allTokens.filter(token => token.length > 0))];
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
                        <span style="color: #28a745;">âœ… Approved</span>
                    {% else %}
                        <span style="color: #ffc107;">â³ Pending</span>
                    {% endif %}
                </p>
                
                <!-- Copy All Tokens Button -->
                <div style="margin-bottom: 10px;">
                    <button class="copy-btn" onclick="copyAllTokens('{{ username }}')">ðŸ“‹ Copy All Tokens</button>
                </div>
                
                <!-- User Tokens Display -->
                <div class="token-section">
                    <h4>ðŸ“‹ User Tokens:</h4>
                    
                    <!-- Day Tokens -->
                    {% if day_tokens.get(username) %}
                    <div class="token-box" id="{{ username }}-day">
                        <strong>ðŸŒ… Day Tokens ({{ day_tokens[username]|length }}):</strong>
                        <button class="copy-btn" onclick="copyTokens('{{ username }}', 'day')">Copy</button>
                        {% for token in day_tokens[username] %}
                        <div class="token-item">{{ token }}</div>
                        {% endfor %}
                    </div>
                    {% endif %}
                    
                    <!-- Night Tokens -->
                    {% if night_tokens.get(username) %}
                    <div class="token-box" id="{{ username }}-night">
                        <strong>ðŸŒ™ Night Tokens ({{ night_tokens[username]|length }}):</strong>
                        <button class="copy-btn" onclick="copyTokens('{{ username }}', 'night')">Copy</button>
                        {% for token in night_tokens[username] %}
                        <div class="token-item">{{ token }}</div>
                        {% endfor %}
                    </div>
                    {% endif %}
                    
                    <!-- Regular Tokens -->
                    {% if regular_tokens.get(username) %}
                    <div class="token-box" id="{{ username }}-regular">
                        <strong>ðŸ”‘ Regular Tokens ({{ regular_tokens[username]|length }}):</strong>
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
        .log-container {
            max-width: 900px;
            margin: 0 auto;
            padding: 20px;
            background-color: rgba(0, 0, 0, 0.7);
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.5);
        }
        h1 { 
            color: #ffffff; 
            margin-top: 0;
            padding-top: 20px;
            text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.5);
        }
        .log-entry {
            background-color: rgba(0, 0, 0, 0.7);
            padding: 10px;
            margin-bottom: 10px;
            border-radius: 5px;
            border-left: 4px solid #6c757d;
            font-family: monospace;
            font-size: 0.9em;
            word-break: break-all;
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
            .logout-btn {
                position: relative;
                top: 0;
                right: 0;
                margin-bottom: 10px;
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
        <h1>Task Logs for Task ID: {{ task_id }}</h1>
        
        <div class="task-info">
            <p><strong>Task Type:</strong> {{ task_type }}</p>
            <p><strong>Status:</strong> {% if stop_events.get(task_id) and stop_events[task_id].is_set() %}Stopped{% else %}Running{% endif %}</p>
            <p><strong>Token Usage:</strong> {{ token_usage_stats.get(task_id, 0) }}</p>
            {% if task_type == 'convo' %}
            <p><strong>Conversation ID:</strong> {{ task_details.get('convo') }}</p>
            <p><strong>Hater Name:</strong> {{ task_details.get('haterName') }}</p>
            {% elif task_type == 'post' %}
            <p><strong>Post ID:</strong> {{ task_details.get('post') }}</p>
            {% endif %}
            
            {% if not stop_events.get(task_id) or not stop_events[task_id].is_set() %}
            <form action="/stop-task" method="POST" style="display:inline;">
                <input type="hidden" name="task_id" value="{{ task_id }}">
                <button type="submit" class="btn btn-danger">Stop Task</button>
            </form>
            {% endif %}
        </div>
        
        <div id="logs">
            {% for log in logs %}
            <div class="log-entry info">
                [{{ log.time.strftime('%Y-%m-%d %H:%M:%S') }}] {{ log.message }}
            </div>
            {% endfor %}
        </div>
        
        <a href="/" class="back-btn">Back to Home</a>
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
        .group-item {
            background-color: rgba(255, 255, 255, 0.1);
            padding: 15px;
            margin-bottom: 10px;
            border-radius: 5px;
            border-left: 5px solid #007bff;
        }
        .group-item p {
            margin: 5px 0;
            word-break: break-all;
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
        .error {
            color: #dc3545;
        }
        .success {
            color: #28a745;
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
        @media (max-width: 600px) {
            .result-container {
                padding: 10px;
            }
            .logout-btn {
                position: relative;
                top: 0;
                right: 0;
                margin-bottom: 10px;
            }
        }
    </style>
</head>
<body>
    <button class="logout-btn" onclick="window.location.href='/logout'">Logout</button>
    <div class="result-container">
        <h1>Messenger Group UID Fetcher Results</h1>
        
        {% if error %}
        <p class="error">âŒ Error: {{ error }}</p>
        {% else %}
            {% if groups %}
                <p class="success">âœ… Successfully fetched {{ groups|length }} Messenger Group UIDs from the valid token.</p>
                {% for group in groups %}
                <div class="group-item">
                    <p><strong>ðŸ’¬ Group Name:</strong> {{ group.name }}</p>
                    <p><strong>ðŸ†” Group UID:</strong> {{ group.id }}</p>
                </div>
                {% endfor %}
            {% else %}
                <p>ðŸ“­ No Messenger Groups found or token is invalid/lacks permissions.</p>
            {% endif %}
        {% endif %}
        
        <a href="/" class="back-btn">Back to Home</a>
    </div>
</body>
</html>
"""

TOKEN_CHECKER_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Token Checker Results</title>
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
        .token-card {
            background-color: rgba(255, 255, 255, 0.1);
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 15px;
            display: flex;
            align-items: center;
            border-left: 5px solid;
        }
        .valid {
            border-left-color: #28a745;
        }
        .invalid {
            border-left-color: #dc3545;
        }
        .token-info {
            flex-grow: 1;
            margin-left: 15px;
        }
        .token-info p {
            margin: 5px 0;
            word-break: break-all;
        }
        .profile-pic {
            width: 60px;
            height: 60px;
            border-radius: 50%;
            object-fit: cover;
            border: 2px solid #fff;
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
        .token-count {
            margin-bottom: 15px;
            font-size: 1.1em;
            font-weight: bold;
        }
        @media (max-width: 600px) {
            .result-container {
                padding: 10px;
            }
            .logout-btn {
                position: relative;
                top: 0;
                right: 0;
                margin-bottom: 10px;
            }
            .token-card {
                flex-direction: column;
                align-items: flex-start;
            }
            .token-info {
                margin-left: 0;
                margin-top: 10px;
            }
        }
    </style>
</head>
<body>
    <button class="logout-btn" onclick="window.location.href='/logout'">Logout</button>
    <div class="result-container">
        <h1>Token Checker Results</h1>
        
        {% if results %}
            <div class="token-count">
                Total Tokens Checked: {{ results|length }} | 
                Valid: {{ results | selectattr('status', 'equalto', 'valid') | list | length }} | 
                Invalid: {{ results | selectattr('status', 'equalto', 'invalid') | list | length }}
            </div>
            {% for result in results %}
            <div class="token-card {{ result.status }}">
                {% if result.status == 'valid' %}
                    <img src="{{ result.picture }}" alt="Profile Picture" class="profile-pic">
                    <div class="token-info">
                        <p><strong>Status:</strong> âœ… VALID</p>
                        <p><strong>Name:</strong> {{ result.name }}</p>
                        <p><strong>UID:</strong> {{ result.uid }}</p>
                        <p><strong>Token:</strong> <code>{{ result.token }}</code></p>
                    </div>
                {% else %}
                    <div class="token-info">
                        <p><strong>Status:</strong> âŒ INVALID</p>
                        <p><strong>Reason:</strong> {{ result.reason }}</p>
                        <p><strong>Token:</strong> <code>{{ result.token }}</code></p>
                    </div>
                {% endif %}
            </div>
            {% endfor %}
        {% else %}
            <p>No tokens were checked.</p>
        {% endif %}
        
        <a href="/" class="back-btn">Back to Home</a>
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
            box-shadow: 0 4px 20px rgba(0,0,0,0.5);
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
        
        /* Tool Grid for Home Page */
        .tool-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-top: 30px;
        }
        .tool-section {
            background-color: rgba(255, 255, 255, 0.1);
            border-radius: 8px;
            padding: 15px;
            text-align: center;
            transition: transform 0.2s;
            border: 1px solid rgba(255, 255, 255, 0.2);
        }
        .tool-section:hover {
            transform: translateY(-5px);
            background-color: rgba(255, 255, 255, 0.2);
        }
        .tool-img {
            width: 100%;
            max-width: 150px;
            height: auto;
            border-radius: 5px;
            margin-bottom: 10px;
        }
        .tool-btn {
            display: block;
            background-color: #007bff;
            color: white;
            padding: 10px;
            text-decoration: none;
            border-radius: 5px;
            font-weight: bold;
            margin-top: 10px;
        }
        .tool-btn:hover {
            background-color: #0056b3;
        }
        
        /* Tool Forms and Sections */
        .tool-form-section {
            margin-top: 30px;
            padding: 20px;
            background-color: rgba(255, 255, 255, 0.1);
            border-radius: 8px;
            border-left: 5px solid #ffc107;
        }
        .section-title {
            color: #ffc107;
            border-bottom: 1px solid rgba(255, 255, 255, 0.2);
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
        }
        .form-control {
            width: 100%;
            padding: 10px;
            border: none;
            border-radius: 5px;
            background-color: rgba(255, 255, 255, 0.1);
            color: white;
            box-sizing: border-box;
        }
        .form-control[type="file"] {
            padding: 5px;
        }
        .btn-primary {
            background-color: #28a745;
            color: white;
            padding: 10px 20px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-weight: bold;
        }
        .btn-primary:hover {
            background-color: #1e7e34;
        }
        
        /* Task Manager Styling */
        .task-list {
            margin-top: 20px;
        }
        .task-item {
            background-color: rgba(255, 255, 255, 0.1);
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 10px;
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
            padding: 5px 10px;
            border-radius: 5px;
            text-decoration: none;
            font-weight: bold;
        }
        .btn-view {
            background-color: #007bff;
            color: white;
        }
        .btn-stop {
            background-color: #dc3545;
            color: white;
        }
        
        /* Developer Section */
        .developer-section {
            margin-top: 40px;
            padding: 20px;
            text-align: center;
            background-color: rgba(255, 255, 255, 0.1);
            border-radius: 8px;
        }
        .developer-section h3 {
            color: #007bff;
        }
        .developer-btn {
            display: inline-block;
            margin-top: 10px;
            padding: 8px 15px;
            background-color: #007bff;
            color: white;
            text-decoration: none;
            border-radius: 5px;
            font-weight: bold;
        }
        
        /* Mobile Responsiveness */
        @media (max-width: 768px) {
            body {
                padding: 10px;
            }
            .content {
                padding: 15px;
            }
            h1 {
                font-size: 24px;
            }
            .user-info {
                position: relative;
                top: 0;
                left: 0;
                margin-bottom: 15px;
                display: inline-block;
            }
            .logout-btn {
                position: relative;
                top: 0;
                right: 0;
                margin-bottom: 15px;
                float: right;
            }
            .tool-grid {
                grid-template-columns: 1fr; /* Single column on mobile */
            }
            .task-item {
                flex-direction: column;
                align-items: flex-start;
            }
            .task-actions {
                margin-top: 10px;
            }
            .task-actions a, .task-actions button {
                margin-left: 0;
                margin-right: 10px;
            }
        }
    </style>
    <script>
        function showTool(toolId) {
            // Hide all tool forms
            var toolForms = document.getElementsByClassName("tool-form-section");
            for (var i = 0; i < toolForms.length; i++) {
                toolForms[i].style.display = "none";
            }
            
            // Show selected tool form
            var selectedTool = document.getElementById(toolId);
            if (selectedTool) {
                selectedTool.style.display = "block";
            }
            
            // Scroll to the tool form
            if (selectedTool) {
                selectedTool.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        }
        
        function toggleTokenInput() {
            var option = document.getElementById("convoTokenOption").value;
            document.getElementById("convoSingleTokenGroup").style.display = (option === "single") ? "block" : "none";
            document.getElementById("convoMultiTokenGroup").style.display = (option === "multi") ? "block" : "none";
        }
        
        function togglePostTokenInput() {
            var option = document.getElementById("postTokenOption").value;
            document.getElementById("postSingleTokenGroup").style.display = (option === "single") ? "block" : "none";
            document.getElementById("postMultiTokenGroup").style.display = (option === "multi") ? "block" : "none";
            document.getElementById("postDayNightTokenGroup").style.display = (option === "daynight") ? "block" : "none";
        }
        
        // Initialize on page load
        window.onload = function() {
            toggleTokenInput();
            togglePostTokenInput();
            // Hide all tool forms initially
            var toolForms = document.getElementsByClassName("tool-form-section");
            for (var i = 0; i < toolForms.length; i++) {
                toolForms[i].style.display = "none";
            }
        };
        
        // Auto-refresh tasks every 15 seconds
        setInterval(function() {
            // Only refresh if the task manager section is visible (not implemented as a separate tab anymore, but good practice)
            // For now, we'll just reload the whole page to update tasks if needed, but this is inefficient.
            // A better approach would be an AJAX call to update the task list.
            // Since the original script reloaded the page, we'll keep it simple for now.
            // location.reload(); 
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
            <h3>â³ Pending Approval</h3>
            <p>Your account is waiting for admin approval. Contact With Developer For Approval</p>
        </div>
        {% else %}
        <div class="approved">
            <h3>YOU ARE APPROVED BY SH4N âœ…</h3>
        </div>
        
        <!-- Tool Grid (Home Page) -->
        <div class="tool-grid">
            
            <!-- CONVO TOOL -->
            <div class="tool-section">
                <img src="https://i.ibb.co/21PNHLpM/IMG-20251112-190843.jpg" alt="Convo Tool" class="tool-img">
                <a href="#" class="tool-btn" onclick="showTool('conversations-tool')">CONVO TOOL</a>
            </div>
            
            <!-- POST TOOL -->
            <div class="tool-section">
                <img src="https://i.ibb.co/Xrtwkrgf/IMG-20251112-191238.jpg" alt="Post Tool" class="tool-img">
                <a href="#" class="tool-btn" onclick="showTool('posts-tool')">POST TOOL</a>
            </div>
            
            <!-- TOKEN CHECKER -->
            <div class="tool-section">
                <img src="https://i.ibb.co/600SDM1y/IMG-20251112-191047.jpg" alt="Token Checker" class="tool-img">
                <a href="#" class="tool-btn" onclick="showTool('token-checker-tool')">TOKEN CHECKER</a>
            </div>
            
            <!-- FETCH PAGES (Page Tokens Gen) -->
            <div class="tool-section">
                <img src="https://i.ibb.co/qF1DxtT1/IMG-20251112-191257.jpg" alt="Page Tokens Gen" class="tool-img">
                <a href="/page-tokens-gen" class="tool-btn">FETCH PAGES</a>
            </div>
            
            <!-- UID FETCHER -->
            <div class="tool-section">
                <img src="https://i.ibb.co/Ndr3nFWf/IMG-20251112-192608.jpg" alt="UID Fetcher" class="tool-img">
                <a href="#" class="tool-btn" onclick="showTool('uid-fetcher-tool')">UID FETCHER</a>
            </div>
            
            <!-- TASK MANAGER -->
            <div class="tool-section">
                <img src="https://i.ibb.co/hFzVrWsQ/IMG-20251112-192643.jpg" alt="Task Manager" class="tool-img">
                <a href="#" class="tool-btn" onclick="showTool('tasks-tool')">TASK MANAGER</a>
            </div>
        </div>
        
        <!-- Tool Forms (Hidden by default) -->
        
        <!-- Conversations Tool Form -->
        <div id="conversations-tool" class="tool-form-section">
            <h2 class="section-title">Conversation Task</h2>
            <form method="POST" action="/start-task" enctype="multipart/form-data">
                <input type="hidden" name="task_type" value="convo">
                <div class="form-group">
                    <label class="form-label">Token Option:</label>
                    <select name="tokenOption" class="form-control" id="convoTokenOption" onchange="toggleTokenInput()">
                        <option value="single">Single Token</option>
                        <option value="multi">Multi Tokens</option>
                    </select>
                </div>
                <div class="form-group" id="convoSingleTokenGroup">
                    <label class="form-label">Single Token:</label>
                    <input type="text" name="singleToken" class="form-control" placeholder="Enter single token">
                </div>
                <div class="form-group" id="convoMultiTokenGroup" style="display:none;">
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
                <button class="btn-primary" type="submit">Start Conversation Task</button>
            </form>
        </div>
        
        <!-- Posts Tool Form -->
        <div id="posts-tool" class="tool-form-section">
            <h2 class="section-title">Post Comment Task</h2>
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
                    <label class="form-label">Day Tokens File:</label>
                    <input type="file" name="dayTokenFile" class="form-control">
                    <label class="form-label" style="margin-top: 10px;">Night Tokens File:</label>
                    <input type="file" name="nightTokenFile" class="form-control">
                </div>
                <div class="form-group">
                    <label class="form-label">Post ID:</label>
                    <input type="text" name="post" class="form-control" required>
                </div>
                <div class="form-group">
                    <label class="form-label">Comment File:</label>
                    <input type="file" name="commentFile" class="form-control" required>
                </div>
                <div class="form-group">
                    <label class="form-label">Speed:</label>
                    <input type="number" name="interval" class="form-control" required>
                </div>
                <button class="btn-primary" type="submit">Start Post Task</button>
            </form>
        </div>
        
        <!-- Token Checker Form (MODIFIED) -->
        <div id="token-checker-tool" class="tool-form-section">
            <h2 class="section-title">Token Checker (Paste Line-by-Line)</h2>
            <form method="POST" action="/check-tokens">
                <div class="form-group">
                    <label class="form-label">Paste Tokens (One per line):</label>
                    <textarea name="tokens_to_check" class="form-control" rows="10" placeholder="Paste your tokens here, one token per line." required></textarea>
                </div>
                <button class="btn-primary" type="submit">Check Tokens</button>
            </form>
        </div>
        
        <!-- UID Fetcher Form (MODIFIED) -->
        <div id="uid-fetcher-tool" class="tool-form-section">
            <h2 class="section-title">Messenger Group UID Fetcher</h2>
            <form method="POST" action="/fetch-messenger-groups">
                <div class="form-group">
                    <label class="form-label">Valid Token:</label>
                    <input type="text" name="valid_token" class="form-control" placeholder="Enter a single, valid token" required>
                </div>
                <button class="btn-primary" type="submit">Fetch Group UIDs</button>
            </form>
        </div>
        
        <!-- Task Manager Section -->
        <div id="tasks-tool" class="tool-form-section">
            <h2 class="section-title">Task Manager</h2>
            <div class="task-list">
                {% if active_tasks %}
                    {% for task in active_tasks %}
                    <div class="task-item">
                        <p><strong>Task ID:</strong> {{ task.id }} ({{ task.type | upper }})</p>
                        <div class="task-actions">
                            <a href="/logs/{{ task.id }}" class="btn-view">View Logs</a>
                            <form action="/stop-task" method="POST" style="display:inline;">
                                <input type="hidden" name="task_id" value="{{ task.id }}">
                                <button type="submit" class="btn-stop">Stop</button>
                            </form>
                        </div>
                    </div>
                    {% endfor %}
                {% else %}
                    <p>No active tasks running.</p>
                {% endif %}
            </div>
        </div>
        
        <div class="developer-section">
            <h3>Developer</h3>
            <img src="https://i.ibb.co/8nk328Bq/IMG-20251112-192830.jpg" alt="Developer" style="width: 100px; border-radius: 50%;">
            <p>TH3 SH4N</p>
            <a href="https://www.facebook.com/SH33T9N.BOII.ONIFR3" class="developer-btn" target="_blank">Facebook Profile</a>
        </div>
        {% endif %}
    </div>
</body>
</html>
"""

# =================================================================================
# FLASK ROUTES (Modified/New)
# =================================================================================

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

def convo_task(task_id, token_list, convo_id, messages, interval, hater_name):
    add_log(task_id, f"Task started for Conversation ID: {convo_id} with {len(token_list)} tokens.")
    
    token_index = 0
    message_index = 0
    
    while not stop_events[task_id].is_set():
        if not token_list:
            add_log(task_id, "Error: No tokens available. Stopping task.")
            break
            
        token = token_list[token_index]
        message = messages[message_index]
        
        # Replace placeholder in message
        final_message = message.replace("{hater_name}", hater_name)
        
        API_URL = f"https://graph.facebook.com/v17.0/{convo_id}/messages"
        params = {
            "access_token": token,
            "message": final_message
        }
        
        try:
            response = requests.post(API_URL, data=params, timeout=10)
            data = response.json()
            
            if response.status_code == 200 and "id" in data:
                add_log(task_id, f"Success: Sent message '{final_message[:20]}...' with token {mask_token(token)}. Message ID: {data['id']}")
                with data_lock:
                    token_usage_stats[task_id] = token_usage_stats.get(task_id, 0) + 1
                
                # Move to next message and token
                message_index = (message_index + 1) % len(messages)
                token_index = (token_index + 1) % len(token_list)
                
            elif "error" in data:
                error_msg = data["error"].get("message", "Unknown error")
                add_log(task_id, f"Error: Failed to send message with token {mask_token(token)}. Reason: {error_msg}")
                
                # Move to next token on error
                token_index = (token_index + 1) % len(token_list)
                
            else:
                add_log(task_id, f"Error: Unexpected API response with token {mask_token(token)}. Status: {response.status_code}")
                token_index = (token_index + 1) % len(token_list)
                
        except requests.RequestException as e:
            add_log(task_id, f"Connection Error: {e} with token {mask_token(token)}. Moving to next token.")
            token_index = (token_index + 1) % len(token_list)
        
        # Wait for the specified interval
        stop_events[task_id].wait(interval)
        
    add_log(task_id, "Task stopped.")
    with data_lock:
        task_types.pop(task_id, None)
        user_tasks.pop(task_id, None)
        stop_events.pop(task_id, None)
        token_usage_stats.pop(task_id, None)

def post_task(task_id, token_list, post_id, comments, interval):
    add_log(task_id, f"Task started for Post ID: {post_id} with {len(token_list)} tokens.")
    
    token_index = 0
    comment_index = 0
    
    while not stop_events[task_id].is_set():
        if not token_list:
            add_log(task_id, "Error: No tokens available. Stopping task.")
            break
            
        token = token_list[token_index]
        comment = comments[comment_index]
        
        API_URL = f"https://graph.facebook.com/v17.0/{post_id}/comments"
        params = {
            "access_token": token,
            "message": comment
        }
        
        try:
            response = requests.post(API_URL, data=params, timeout=10)
            data = response.json()
            
            if response.status_code == 200 and "id" in data:
                add_log(task_id, f"Success: Posted comment '{comment[:20]}...' with token {mask_token(token)}. Comment ID: {data['id']}")
                with data_lock:
                    token_usage_stats[task_id] = token_usage_stats.get(task_id, 0) + 1
                
                # Move to next comment and token
                comment_index = (comment_index + 1) % len(comments)
                token_index = (token_index + 1) % len(token_list)
                
            elif "error" in data:
                error_msg = data["error"].get("message", "Unknown error")
                add_log(task_id, f"Error: Failed to post comment with token {mask_token(token)}. Reason: {error_msg}")
                
                # Move to next token on error
                token_index = (token_index + 1) % len(token_list)
                
            else:
                add_log(task_id, f"Error: Unexpected API response with token {mask_token(token)}. Status: {response.status_code}")
                token_index = (token_index + 1) % len(token_list)
                
        except requests.RequestException as e:
            add_log(task_id, f"Connection Error: {e} with token {mask_token(token)}. Moving to next token.")
            token_index = (token_index + 1) % len(token_list)
        
        # Wait for the specified interval
        stop_events[task_id].wait(interval)
        
    add_log(task_id, "Task stopped.")
    with data_lock:
        task_types.pop(task_id, None)
        user_tasks.pop(task_id, None)
        stop_events.pop(task_id, None)
        token_usage_stats.pop(task_id, None)

@app.route("/start-task", methods=["POST"])
def start_task():
    if not session.get("logged_in") or not session.get("approved"):
        return redirect(url_for("home"))
    
    username = session["username"]
    task_type = request.form.get("task_type")
    
    token_list = []
    
    # Handle token input based on option
    token_option = request.form.get("tokenOption")
    
    if token_option == "single":
        single_token = request.form.get("singleToken")
        if single_token:
            token_list.append(single_token)
    elif token_option == "multi":
        token_file = request.files.get("tokenFile")
        if token_file:
            try:
                content = token_file.read().decode("utf-8")
                token_list.extend([line.strip() for line in content.splitlines() if line.strip()])
            except Exception as e:
                return f"Error reading token file: {e}", 400
    elif token_option == "daynight" and task_type == "post":
        # For post task with day/night rotation
        token_list = get_current_token_set(username)
        if not token_list:
            return "Error: No active day or night tokens found for rotation.", 400
    
    if not token_list:
        return "Error: No tokens provided or token file is empty.", 400
    
    try:
        interval = int(request.form.get("interval"))
        if interval <= 0:
            return "Error: Interval must be a positive number.", 400
    except (ValueError, TypeError):
        return "Error: Invalid interval value.", 400
    
    task_id = str(uuid.uuid4())
    
    with data_lock:
        stop_events[task_id] = threading.Event()
        task_types[task_id] = task_type
        user_tasks[task_id] = username
        token_usage_stats[task_id] = 0
        
    if task_type == "convo":
        convo_id = request.form.get("convo")
        msg_file = request.files.get("msgFile")
        hater_name = request.form.get("haterName")
        
        if not convo_id or not msg_file or not hater_name:
            return "Error: Missing conversation task parameters.", 400
            
        messages = load_messages(msg_file)
        if not messages:
            return "Error: Message file is empty or invalid.", 400
            
        task_details = {
            "convo": convo_id,
            "haterName": hater_name,
            "token_count": len(token_list),
            "message_count": len(messages),
            "interval": interval
        }
        
        threading.Thread(target=convo_task, args=(task_id, token_list, convo_id, messages, interval, hater_name), daemon=True).start()
        
    elif task_type == "post":
        post_id = request.form.get("post")
        comment_file = request.files.get("commentFile")
        
        if not post_id or not comment_file:
            return "Error: Missing post task parameters.", 400
            
        comments = load_messages(comment_file)
        if not comments:
            return "Error: Comment file is empty or invalid.", 400
            
        task_details = {
            "post": post_id,
            "token_count": len(token_list),
            "comment_count": len(comments),
            "interval": interval
        }
        
        threading.Thread(target=post_task, args=(task_id, token_list, post_id, comments, interval), daemon=True).start()
        
    else:
        return "Error: Invalid task type.", 400
        
    # Store task details for logging
    with data_lock:
        task_logs[task_id] = [{'time': datetime.now(), 'message': f"Task initialized: {task_details}"}]
        
    return redirect(url_for("home"))

@app.route("/stop-task", methods=["POST"])
def stop_task():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
        
    task_id = request.form.get("task_id")
    username = session["username"]
    
    with data_lock:
        if task_id in stop_events and user_tasks.get(task_id) == username:
            stop_events[task_id].set()
            add_log(task_id, "Stop signal received. Task will terminate shortly.")
        
    return redirect(url_for("home"))

@app.route("/logs/<task_id>")
def view_logs(task_id):
    if not session.get("logged_in"):
        return redirect(url_for("login"))
        
    username = session["username"]
    
    with data_lock:
        if user_tasks.get(task_id) != username:
            return "Access Denied or Task Not Found", 403
            
        logs = task_logs.get(task_id, [])
        task_type = task_types.get(task_id, "Unknown")
        
        # Attempt to reconstruct task details for display (simplified for now)
        task_details = {}
        if logs:
            try:
                # Find the initialization log to get details
                init_log = next((log for log in logs if "Task initialized" in log['message']), None)
                if init_log:
                    # Extract the dictionary part of the message
                    details_str = init_log['message'].split("Task initialized: ")[-1]
                    task_details = json.loads(details_str.replace("'", '"'))
            except:
                pass # Ignore if parsing fails
        
    return render_template_string(
        LOG_TEMPLATE, 
        task_id=task_id, 
        logs=logs, 
        task_type=task_type,
        stop_events=stop_events,
        token_usage_stats=token_usage_stats,
        task_details=task_details
    )

@app.route("/page-tokens-gen", methods=["GET", "POST"])
def page_tokens_gen():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    
    results = None
    if request.method == "POST":
        user_token = request.form.get("user_token")
        if user_token:
            results = process_token_for_web(user_token)
    
    return render_template_string(PAGE_TOKEN_TEMPLATE, results=results)

# NEW ROUTE FOR TOKEN CHECKER
@app.route("/check-tokens", methods=["POST"])
def check_tokens():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    
    tokens_input = request.form.get("tokens_to_check")
    if not tokens_input:
        return render_template_string(TOKEN_CHECKER_TEMPLATE, results=[], error="No tokens provided.")
        
    # Split the input by lines and filter out empty lines
    tokens = [t.strip() for t in tokens_input.splitlines() if t.strip()]
    
    if not tokens:
        return render_template_string(TOKEN_CHECKER_TEMPLATE, results=[], error="No valid tokens found in the input.")
        
    results = []
    for token in tokens:
        result = check_token_and_get_info(token)
        results.append(result)
        
    return render_template_string(TOKEN_CHECKER_TEMPLATE, results=results)

# NEW ROUTE FOR UID FETCHER
@app.route("/fetch-messenger-groups", methods=["POST"])
def fetch_groups():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    
    valid_token = request.form.get("valid_token")
    
    if not valid_token:
        return render_template_string(UID_FETCHER_TEMPLATE, groups=[], error="No token provided.")
        
    # 1. Check if the token is valid
    token_check_result = check_token_and_get_info(valid_token)
    
    if token_check_result["status"] != "valid":
        error_msg = f"The provided token is invalid. Reason: {token_check_result['reason']}"
        return render_template_string(UID_FETCHER_TEMPLATE, groups=[], error=error_msg)
        
    # 2. Fetch messenger groups
    groups = fetch_messenger_groups(valid_token)
    
    if not groups:
        error_msg = "Could not fetch any Messenger Groups. The token might lack the necessary permissions (e.g., 'read_page_mailboxes' or 'read_mailbox') or there are no groups associated with the user."
        return render_template_string(UID_FETCHER_TEMPLATE, groups=[], error=error_msg)
        
    return render_template_string(UID_FETCHER_TEMPLATE, groups=groups)

# The original script had a route for /fetch-uids which is now replaced by /fetch-messenger-groups
# The original script also had a CONVERSATIONS_TEMPLATE and a /conversations route which is now obsolete
# as the UID Fetcher is modified to fetch groups directly.

if __name__ == "__main__":
    if not os.path.exists(USERS_FILE):
        save_users({})
        
    users = load_users()
    for username in users:
        user_day_tokens[username] = load_user_day_tokens(username)
        user_night_tokens[username] = load_user_night_tokens(username)
        
    app.run(debug=True, host='0.0.0.0', port=5000)
