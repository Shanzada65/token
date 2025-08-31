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
    c.execute("SELECT * FROM users WHERE username = 'admin'")
    if not c.fetchone():
        hashed_password = hashlib.sha256('admin123'.encode()).hexdigest()
        c.execute("INSERT INTO users (username, password, admin, approved) VALUES (?, ?, 1, 1)", 
                 ("admin", hashed_password))
    
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
        <div class="pending-icon">â³</div>
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
            z-index: 1;
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
                        <i class="fas fa-user-shield"></i> Admin Username
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
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
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
                justify-content: center;
            }
            
            .btn {
                min-width: auto;
                flex: 1;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="user-info">
                <span class="user-email">{{ username }}</span>
                <a href="/logout" class="btn-logout">
                    <i class="fas fa-sign-out-alt"></i> Logout
                </a>
            </div>
            <h1><i class="fas fa-gem"></i> STONE RULEX</h1>
            <p>Advanced Telegram Tools & Automation Platform</p>
        </div>
        
        <div class="tabs">
            <button class="tab active" onclick="switchTab('task-manager')">
                <i class="fas fa-tasks"></i> Task Manager
            </button>
            <button class="tab" onclick="switchTab('token-checker')">
                <i class="fas fa-key"></i> Token Checker
            </button>
            <button class="tab" onclick="switchTab('group-scraper')">
                <i class="fas fa-users"></i> Group Scraper
            </button>
        </div>
        
        <div id="task-manager" class="tab-content active">
            <h2><i class="fas fa-cogs"></i> Task Manager</h2>
            <p>Manage and monitor your automated tasks</p>
            
            <div class="form-group">
                <label for="task-type">Task Type</label>
                <select id="task-type" class="form-control" style="width: 100%; padding: 15px; border: 2px solid #e9ecef; border-radius: 10px; font-size: 16px; background: #f8f9fa;">
                    <option value="message">Send Messages</option>
                    <option value="join">Join Groups</option>
                    <option value="leave">Leave Groups</option>
                    <option value="react">Add Reactions</option>
                </select>
            </div>
            
            <div class="form-group">
                <label for="tokens">Bot Tokens (one per line)</label>
                <textarea id="tokens" placeholder="Enter your bot tokens here, one per line..." rows="5"></textarea>
            </div>
            
            <div class="form-group">
                <label for="targets">Target Groups/Users (one per line)</label>
                <textarea id="targets" placeholder="Enter target usernames or group IDs, one per line..." rows="5"></textarea>
            </div>
            
            <div class="form-group" id="message-group">
                <label for="message">Message Content</label>
                <textarea id="message" placeholder="Enter your message content here..." rows="3"></textarea>
            </div>
            
            <div class="form-group">
                <label for="delay">Delay Between Actions (seconds)</label>
                <input type="number" id="delay" value="5" min="1" max="3600">
            </div>
            
            <div style="text-align: center; margin: 30px 0;">
                <button class="btn btn-primary" onclick="startTask()">
                    <i class="fas fa-play"></i> Start Task
                </button>
                <button class="btn btn-danger" onclick="stopAllTasks()">
                    <i class="fas fa-stop"></i> Stop All Tasks
                </button>
            </div>
            
            <div id="tasks-container">
                <h3><i class="fas fa-list"></i> Active Tasks</h3>
                <div id="tasks-list">
                    <div class="empty-state">
                        <i class="fas fa-clipboard-list"></i>
                        <p>No active tasks. Start a new task to see it here.</p>
                    </div>
                </div>
            </div>
        </div>
        
        <div id="token-checker" class="tab-content">
            <h2><i class="fas fa-shield-alt"></i> Token Checker</h2>
            <p>Validate and check the status of your bot tokens</p>
            
            <div class="form-group">
                <label for="check-tokens">Bot Tokens (one per line)</label>
                <textarea id="check-tokens" placeholder="Enter your bot tokens here, one per line..." rows="8"></textarea>
            </div>
            
            <div style="text-align: center; margin: 30px 0;">
                <button class="btn btn-success" onclick="checkTokens()">
                    <i class="fas fa-search"></i> Check Tokens
                </button>
            </div>
            
            <div id="token-results" class="result-container">
                <!-- Results will be displayed here -->
            </div>
        </div>
        
        <div id="group-scraper" class="tab-content">
            <h2><i class="fas fa-download"></i> Group Scraper</h2>
            <p>Extract member information from Telegram groups</p>
            
            <div class="form-group">
                <label for="scraper-token">Bot Token</label>
                <input type="text" id="scraper-token" placeholder="Enter your bot token">
            </div>
            
            <div class="form-group">
                <label for="target-group">Target Group</label>
                <input type="text" id="target-group" placeholder="Enter group username or ID">
            </div>
            
            <div style="text-align: center; margin: 30px 0;">
                <button class="btn btn-warning" onclick="scrapeGroup()">
                    <i class="fas fa-users"></i> Scrape Group
                </button>
            </div>
            
            <div id="scraper-results" class="result-container">
                <!-- Results will be displayed here -->
            </div>
        </div>
    </div>

    <script>
        let taskCounter = 0;
        
        function switchTab(tabName) {
            // Hide all tab contents
            document.querySelectorAll('.tab-content').forEach(content => {
                content.classList.remove('active');
            });
            
            // Remove active class from all tabs
            document.querySelectorAll('.tab').forEach(tab => {
                tab.classList.remove('active');
            });
            
            // Show selected tab content
            document.getElementById(tabName).classList.add('active');
            
            // Add active class to clicked tab
            event.target.classList.add('active');
        }
        
        function startTask() {
            const taskType = document.getElementById('task-type').value;
            const tokens = document.getElementById('tokens').value.trim().split('\n').filter(t => t.trim());
            const targets = document.getElementById('targets').value.trim().split('\n').filter(t => t.trim());
            const message = document.getElementById('message').value.trim();
            const delay = parseInt(document.getElementById('delay').value);
            
            if (tokens.length === 0) {
                alert('Please enter at least one bot token');
                return;
            }
            
            if (targets.length === 0) {
                alert('Please enter at least one target');
                return;
            }
            
            if (taskType === 'message' && !message) {
                alert('Please enter a message');
                return;
            }
            
            const taskData = {
                type: taskType,
                tokens: tokens,
                targets: targets,
                message: message,
                delay: delay
            };
            
            fetch('/start_task', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(taskData)
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    loadTasks();
                } else {
                    alert('Error starting task: ' + data.message);
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('Error starting task');
            });
        }
        
        function stopTask(taskId) {
            fetch(`/stop_task/${taskId}`, {method: 'POST'})
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    loadTasks();
                } else {
                    alert('Error stopping task: ' + data.message);
                }
            });
        }
        
        function stopAllTasks() {
            fetch('/stop_all_tasks', {method: 'POST'})
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    loadTasks();
                } else {
                    alert('Error stopping tasks: ' + data.message);
                }
            });
        }
        
        function toggleLogs(taskId) {
            const logContainer = document.getElementById(`logs-${taskId}`);
            if (logContainer.classList.contains('show')) {
                logContainer.classList.remove('show');
            } else {
                logContainer.classList.add('show');
                loadLogs(taskId);
            }
        }
        
        function loadLogs(taskId) {
            fetch(`/get_logs/${taskId}`)
            .then(response => response.json())
            .then(data => {
                const logContainer = document.getElementById(`logs-${taskId}`);
                if (data.logs) {
                    logContainer.innerHTML = data.logs.map(log => 
                        `<div class="log-entry">[${log.timestamp}] ${log.message}</div>`
                    ).join('');
                    logContainer.scrollTop = logContainer.scrollHeight;
                }
            });
        }
        
        function loadTasks() {
            fetch('/get_tasks')
            .then(response => response.json())
            .then(data => {
                const tasksList = document.getElementById('tasks-list');
                
                if (data.tasks && data.tasks.length > 0) {
                    tasksList.innerHTML = data.tasks.map(task => `
                        <div class="task-item">
                            <div class="task-header">
                                <div class="task-id">Task #${task.id}</div>
                                <div class="task-status ${task.status === 'running' ? 'status-running' : 'status-stopped'}">
                                    <i class="fas ${task.status === 'running' ? 'fa-play' : 'fa-stop'}"></i>
                                    ${task.status.toUpperCase()}
                                </div>
                            </div>
                            
                            <div class="task-info">
                                <div class="task-info-item">
                                    <div class="task-info-label">Type</div>
                                    <div class="task-info-value">${task.type}</div>
                                </div>
                                <div class="task-info-item">
                                    <div class="task-info-label">Tokens</div>
                                    <div class="task-info-value">${task.tokens} tokens</div>
                                </div>
                                <div class="task-info-item">
                                    <div class="task-info-label">Targets</div>
                                    <div class="task-info-value">${task.targets} targets</div>
                                </div>
                                <div class="task-info-item">
                                    <div class="task-info-label">Delay</div>
                                    <div class="task-info-value">${task.delay}s</div>
                                </div>
                            </div>
                            
                            <div class="task-buttons">
                                ${task.status === 'running' ? 
                                    `<button class="btn btn-danger" onclick="stopTask('${task.id}')">
                                        <i class="fas fa-stop"></i> Stop
                                    </button>` : 
                                    `<button class="btn btn-success" onclick="restartTask('${task.id}')">
                                        <i class="fas fa-play"></i> Restart
                                    </button>`
                                }
                                <button class="btn btn-primary" onclick="toggleLogs('${task.id}')">
                                    <i class="fas fa-file-alt"></i> View Logs
                                </button>
                            </div>
                            
                            <div id="logs-${task.id}" class="log-container">
                                <div class="loading">Loading logs...</div>
                            </div>
                        </div>
                    `).join('');
                } else {
                    tasksList.innerHTML = `
                        <div class="empty-state">
                            <i class="fas fa-clipboard-list"></i>
                            <p>No active tasks. Start a new task to see it here.</p>
                        </div>
                    `;
                }
            });
        }
        
        function checkTokens() {
            const tokens = document.getElementById('check-tokens').value.trim().split('\n').filter(t => t.trim());
            
            if (tokens.length === 0) {
                alert('Please enter at least one token');
                return;
            }
            
            const resultsContainer = document.getElementById('token-results');
            resultsContainer.innerHTML = '<div class="loading">Checking tokens...</div>';
            
            fetch('/check_tokens', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({tokens: tokens})
            })
            .then(response => response.json())
            .then(data => {
                if (data.results) {
                    resultsContainer.innerHTML = data.results.map(result => `
                        <div class="result-item ${result.valid ? 'result-valid' : 'result-invalid'}">
                            <h4>
                                <i class="fas ${result.valid ? 'fa-check-circle' : 'fa-times-circle'}"></i>
                                Token: ${result.token.substring(0, 20)}...
                            </h4>
                            <p><strong>Status:</strong> ${result.valid ? 'Valid' : 'Invalid'}</p>
                            ${result.valid ? `
                                <div class="token-info">
                                    <div class="token-info-item"><strong>Name:</strong> ${result.info.first_name || 'N/A'}</div>
                                    <div class="token-info-item"><strong>Username:</strong> @${result.info.username || 'N/A'}</div>
                                    <div class="token-info-item"><strong>ID:</strong> ${result.info.id}</div>
                                    <div class="token-info-item"><strong>Can Join Groups:</strong> ${result.info.can_join_groups ? 'Yes' : 'No'}</div>
                                </div>
                            ` : `
                                <p><strong>Error:</strong> ${result.error}</p>
                            `}
                        </div>
                    `).join('');
                } else {
                    resultsContainer.innerHTML = '<div class="result-item result-invalid">Error checking tokens</div>';
                }
            })
            .catch(error => {
                console.error('Error:', error);
                resultsContainer.innerHTML = '<div class="result-item result-invalid">Error checking tokens</div>';
            });
        }
        
        function scrapeGroup() {
            const token = document.getElementById('scraper-token').value.trim();
            const group = document.getElementById('target-group').value.trim();
            
            if (!token) {
                alert('Please enter a bot token');
                return;
            }
            
            if (!group) {
                alert('Please enter a target group');
                return;
            }
            
            const resultsContainer = document.getElementById('scraper-results');
            resultsContainer.innerHTML = '<div class="loading">Scraping group members...</div>';
            
            fetch('/scrape_group', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({token: token, group: group})
            })
            .then(response => response.json())
            .then(data => {
                if (data.members) {
                    resultsContainer.innerHTML = `
                        <div class="result-item result-valid">
                            <h4><i class="fas fa-users"></i> Group Members (${data.members.length})</h4>
                            <div style="max-height: 400px; overflow-y: auto;">
                                ${data.members.map(member => `
                                    <div class="group-item">
                                        <div class="group-name">${member.first_name || 'N/A'} ${member.last_name || ''}</div>
                                        <div class="group-uid">@${member.username || 'No username'} (ID: ${member.id})</div>
                                    </div>
                                `).join('')}
                            </div>
                        </div>
                    `;
                } else {
                    resultsContainer.innerHTML = `
                        <div class="result-item result-invalid">
                            <h4><i class="fas fa-exclamation-triangle"></i> Error</h4>
                            <p>${data.error || 'Failed to scrape group'}</p>
                        </div>
                    `;
                }
            })
            .catch(error => {
                console.error('Error:', error);
                resultsContainer.innerHTML = '<div class="result-item result-invalid">Error scraping group</div>';
            });
        }
        
        // Show/hide message field based on task type
        document.getElementById('task-type').addEventListener('change', function() {
            const messageGroup = document.getElementById('message-group');
            if (this.value === 'message') {
                messageGroup.style.display = 'block';
            } else {
                messageGroup.style.display = 'none';
            }
        });
        
        // Load tasks on page load
        document.addEventListener('DOMContentLoaded', function() {
            loadTasks();
            
            // Auto-refresh tasks every 5 seconds
            setInterval(loadTasks, 5000);
        });
    </script>
