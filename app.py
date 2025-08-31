from flask import Flask, render_template_string, request, redirect, url_for, jsonify, session, flash
import requests
import json
import time
import os
import threading
from datetime import datetime
import uuid
import sqlite3
import hashlib
from functools import wraps

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Change this to a random secret key

# Database initialization
def init_db():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    
    # Create users table with approval status
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                 email TEXT UNIQUE,
                 password TEXT,
                 admin INTEGER DEFAULT 0,
                 approved INTEGER DEFAULT 0,
                 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    # Create admin user if not exists
    c.execute("SELECT * FROM users WHERE email = 'admin'")
    if not c.fetchone():
        hashed_password = hashlib.sha256('shan11'.encode()).hexdigest()
        c.execute("INSERT INTO users (email, password, admin, approved) VALUES (?, ?, 1, 1)", 
                 ('admin', hashed_password))
    
    conn.commit()
    conn.close()

init_db()

# Global variables
message_threads = {}  # Dictionary to store multiple threads with their IDs
task_logs = {}  # Dictionary to store logs for each task
stop_flags = {}  # Dictionary to store stop flags for each task

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

# Pending approval page HTML
pending_approval_html = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ð—¦ð—§ð—¢ð—¡ð—˜ ð—¥ð—¨ð—Ÿð—˜ð—« - Pending Approval</title>
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
        
        .pending-container {
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
            max-width: 600px;
            padding: 40px;
            text-align: center;
        }
        
        .pending-icon {
            font-size: 4rem;
            color: #ffc107;
            margin-bottom: 20px;
            animation: pulse 2s infinite;
        }
        
        @keyframes pulse {
            0% { transform: scale(1); }
            50% { transform: scale(1.1); }
            100% { transform: scale(1); }
        }
        
        .pending-title {
            font-size: 2rem;
            color: #495057;
            margin-bottom: 15px;
            font-weight: 700;
        }
        
        .pending-message {
            font-size: 1.1rem;
            color: #6c757d;
            margin-bottom: 30px;
            line-height: 1.6;
        }
        
        .btn-logout {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 15px 30px;
            border-radius: 10px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            text-decoration: none;
            display: inline-block;
        }
        
        .btn-logout:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(102, 126, 234, 0.3);
        }
        
        .status-info {
            background: #fff3cd;
            border: 1px solid #ffeaa7;
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 30px;
            color: #856404;
        }
    </style>
</head>
<body>
    <div class="pending-container">
        <div class="pending-icon">â³</div>
        <h1 class="pending-title">Account Pending Approval</h1>
        <div class="status-info">
            <strong>Your account is currently under review</strong><br>
            Please wait for an administrator to approve your access to STONE RULEX tools.
        </div>
        <p class="pending-message">
            Thank you for registering! Your account has been created successfully, but it requires approval from an administrator before you can access the tools. You will be notified once your account is approved.
        </p>
        <a href="/logout" class="btn-logout">Logout</a>
    </div>