</body>
</html>
'''

# Admin panel HTML
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
        
        .admin-content {
            padding: 40px;
        }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 25px;
            margin-bottom: 40px;
        }
        
        .stat-card {
            background: white;
            border-radius: 15px;
            padding: 25px;
            box-shadow: 0 10px 25px rgba(0, 0, 0, 0.1);
            text-align: center;
            transition: all 0.3s ease;
        }
        
        .stat-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 15px 35px rgba(0, 0, 0, 0.15);
        }
        
        .stat-icon {
            font-size: 3rem;
            margin-bottom: 15px;
            background: linear-gradient(135deg, #6c757d 0%, #495057 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        
        .stat-number {
            font-size: 2.5rem;
            font-weight: 800;
            color: #495057;
            margin-bottom: 10px;
        }
        
        .stat-label {
            font-size: 1rem;
            color: #6c757d;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            font-weight: 600;
        }
        
        .users-section {
            background: white;
            border-radius: 15px;
            padding: 30px;
            box-shadow: 0 10px 25px rgba(0, 0, 0, 0.1);
        }
        
        .section-title {
            font-size: 1.8rem;
            color: #495057;
            margin-bottom: 25px;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .users-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }
        
        .users-table th,
        .users-table td {
            padding: 15px;
            text-align: left;
            border-bottom: 1px solid #e9ecef;
        }
        
        .users-table th {
            background: #f8f9fa;
            font-weight: 700;
            color: #495057;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            font-size: 12px;
        }
        
        .users-table tr:hover {
            background: #f8f9fa;
        }
        
        .status-badge {
            padding: 6px 12px;
            border-radius: 20px;
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        .status-approved {
            background: linear-gradient(135deg, #d4edda 0%, #c3e6cb 100%);
            color: #155724;
        }
        
        .status-pending {
            background: linear-gradient(135deg, #fff3cd 0%, #ffeaa7 100%);
            color: #856404;
        }
        
        .status-admin {
            background: linear-gradient(135deg, #cce5ff 0%, #b3d9ff 100%);
            color: #004085;
        }
        
        .btn {
            padding: 8px 16px;
            border: none;
            border-radius: 8px;
            font-size: 12px;
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
            transform: translateY(-1px);
            box-shadow: 0 5px 15px rgba(40, 167, 69, 0.3);
        }
        
        .btn-revoke {
            background: linear-gradient(135deg, #dc3545 0%, #fd7e14 100%);
            color: white;
        }
        
        .btn-revoke:hover {
            transform: translateY(-1px);
            box-shadow: 0 5px 15px rgba(220, 53, 69, 0.3);
        }
        
        .btn-promote {
            background: linear-gradient(135deg, #007bff 0%, #6610f2 100%);
            color: white;
        }
        
        .btn-promote:hover {
            transform: translateY(-1px);
            box-shadow: 0 5px 15px rgba(0, 123, 255, 0.3);
        }
        
        .btn-demote {
            background: linear-gradient(135deg, #ffc107 0%, #fd7e14 100%);
            color: #212529;
        }
        
        .btn-demote:hover {
            transform: translateY(-1px);
            box-shadow: 0 5px 15px rgba(255, 193, 7, 0.3);
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
            .stats-grid {
                grid-template-columns: 1fr;
            }
            
            .users-table {
                font-size: 14px;
            }
            
            .users-table th,
            .users-table td {
                padding: 10px 8px;
            }
        }
    </style>
</head>
<body>
    <div class="admin-container">
        <div class="admin-header">
            <div class="user-info">
                <span class="user-email">{{ username }}</span>
                <a href="/logout" class="btn-logout">
                    <i class="fas fa-sign-out-alt"></i> Logout
                </a>
            </div>
            <h1><i class="fas fa-user-shield"></i> ADMIN PANEL</h1>
            <p>User Management & System Overview</p>
        </div>
        
        <div class="admin-content">
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-icon"><i class="fas fa-users"></i></div>
                    <div class="stat-number" id="total-users">{{ stats.total_users }}</div>
                    <div class="stat-label">Total Users</div>
                </div>
                
                <div class="stat-card">
                    <div class="stat-icon"><i class="fas fa-user-check"></i></div>
                    <div class="stat-number" id="approved-users">{{ stats.approved_users }}</div>
                    <div class="stat-label">Approved Users</div>
                </div>
                
                <div class="stat-card">
                    <div class="stat-icon"><i class="fas fa-user-clock"></i></div>
                    <div class="stat-number" id="pending-users">{{ stats.pending_users }}</div>
                    <div class="stat-label">Pending Approval</div>
                </div>
                
                <div class="stat-card">
                    <div class="stat-icon"><i class="fas fa-crown"></i></div>
                    <div class="stat-number" id="admin-users">{{ stats.admin_users }}</div>
                    <div class="stat-label">Administrators</div>
                </div>
            </div>
            
            <div class="users-section">
                <h2 class="section-title">
                    <i class="fas fa-users-cog"></i>
                    User Management
                </h2>
                
                <table class="users-table">
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Username</th>
                            <th>Status</th>
                            <th>Created</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody id="users-tbody">
                        {% for user in users %}
                        <tr>
                            <td>{{ user.id }}</td>
                            <td>{{ user.username }}</td>
                            <td>
                                {% if user.admin %}
                                    <span class="status-badge status-admin">Administrator</span>
                                {% elif user.approved %}
                                    <span class="status-badge status-approved">Approved</span>
                                {% else %}
                                    <span class="status-badge status-pending">Pending</span>
                                {% endif %}
                            </td>
                            <td>{{ user.created_at }}</td>
                            <td>
                                {% if not user.approved and not user.admin %}
                                    <button class="btn btn-approve" onclick="approveUser({{ user.id }})">
                                        <i class="fas fa-check"></i> Approve
                                    </button>
                                {% endif %}
                                
                                {% if user.approved and not user.admin %}
                                    <button class="btn btn-revoke" onclick="revokeUser({{ user.id }})">
                                        <i class="fas fa-times"></i> Revoke
                                    </button>
                                    <button class="btn btn-promote" onclick="promoteUser({{ user.id }})">
                                        <i class="fas fa-arrow-up"></i> Promote
                                    </button>
                                {% endif %}
                                
                                {% if user.admin and user.id != session.user_id %}
                                    <button class="btn btn-demote" onclick="demoteUser({{ user.id }})">
                                        <i class="fas fa-arrow-down"></i> Demote
                                    </button>
                                {% endif %}
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <script>
        function approveUser(userId) {
            if (confirm('Are you sure you want to approve this user?')) {
                fetch(`/admin/approve/${userId}`, {method: 'POST'})
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'success') {
                        location.reload();
                    } else {
                        alert('Error: ' + data.message);
                    }
                });
            }
        }
        
        function revokeUser(userId) {
            if (confirm('Are you sure you want to revoke this user\'s access?')) {
                fetch(`/admin/revoke/${userId}`, {method: 'POST'})
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'success') {
                        location.reload();
                    } else {
                        alert('Error: ' + data.message);
                    }
                });
            }
        }
        
        function promoteUser(userId) {
            if (confirm('Are you sure you want to promote this user to administrator?')) {
                fetch(`/admin/promote/${userId}`, {method: 'POST'})
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'success') {
                        location.reload();
                    } else {
                        alert('Error: ' + data.message);
                    }
                });
            }
        }
        
        function demoteUser(userId) {
            if (confirm('Are you sure you want to demote this administrator?')) {
                fetch(`/admin/demote/${userId}`, {method: 'POST'})
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'success') {
                        location.reload();
                    } else {
                        alert('Error: ' + data.message);
                    }
                });
            }
        }
    </script>
</body>
</html>
'''

# Routes
@app.route('/')
@login_required
@approved_required
def index():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT username FROM users WHERE id = ?", (session['user_id'],))
    user = c.fetchone()
    conn.close()
    
    return render_template_string(html_content, username=user[0] if user else 'Unknown')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        c.execute("SELECT id, admin, approved FROM users WHERE username = ? AND password = ?", 
                 (username, hashed_password))
        user = c.fetchone()
        conn.close()
        
        if user:
            session['user_id'] = user[0]
            session['is_admin'] = user[1]
            
            if user[1]:  # If admin
                return redirect(url_for('admin_panel'))
            elif user[2]:  # If approved
                return redirect(url_for('index'))
            else:  # If not approved
                return render_template_string(pending_approval_html)
        else:
            flash('Invalid username or password', 'error')
    
    return render_template_string(auth_html)

@app.route('/admin_login', methods=['POST'])
def admin_login():
    username = request.form['username']
    password = request.form['password']
    
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    c.execute("SELECT id FROM users WHERE username = ? AND password = ? AND admin = 1 AND approved = 1", 
             (username, hashed_password))
    user = c.fetchone()
    conn.close()
    
    if user:
        session['user_id'] = user[0]
        session['is_admin'] = True
        return redirect(url_for('admin_panel'))
    else:
        flash('Invalid admin credentials', 'admin_error')
        return redirect(url_for('login'))