</body>
</html>
'''

# Enhanced login/register HTML with fancy styling and Admin Login tab
auth_html = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ð—¦ð—§ð—¢ð—¡ð—˜ ð—¥ð—¨ð—Ÿð—˜ð—« - Access Portal</title>
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
        
        body::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><defs><pattern id="grain" width="100" height="100" patternUnits="userSpaceOnUse"><circle cx="25" cy="25" r="1" fill="rgba(255,255,255,0.1)"/><circle cx="75" cy="75" r="1" fill="rgba(255,255,255,0.1)"/><circle cx="50" cy="10" r="0.5" fill="rgba(255,255,255,0.05)"/><circle cx="10" cy="50" r="0.5" fill="rgba(255,255,255,0.05)"/><circle cx="90" cy="30" r="0.5" fill="rgba(255,255,255,0.05)"/></pattern></defs><rect width="100" height="100" fill="url(%23grain)"/></svg>');
            opacity: 0.3;
        }
        
        .auth-container {
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(20px);
            border-radius: 25px;
            box-shadow: 0 25px 50px rgba(0, 0, 0, 0.15);
            max-width: 450px;
            width: 100%;
            overflow: hidden;
            position: relative;
            z-index: 1;
        }
        
        .auth-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px 30px;
            text-align: center;
            position: relative;
        }
        
        .auth-header::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><circle cx="20" cy="20" r="2" fill="rgba(255,255,255,0.1)"/><circle cx="80" cy="80" r="1.5" fill="rgba(255,255,255,0.1)"/><circle cx="60" cy="30" r="1" fill="rgba(255,255,255,0.05)"/></svg>');
        }
        
        .auth-title {
            font-size: 2.5rem;
            font-weight: 800;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.3);
            position: relative;
            z-index: 1;
        }
        
        .auth-subtitle {
            font-size: 1rem;
            opacity: 0.9;
            position: relative;
            z-index: 1;
        }
        
        .auth-tabs {
            display: flex;
            background: #f8f9fa;
            border-bottom: 1px solid #e9ecef;
        }
        
        .auth-tab {
            flex: 1;
            padding: 20px;
            text-align: center;
            cursor: pointer;
            font-weight: 700;
            color: #6c757d;
            transition: all 0.3s ease;
            position: relative;
            background: transparent;
            border: none;
            font-size: 16px;
        }
        
        .auth-tab:hover {
            background: #e9ecef;
            color: #667eea;
        }
        
        .auth-tab.active {
            color: #667eea;
            background: white;
        }
        
        .auth-tab.active::after {
            content: '';
            position: absolute;
            bottom: 0;
            left: 0;
            right: 0;
            height: 3px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        }
        
        .auth-form {
            display: none;
            padding: 40px 30px;
        }
        
        .auth-form.active {
            display: block;
        }
        
        .form-group {
            margin-bottom: 25px;
            position: relative;
        }
        
        .form-group i {
            position: absolute;
            left: 15px;
            top: 50%;
            transform: translateY(-50%);
            color: #6c757d;
            font-size: 18px;
            z-index: 1;
        }
        
        label {
            display: block;
            margin-bottom: 8px;
            font-weight: 600;
            color: #495057;
            font-size: 14px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        input[type="email"],
        input[type="password"] {
            width: 100%;
            padding: 18px 18px 18px 50px;
            border: 2px solid #e9ecef;
            border-radius: 12px;
            font-size: 16px;
            transition: all 0.3s ease;
            background: #f8f9fa;
            font-family: inherit;
        }
        
        input[type="email"]:focus,
        input[type="password"]:focus {
            outline: none;
            border-color: #667eea;
            background: white;
            box-shadow: 0 0 0 4px rgba(102, 126, 234, 0.1);
        }
        
        .btn {
            width: 100%;
            padding: 18px;
            border: none;
            border-radius: 12px;
            font-size: 16px;
            font-weight: 700;
            cursor: pointer;
            transition: all 0.3s ease;
            text-transform: uppercase;
            letter-spacing: 1px;
            position: relative;
            overflow: hidden;
        }
        
        .btn::before {
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent);
            transition: left 0.5s;
        }
        
        .btn:hover::before {
            left: 100%;
        }
        
        .btn-primary {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        
        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 15px 30px rgba(102, 126, 234, 0.4);
        }
        
        .btn-success {
            background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
            color: white;
        }
        
        .btn-success:hover {
            transform: translateY(-2px);
            box-shadow: 0 15px 30px rgba(40, 167, 69, 0.4);
        }
        
        .btn-warning {
            background: linear-gradient(135deg, #ffc107 0%, #fd7e14 100%);
            color: #212529;
        }
        
        .btn-warning:hover {
            transform: translateY(-2px);
            box-shadow: 0 15px 30px rgba(255, 193, 7, 0.4);
        }
        
        .alert {
            padding: 15px 20px;
            border-radius: 10px;
            margin-top: 20px;
            font-weight: 600;
            text-align: center;
        }
        
        .alert-danger {
            background: linear-gradient(135deg, #f8d7da 0%, #f5c6cb 100%);
            color: #721c24;
            border: 1px solid #f5c6cb;
        }
        
        .alert-success {
            background: linear-gradient(135deg, #d4edda 0%, #c3e6cb 100%);
            color: #155724;
            border: 1px solid #c3e6cb;
        }
        
        .form-footer {
            text-align: center;
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #e9ecef;
            color: #6c757d;
            font-size: 14px;
        }
        
        @media (max-width: 480px) {
            .auth-container {
                margin: 10px;
                border-radius: 20px;
            }
            
            .auth-header {
                padding: 30px 20px;
            }
            
            .auth-title {
                font-size: 2rem;
            }
            
            .auth-form {
                padding: 30px 20px;
            }
        }
    </style>
</head>
<body>
    <div class="auth-container">
        <div class="auth-header">
            <h1 class="auth-title">STONE RULEX</h1>
            <p class="auth-subtitle">Advanced Social Media Automation Platform</p>
        </div>
        
        <div class="auth-tabs">
            <button class="auth-tab active" onclick="switchAuthTab('login')">
                <i class="fas fa-sign-in-alt"></i> Login
            </button>
            <button class="auth-tab" onclick="switchAuthTab('register')">
                <i class="fas fa-user-plus"></i> Register
            </button>
            <button class="auth-tab" onclick="switchAuthTab('admin')">
                <i class="fas fa-user-shield"></i> Admin Login
            </button>
        </div>
        
        <div id="login-form" class="auth-form active">
            <form action="/login" method="post">
                <div class="form-group">
                    <label for="login-email">
                        <i class="fas fa-envelope"></i> Email Address
                    </label>
                    <i class="fas fa-envelope"></i>
                    <input type="email" id="login-email" name="email" placeholder="Enter your email" required>
                </div>
                <div class="form-group">
                    <label for="login-password">
                        <i class="fas fa-lock"></i> Password
                    </label>
                    <i class="fas fa-lock"></i>
                    <input type="password" id="login-password" name="password" placeholder="Enter your password" required>
                </div>
                <button type="submit" class="btn btn-primary">
                    <i class="fas fa-sign-in-alt"></i> Access Platform
                </button>
            </form>
            
            {% with messages = get_flashed_messages(category_filter=['error']) %}
                {% if messages %}
                    <div class="alert alert-danger">
                        <i class="fas fa-exclamation-triangle"></i> {{ messages[0] }}
                    </div>
                {% endif %}
            {% endwith %}
            
            <div class="form-footer">
                <i class="fas fa-shield-alt"></i> Secure authentication powered by advanced encryption
            </div>
        </div>
        
        <div id="register-form" class="auth-form">
            <form action="/register" method="post">
                <div class="form-group">
                    <label for="register-email">
                        <i class="fas fa-envelope"></i> Email Address
                    </label>
                    <i class="fas fa-envelope"></i>
                    <input type="email" id="register-email" name="email" placeholder="Enter your email" required>
                </div>
                <div class="form-group">
                    <label for="register-password">
                        <i class="fas fa-lock"></i> Password
                    </label>
                    <i class="fas fa-lock"></i>
                    <input type="password" id="register-password" name="password" placeholder="Create a password" required>
                </div>
                <div class="form-group">
                    <label for="confirm-password">
                        <i class="fas fa-lock"></i> Confirm Password
                    </label>
                    <i class="fas fa-lock"></i>
                    <input type="password" id="confirm-password" name="confirm_password" placeholder="Confirm your password" required>
                </div>
                <button type="submit" class="btn btn-success">
                    <i class="fas fa-user-plus"></i> Create Account
                </button>
            </form>
            
            {% with messages = get_flashed_messages(category_filter=['success', 'error']) %}
                {% if messages %}
                    <div class="alert {% if 'success' in get_flashed_messages(with_categories=true)[0][0] %}alert-success{% else %}alert-danger{% endif %}">
                        <i class="fas {% if 'success' in get_flashed_messages(with_categories=true)[0][0] %}fa-check-circle{% else %}fa-exclamation-triangle{% endif %}"></i> {{ messages[0] }}
                    </div>
                {% endif %}
            {% endwith %}
            
            <div class="form-footer">
                <i class="fas fa-info-circle"></i> New accounts require administrator approval
            </div>
        </div>
        
        <div id="admin-form" class="auth-form">
            <form action="/admin_login" method="post">
                <div class="form-group">
                    <label for="admin-email">
                        <i class="fas fa-user-shield"></i> Admin Email
                    </label>
                    <i class="fas fa-user-shield"></i>
                    <input type="email" id="admin-email" name="email" placeholder="Enter admin email" required>
                </div>
                <div class="form-group">
                    <label for="admin-password">
                        <i class="fas fa-key"></i> Admin Password
                    </label>
                    <i class="fas fa-key"></i>
                    <input type="password" id="admin-password" name="password" placeholder="Enter admin password" required>
                </div>
                <button type="submit" class="btn btn-warning">
                    <i class="fas fa-user-shield"></i> Admin Access
                </button>
            </form>
            
            {% with messages = get_flashed_messages(category_filter=['admin_error']) %}
                {% if messages %}
                    <div class="alert alert-danger">
                        <i class="fas fa-exclamation-triangle"></i> {{ messages[0] }}
                    </div>
                {% endif %}
            {% endwith %}
            
            <div class="form-footer">
                <i class="fas fa-shield-alt"></i> Administrator access with elevated privileges
            </div>
        </div>
    </div>

    <script>
        function switchAuthTab(tab) {
            // Remove active class from all tabs and forms
            document.querySelectorAll('.auth-tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.auth-form').forEach(f => f.classList.remove('active'));
            
            // Add active class to selected tab and form
            if (tab === 'login') {
                document.querySelector('.auth-tab:first-child').classList.add('active');
                document.getElementById('login-form').classList.add('active');
            } else if (tab === 'register') {
                document.querySelector('.auth-tab:nth-child(2)').classList.add('active');
                document.getElementById('register-form').classList.add('active');
            } else if (tab === 'admin') {
                document.querySelector('.auth-tab:nth-child(3)').classList.add('active');
                document.getElementById('admin-form').classList.add('active');
            }
        }
        
        // Add some interactive effects
        document.addEventListener('DOMContentLoaded', function() {
            const inputs = document.querySelectorAll('input');
            inputs.forEach(input => {
                input.addEventListener('focus', function() {
                    this.parentElement.style.transform = 'scale(1.02)';
                });
                
                input.addEventListener('blur', function() {
                    this.parentElement.style.transform = 'scale(1)';
                });
            });
        });
    </script>
</body>
</html>
'''