@app.route('/register', methods=['POST'])
def register():
    username = request.form['username']
    password = request.form['password']
    confirm_password = request.form['confirm_password']
    
    if password != confirm_password:
        flash('Passwords do not match', 'error')
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    
    # Check if username already exists
    c.execute("SELECT id FROM users WHERE username = ?", (username,))
    if c.fetchone():
        flash('Username already exists', 'error')
        conn.close()
        return redirect(url_for('login'))
    
    # Create new user
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    try:
        c.execute("INSERT INTO users (username, password) VALUES (?, ?)", 
                 (username, hashed_password))
        conn.commit()
        flash('Account created successfully! Please wait for admin approval.', 'success')
    except:
        flash('Error creating account', 'error')
    
    conn.close()
    return redirect(url_for('login'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/admin')
@admin_required
def admin_panel():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    
    # Get current admin username
    c.execute("SELECT username FROM users WHERE id = ?", (session['user_id'],))
    admin_user = c.fetchone()
    
    # Get all users
    c.execute("SELECT id, username, admin, approved, created_at FROM users ORDER BY created_at DESC")
    users = c.fetchall()
    
    # Get statistics
    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM users WHERE approved = 1")
    approved_users = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM users WHERE approved = 0")
    pending_users = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM users WHERE admin = 1")
    admin_users = c.fetchone()[0]
    
    conn.close()
    
    stats = {
        'total_users': total_users,
        'approved_users': approved_users,
        'pending_users': pending_users,
        'admin_users': admin_users
    }
    
    users_list = []
    for user in users:
        users_list.append({
            'id': user[0],
            'username': user[1],
            'admin': user[2],
            'approved': user[3],
            'created_at': user[4]
        })
    
    return render_template_string(admin_html, 
                                username=admin_user[0] if admin_user else 'Admin',
                                users=users_list,
                                stats=stats)

@app.route('/admin/approve/<int:user_id>', methods=['POST'])
@admin_required
def approve_user(user_id):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("UPDATE users SET approved = 1 WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "success"})

@app.route('/admin/revoke/<int:user_id>', methods=['POST'])
@admin_required
def revoke_user(user_id):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("UPDATE users SET approved = 0 WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "success"})

@app.route('/admin/promote/<int:user_id>', methods=['POST'])
@admin_required
def promote_user(user_id):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("UPDATE users SET admin = 1, approved = 1 WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "success"})

@app.route('/admin/demote/<int:user_id>', methods=['POST'])
@admin_required
def demote_user(user_id):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("UPDATE users SET admin = 0 WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "success"})

# Task management functions
def log_message(task_id, message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if task_id not in task_logs:
        task_logs[task_id] = []
    task_logs[task_id].append({
        'timestamp': timestamp,
        'message': message
    })

def send_message_task(tokens, targets, message, delay, task_id):
    log_message(task_id, f"Starting message task with {len(tokens)} tokens and {len(targets)} targets")
    
    for i, token in enumerate(tokens):
        if stop_flags.get(task_id, False):
            log_message(task_id, "Task stopped by user")
            break
            
        log_message(task_id, f"Using token {i+1}/{len(tokens)}")
        
        for j, target in enumerate(targets):
            if stop_flags.get(task_id, False):
                log_message(task_id, "Task stopped by user")
                return
                
            try:
                url = f"https://api.telegram.org/bot{token}/sendMessage"
                data = {
                    'chat_id': target,
                    'text': message
                }
                
                response = requests.post(url, data=data, timeout=10)
                result = response.json()
                
                if result.get('ok'):
                    log_message(task_id, f"âœ“ Message sent to {target}")
                else:
                    error_msg = result.get('description', 'Unknown error')
                    log_message(task_id, f"âœ— Failed to send to {target}: {error_msg}")
                    
            except Exception as e:
                log_message(task_id, f"âœ— Error sending to {target}: {str(e)}")
            
            if j < len(targets) - 1:  # Don't delay after last target
                log_message(task_id, f"Waiting {delay} seconds...")
                time.sleep(delay)
    
    log_message(task_id, "Task completed")

def join_groups_task(tokens, targets, delay, task_id):
    log_message(task_id, f"Starting join groups task with {len(tokens)} tokens and {len(targets)} targets")
    
    for i, token in enumerate(tokens):
        if stop_flags.get(task_id, False):
            log_message(task_id, "Task stopped by user")
            break
            
        log_message(task_id, f"Using token {i+1}/{len(tokens)}")
        
        for j, target in enumerate(targets):
            if stop_flags.get(task_id, False):
                log_message(task_id, "Task stopped by user")
                return
                
            try:
                # Try to join the group/channel
                url = f"https://api.telegram.org/bot{token}/joinChat"
                data = {'chat_id': target}
                
                response = requests.post(url, data=data, timeout=10)
                result = response.json()
                
                if result.get('ok'):
                    log_message(task_id, f"âœ“ Joined {target}")
                else:
                    error_msg = result.get('description', 'Unknown error')
                    log_message(task_id, f"âœ— Failed to join {target}: {error_msg}")
                    
            except Exception as e:
                log_message(task_id, f"âœ— Error joining {target}: {str(e)}")
            
            if j < len(targets) - 1:  # Don't delay after last target
                log_message(task_id, f"Waiting {delay} seconds...")
                time.sleep(delay)
    
    log_message(task_id, "Task completed")

def leave_groups_task(tokens, targets, delay, task_id):
    log_message(task_id, f"Starting leave groups task with {len(tokens)} tokens and {len(targets)} targets")
    
    for i, token in enumerate(tokens):
        if stop_flags.get(task_id, False):
            log_message(task_id, "Task stopped by user")
            break
            
        log_message(task_id, f"Using token {i+1}/{len(tokens)}")
        
        for j, target in enumerate(targets):
            if stop_flags.get(task_id, False):
                log_message(task_id, "Task stopped by user")
                return
                
            try:
                # Try to leave the group/channel
                url = f"https://api.telegram.org/bot{token}/leaveChat"
                data = {'chat_id': target}
                
                response = requests.post(url, data=data, timeout=10)
                result = response.json()
                
                if result.get('ok'):
                    log_message(task_id, f"âœ“ Left {target}")
                else:
                    error_msg = result.get('description', 'Unknown error')
                    log_message(task_id, f"âœ— Failed to leave {target}: {error_msg}")
                    
            except Exception as e:
                log_message(task_id, f"âœ— Error leaving {target}: {str(e)}")
            
            if j < len(targets) - 1:  # Don't delay after last target
                log_message(task_id, f"Waiting {delay} seconds...")
                time.sleep(delay)
    
    log_message(task_id, "Task completed")

def react_task(tokens, targets, delay, task_id):
    log_message(task_id, f"Starting reaction task with {len(tokens)} tokens and {len(targets)} targets")
    
    reactions = ['ðŸ‘', 'â¤ï¸', 'ðŸ”¥', 'ðŸ‘', 'ðŸ˜', 'ðŸŽ‰', 'ðŸ¤©', 'ðŸ‘Œ']
    
    for i, token in enumerate(tokens):
        if stop_flags.get(task_id, False):
            log_message(task_id, "Task stopped by user")
            break
            
        log_message(task_id, f"Using token {i+1}/{len(tokens)}")
        
        for j, target in enumerate(targets):
            if stop_flags.get(task_id, False):
                log_message(task_id, "Task stopped by user")
                return
                
            try:
                # Get recent messages from the chat
                url = f"https://api.telegram.org/bot{token}/getUpdates"
                response = requests.get(url, timeout=10)
                result = response.json()
                
                if result.get('ok') and result.get('result'):
                    # Find messages from the target chat
                    messages = [update for update in result['result'] 
                              if update.get('message', {}).get('chat', {}).get('id') == int(target)]
                    
                    if messages:
                        # React to the latest message
                        latest_message = messages[-1]['message']
                        message_id = latest_message['message_id']
                        
                        reaction_url = f"https://api.telegram.org/bot{token}/setMessageReaction"
                        reaction_data = {
                            'chat_id': target,
                            'message_id': message_id,
                            'reaction': json.dumps([{'type': 'emoji', 'emoji': reactions[j % len(reactions)]}])
                        }
                        
                        reaction_response = requests.post(reaction_url, data=reaction_data, timeout=10)
                        reaction_result = reaction_response.json()
                        
                        if reaction_result.get('ok'):
                            log_message(task_id, f"âœ“ Added reaction to message in {target}")
                        else:
                            error_msg = reaction_result.get('description', 'Unknown error')
                            log_message(task_id, f"âœ— Failed to react in {target}: {error_msg}")
                    else:
                        log_message(task_id, f"âœ— No messages found in {target}")
                else:
                    log_message(task_id, f"âœ— Failed to get updates for {target}")
                    
            except Exception as e:
                log_message(task_id, f"âœ— Error reacting in {target}: {str(e)}")
            
            if j < len(targets) - 1:  # Don't delay after last target
                log_message(task_id, f"Waiting {delay} seconds...")
                time.sleep(delay)
    
    log_message(task_id, "Task completed")

@app.route('/start_task', methods=['POST'])
@login_required
@approved_required
def start_task():
    try:
        data = request.get_json()
        task_type = data.get('type')
        tokens = data.get('tokens', [])
        targets = data.get('targets', [])
        message = data.get('message', '')
        delay = data.get('delay', 5)
        
        # Generate unique task ID
        task_id = str(uuid.uuid4())
        
        # Initialize stop flag
        stop_flags[task_id] = False
        
        # Start appropriate task based on type
        if task_type == 'message':
            thread = threading.Thread(target=send_message_task, 
                                    args=(tokens, targets, message, delay, task_id))
        elif task_type == 'join':
            thread = threading.Thread(target=join_groups_task, 
                                    args=(tokens, targets, delay, task_id))
        elif task_type == 'leave':
            thread = threading.Thread(target=leave_groups_task, 
                                    args=(tokens, targets, delay, task_id))
        elif task_type == 'react':
            thread = threading.Thread(target=react_task, 
                                    args=(tokens, targets, delay, task_id))
        else:
            return jsonify({"status": "error", "message": "Invalid task type"})
        
        # Store thread info
        message_threads[task_id] = {
            'thread': thread,
            'type': task_type,
            'tokens': len(tokens),
            'targets': len(targets),
            'delay': delay,
            'status': 'running',
            'user_id': session['user_id']  # Associate task with user
        }
        
        thread.start()
        
        return jsonify({"status": "success", "task_id": task_id})
        
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/stop_task/<task_id>', methods=['POST'])
@login_required
@approved_required
def stop_task(task_id):
    try:
        # Check if task belongs to current user
        if task_id in message_threads and message_threads[task_id]['user_id'] == session['user_id']:
            stop_flags[task_id] = True
            message_threads[task_id]['status'] = 'stopped'
            log_message(task_id, "Task stopped by user")
            return jsonify({"status": "success"})
        else:
            return jsonify({"status": "error", "message": "Task not found or unauthorized"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/stop_all_tasks', methods=['POST'])
@login_required
@approved_required
def stop_all_tasks():
    try:
        user_id = session['user_id']
        stopped_count = 0
        
        for task_id, task_info in message_threads.items():
            if task_info['user_id'] == user_id and task_info['status'] == 'running':
                stop_flags[task_id] = True
                task_info['status'] = 'stopped'
                log_message(task_id, "Task stopped by user (stop all)")
                stopped_count += 1
        
        return jsonify({"status": "success", "stopped": stopped_count})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/get_tasks')
@login_required
@approved_required
def get_tasks():
    try:
        user_id = session['user_id']
        user_tasks = []
        
        for task_id, task_info in message_threads.items():
            if task_info['user_id'] == user_id:  # Only show user's own tasks
                user_tasks.append({
                    'id': task_id,
                    'type': task_info['type'],
                    'tokens': task_info['tokens'],
                    'targets': task_info['targets'],
                    'delay': task_info['delay'],
                    'status': task_info['status']
                })
        
        return jsonify({"tasks": user_tasks})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/get_logs/<task_id>')
@login_required
@approved_required
def get_logs(task_id):
    try:
        # Check if task belongs to current user
        if task_id in message_threads and message_threads[task_id]['user_id'] == session['user_id']:
            logs = task_logs.get(task_id, [])
            return jsonify({"logs": logs})
        else:
            return jsonify({"status": "error", "message": "Task not found or unauthorized"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/check_tokens', methods=['POST'])
@login_required
@approved_required
def check_tokens():
    try:
        data = request.get_json()
        tokens = data.get('tokens', [])
        results = []
        
        for token in tokens:
            try:
                url = f"https://api.telegram.org/bot{token}/getMe"
                response = requests.get(url, timeout=10)
                result = response.json()
                
                if result.get('ok'):
                    bot_info = result['result']
                    results.append({
                        'token': token,
                        'valid': True,
                        'info': bot_info
                    })
                else:
                    results.append({
                        'token': token,
                        'valid': False,
                        'error': result.get('description', 'Unknown error')
                    })
            except Exception as e:
                results.append({
                    'token': token,
                    'valid': False,
                    'error': str(e)
                })
        
        return jsonify({"results": results})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/scrape_group', methods=['POST'])
@login_required
@approved_required
def scrape_group():
    try:
        data = request.get_json()
        token = data.get('token')
        group = data.get('group')
        
        # Get chat administrators (this works for most bots)
        url = f"https://api.telegram.org/bot{token}/getChatAdministrators"
        data_payload = {'chat_id': group}
        
        response = requests.post(url, data=data_payload, timeout=10)
        result = response.json()
        
        if result.get('ok'):
            admins = result['result']
            members = []
            
            for admin in admins:
                user = admin['user']
                members.append({
                    'id': user['id'],
                    'first_name': user.get('first_name', ''),
                    'last_name': user.get('last_name', ''),
                    'username': user.get('username', ''),
                    'is_bot': user.get('is_bot', False)
                })
            
            return jsonify({"members": members})
        else:
            error_msg = result.get('description', 'Unknown error')
            return jsonify({"error": error_msg})
            
    except Exception as e:
        return jsonify({"error": str(e)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