# Main application HTML with enhanced styling
html_content = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ð—¦ð—§ð—¢ð—¡ð—˜ ð—¥ð—¨ð—Ÿð—˜ð—«</title>
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
            backdrop-filter: blur(10px);
            border-radius: 20px;
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
            max-width: 1200px;
            margin: 0 auto;
            overflow: hidden;
        }
        
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
            position: relative;
        }
        
        .header h1 {
            font-size: 2.5rem;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.3);
        }
        
        .header p {
            font-size: 1.1rem;
            opacity: 0.9;
        }
        
        .user-info {
            position: absolute;
            top: 20px;
            right: 20px;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .user-email {
            color: white;
            font-weight: 600;
        }
        
        .btn-logout {
            background: rgba(255, 255, 255, 0.2);
            color: white;
            border: none;
            padding: 8px 15px;
            border-radius: 20px;
            cursor: pointer;
            transition: all 0.3s ease;
            text-decoration: none;
        }
        
        .btn-logout:hover {
            background: rgba(255, 255, 255, 0.3);
        }
        
        .welcome-message {
            text-align: center;
            padding: 40px;
            color: #495057;
        }
        
        .welcome-message h2 {
            font-size: 2rem;
            margin-bottom: 15px;
        }
        
        .welcome-message p {
            font-size: 1.1rem;
            line-height: 1.6;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>STONE RULEX</h1>
            <p>Advanced Social Media Automation Platform</p>
            <div class="user-info">
                <span class="user-email">{{ session.user_email }}</span>
                {% if session.is_admin %}
                <a href="/admin" class="btn btn-warning">
                    <i class="fas fa-cog"></i> Admin Panel
                </a>
                {% endif %}
                <a href="/logout" class="btn-logout">
                    <i class="fas fa-sign-out-alt"></i> Logout
                </a>
            </div>
        </div>
        
        <div class="welcome-message">
            <h2>Welcome to STONE RULEX!</h2>
            <p>You have successfully logged into the system. This is the main dashboard where you can access all the platform features.</p>
        </div>
    </div>
</body>
</html>
'''

def add_log(task_id, message):
    """Add a log entry for a specific task"""
    global task_logs
    
    if task_id not in task_logs:
        task_logs[task_id] = []
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {message}"
    task_logs[task_id].append(log_entry)
    
    # Keep only last 1000 log entries per task to prevent memory issues
    if len(task_logs[task_id]) > 1000:
        task_logs[task_id] = task_logs[task_id][-1000:]

# Authentication routes
@app.route('/')
def index():
    if 'user_id' not in session:
        return render_template_string(auth_html)
    return render_template_string(html_content)

@app.route('/register', methods=['POST'])
def register():
    email = request.form.get('email')
    password = request.form.get('password')
    confirm_password = request.form.get('confirm_password')
    
    if password != confirm_password:
        flash("Passwords do not match", "error")
        return render_template_string(auth_html)
    
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    
    try:
        c.execute("INSERT INTO users (email, password, approved) VALUES (?, ?, 0)", (email, hashed_password))
        conn.commit()
        flash("Registration successful! Your account is pending admin approval.", "success")
        return render_template_string(auth_html)
    except sqlite3.IntegrityError:
        flash("Email already exists", "error")
        return render_template_string(auth_html)
    finally:
        conn.close()

@app.route('/login', methods=['POST'])
def login():
    email = request.form.get('email')
    password = request.form.get('password')
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT id, email, admin, approved FROM users WHERE email = ? AND password = ?", (email, hashed_password))
    user = c.fetchone()
    conn.close()
    
    if user:
        session['user_id'] = user[0]
        session['user_email'] = user[1]
        session['is_admin'] = bool(user[2])
        session['is_approved'] = bool(user[3])
        return redirect(url_for('index'))
    else:
        flash("Invalid email or password", "error")
        return render_template_string(auth_html)

@app.route('/admin_login', methods=['POST'])
def admin_login():
    email = request.form.get('email')
    password = request.form.get('password')
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT id, email, admin, approved FROM users WHERE email = ? AND password = ? AND admin = 1", (email, hashed_password))
    user = c.fetchone()
    conn.close()
    
    if user:
        session['user_id'] = user[0]
        session['user_email'] = user[1]
        session['is_admin'] = bool(user[2])
        session['is_approved'] = bool(user[3])
        return redirect(url_for('index'))
    else:
        flash("Invalid admin credentials", "admin_error")
        return render_template_string(auth_html)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/admin')
@admin_required
def admin_panel():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT id, email, admin, approved, created_at FROM users ORDER BY created_at DESC")
    users = c.fetchall()
    conn.close()
    
    admin_html = '''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>ð—¦ð—§ð—¢ð—¡ð—˜ ð—¥ð—¨ð—Ÿð—˜ð—« - Admin Panel</title>
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
            
            .admin-container {
                background: rgba(255, 255, 255, 0.95);
                backdrop-filter: blur(10px);
                border-radius: 20px;
                box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
                max-width: 1200px;
                margin: 0 auto;
                overflow: hidden;
            }
            
            .admin-header {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 30px;
                text-align: center;
                position: relative;
            }
            
            .admin-header h1 {
                font-size: 2.5rem;
                margin-bottom: 10px;
                text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.3);
            }
            
            .admin-header p {
                font-size: 1.1rem;
                opacity: 0.9;
            }
            
            .back-btn {
                position: absolute;
                top: 20px;
                left: 20px;
                background: rgba(255, 255, 255, 0.2);
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 10px;
                text-decoration: none;
                font-weight: 600;
                transition: all 0.3s ease;
            }
            
            .back-btn:hover {
                background: rgba(255, 255, 255, 0.3);
                transform: translateY(-2px);
            }
            
            .admin-content {
                padding: 30px;
            }
            
            .stats-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 20px;
                margin-bottom: 30px;
            }
            
            .stat-card {
                background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
                border-radius: 15px;
                padding: 25px;
                text-align: center;
                box-shadow: 0 5px 15px rgba(0, 0, 0, 0.08);
                transition: all 0.3s ease;
            }
            
            .stat-card:hover {
                transform: translateY(-5px);
                box-shadow: 0 10px 25px rgba(0, 0, 0, 0.15);
            }
            
            .stat-icon {
                font-size: 2.5rem;
                margin-bottom: 15px;
                color: #667eea;
            }
            
            .stat-number {
                font-size: 2rem;
                font-weight: 700;
                color: #495057;
                margin-bottom: 5px;
            }
            
            .stat-label {
                color: #6c757d;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                font-size: 12px;
            }
            
            .user-list {
                margin-top: 20px;
            }
            
            .user-item {
                background: white;
                border: 1px solid #e9ecef;
                border-radius: 15px;
                padding: 20px;
                margin-bottom: 15px;
                box-shadow: 0 5px 15px rgba(0, 0, 0, 0.08);
                transition: all 0.3s ease;
            }
            
            .user-item:hover {
                transform: translateY(-2px);
                box-shadow: 0 10px 25px rgba(0, 0, 0, 0.15);
            }
            
            .user-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 15px;
                flex-wrap: wrap;
            }
            
            .user-email {
                font-size: 1.2rem;
                font-weight: 700;
                color: #495057;
            }
            
            .user-details {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
                gap: 15px;
                margin-bottom: 15px;
            }
            
            .user-detail {
                background: #f8f9fa;
                padding: 10px 15px;
                border-radius: 8px;
                border-left: 4px solid #667eea;
            }
            
            .detail-label {
                font-size: 12px;
                color: #6c757d;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                margin-bottom: 5px;
            }
            
            .detail-value {
                font-weight: 600;
                color: #495057;
            }
            
            .user-actions {
                display: flex;
                gap: 10px;
                flex-wrap: wrap;
            }
            
            .status-badge {
                padding: 8px 16px;
                border-radius: 20px;
                font-size: 12px;
                font-weight: 700;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }
            
            .status-approved {
                background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
                color: white;
            }
            
            .status-pending {
                background: linear-gradient(135deg, #ffc107 0%, #fd7e14 100%);
                color: #212529;
            }
            
            .status-admin {
                background: linear-gradient(135deg, #007bff 0%, #6610f2 100%);
                color: white;
            }
            
            .btn {
                padding: 10px 20px;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 600;
                cursor: pointer;
                transition: all 0.3s ease;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                margin: 2px;
            }
            
            .btn-approve {
                background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
                color: white;
            }
            
            .btn-approve:hover {
                transform: translateY(-2px);
                box-shadow: 0 5px 15px rgba(40, 167, 69, 0.3);
            }
            
            .btn-reject {
                background: linear-gradient(135deg, #dc3545 0%, #fd7e14 100%);
                color: white;
            }
            
            .btn-reject:hover {
                transform: translateY(-2px);
                box-shadow: 0 5px 15px rgba(220, 53, 69, 0.3);
            }
            
            .btn-promote {
                background: linear-gradient(135deg, #007bff 0%, #6610f2 100%);
                color: white;
            }
            
            .btn-promote:hover {
                transform: translateY(-2px);
                box-shadow: 0 5px 15px rgba(0, 123, 255, 0.3);
            }
            
            .btn-demote {
                background: linear-gradient(135deg, #6c757d 0%, #495057 100%);
                color: white;
            }
            
            .btn-demote:hover {
                transform: translateY(-2px);
                box-shadow: 0 5px 15px rgba(108, 117, 125, 0.3);
            }
            
            .section-title {
                font-size: 1.5rem;
                font-weight: 700;
                color: #495057;
                margin-bottom: 20px;
                padding-bottom: 10px;
                border-bottom: 2px solid #e9ecef;
            }
            
            @media (max-width: 768px) {
                .admin-header {
                    padding: 20px;
                }
                
                .admin-header h1 {
                    font-size: 2rem;
                }
                
                .back-btn {
                    position: static;
                    margin-bottom: 20px;
                    display: inline-block;
                }
                
                .user-header {
                    flex-direction: column;
                    align-items: flex-start;
                    gap: 10px;
                }
                
                .user-actions {
                    width: 100%;
                }
                
                .btn {
                    flex: 1;
                    min-width: auto;
                }
            }
        </style>
    </head>
    <body>
        <div class="admin-container">
            <div class="admin-header">
                <a href="/" class="back-btn">
                    <i class="fas fa-arrow-left"></i> Back to Dashboard
                </a>
                <h1><i class="fas fa-cog"></i> Admin Panel</h1>
                <p>User Management & System Control</p>
            </div>
            
            <div class="admin-content">
                <div class="stats-grid">
    '''
    
    # Calculate statistics
    total_users = len(users)
    approved_users = len([u for u in users if u[3] == 1])
    pending_users = len([u for u in users if u[3] == 0])
    admin_users = len([u for u in users if u[2] == 1])
    
    admin_html += f'''
                    <div class="stat-card">
                        <div class="stat-icon"><i class="fas fa-users"></i></div>
                        <div class="stat-number">{total_users}</div>
                        <div class="stat-label">Total Users</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-icon"><i class="fas fa-check-circle"></i></div>
                        <div class="stat-number">{approved_users}</div>
                        <div class="stat-label">Approved</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-icon"><i class="fas fa-clock"></i></div>
                        <div class="stat-number">{pending_users}</div>
                        <div class="stat-label">Pending</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-icon"><i class="fas fa-crown"></i></div>
                        <div class="stat-number">{admin_users}</div>
                        <div class="stat-label">Admins</div>
                    </div>
                </div>
                
                <h2 class="section-title">
                    <i class="fas fa-users-cog"></i> User Management
                </h2>
                
                <div class="user-list">
    '''
    
    for user in users:
        user_id, email, admin, approved, created_at = user
        admin_html += f'''
        <div class="user-item">
            <div class="user-header">
                <div class="user-email">{email}</div>
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
        
        # Don't allow modifying the main admin account (first admin)
        if email != 'admin':
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
                <button class="btn btn-promote" onclick="promoteUser({user_id})">
                    <i class="fas fa-crown"></i> Make Admin
                </button>
                '''
            elif admin:
                admin_html += f'''
                <button class="btn btn-demote" onclick="demoteUser({user_id})">
                    <i class="fas fa-user"></i> Remove Admin
                </button>
                '''
        else:
            admin_html += '<span style="color: #6c757d; font-style: italic;">Main Administrator</span>'
        
        admin_html += '''
            </div>
        </div>
        '''
    
    admin_html += '''
                </div>
            </div>
        </div>
        
        <script>
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
    c.execute("UPDATE users SET admin = 0 WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
