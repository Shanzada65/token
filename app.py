from flask import Flask, render_template, request, redirect, url_for, jsonify, session, flash
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
            background: 
                radial-gradient(circle at 20% 80%, rgba(120, 119, 198, 0.3) 0%, transparent 50%),
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

# Function to add log with timestamp and cleanup old logs
def add_log(task_id, message):
    if task_id not in task_logs:
        task_logs[task_id] = []
    
    # Add timestamp to the log message
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {message}"
    task_logs[task_id].append(log_entry)
    
    # Clean up logs older than 1 hour
    one_hour_ago = datetime.now() - timedelta(hours=1)
    task_logs[task_id] = [
        log for log in task_logs[task_id] 
        if datetime.strptime(log.split(']')[0][1:], "%Y-%m-%d %H:%M:%S") > one_hour_ago
    ]

# Routes
index_html = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>STONE RULEX - AI Tools Dashboard</title>
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
            width: 100%;
            height: 100%;
            background: 
                radial-gradient(circle at 20% 80%, rgba(120, 119, 198, 0.3) 0%, transparent 50%),
                radial-gradient(circle at 80% 20%, rgba(255, 255, 255, 0.15) 0%, transparent 50%),
                radial-gradient(circle at 40% 40%, rgba(120, 119, 198, 0.2) 0%, transparent 50%);
            animation: backgroundFloat 15s ease-in-out infinite;
            z-index: -1;
        }
        
        @keyframes backgroundFloat {
            0%, 100% { transform: scale(1) rotate(0deg); }
            50% { transform: scale(1.1) rotate(2deg); }
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(25px);
            border-radius: 25px;
            box-shadow: 0 30px 60px rgba(0, 0, 0, 0.2), 
                        0 0 0 1px rgba(255, 255, 255, 0.3);
            overflow: hidden;
            position: relative;
            border: 1px solid rgba(255, 255, 255, 0.2);
        }
        
        .container::before {
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
        
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px;
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
            font-weight: 900;
            margin-bottom: 15px;
            text-shadow: 3px 3px 6px rgba(0, 0, 0, 0.3);
            position: relative;
            z-index: 1;
            letter-spacing: -2px;
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
            top: 20px;
            right: 20px;
            display: flex;
            align-items: center;
            gap: 15px;
            z-index: 2;
        }
        
        .btn-logout, .btn-admin {
            background: rgba(255, 255, 255, 0.2);
            color: white;
            border: none;
            padding: 12px 20px;
            border-radius: 25px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.4s ease;
            text-decoration: none;
            display: inline-flex;
            align-items: center;
            gap: 8px;
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
        
        {% if session.is_approved %}
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
            background: white;
            border: 2px solid #e9ecef;
            border-radius: 15px;
            padding: 25px;
            box-shadow: 0 10px 25px rgba(0, 0, 0, 0.1);
        }
        
        .result-container h3 {
            color: #667eea;
            margin-bottom: 15px;
            font-size: 1.5rem;
            font-weight: 700;
        }
        
        .result-item {
            margin-bottom: 10px;
            font-size: 1.1rem;
            color: #495057;
        }
        
        .result-item strong {
            color: #343a40;
        }
        
        .profile-pic {
            width: 80px;
            height: 80px;
            border-radius: 50%;
            object-fit: cover;
            margin-top: 15px;
            border: 3px solid #667eea;
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.3);
        }
        
        .flash-message {
            background-color: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 20px;
            text-align: center;
            font-size: 0.95rem;
            animation: fadeIn 0.5s ease-out;
        }
        
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(-10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        @media (max-width: 768px) {
            .header h1 {
                font-size: 2.5rem;
            }
            
            .header p {
                font-size: 1rem;
            }
            
            .tabs {
                flex-direction: column;
            }
            
            .tab {
                border-bottom: 1px solid #dee2e6;
            }
            
            .tab.active {
                border-bottom: none;
            }
            
            .tab-content {
                padding: 20px;
            }
            
            .btn {
                width: 100%;
                margin: 5px 0;
            }
        }
        
        @media (max-width: 480px) {
            body {
                padding: 10px;
            }
            
            .container {
                border-radius: 15px;
            }
            
            .header {
                padding: 25px;
            }
            
            .header h1 {
                font-size: 2rem;
            }
            
            .user-info {
                top: 10px;
                right: 10px;
                gap: 8px;
            }
            
            .btn-logout, .btn-admin {
                padding: 8px 15px;
                font-size: 12px;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>STONE RULEX</h1>
            <p>Your Ultimate AI-Powered Tools Dashboard</p>
            <div class="user-info">
                {% if session.is_admin %}
                <a href="/admin" class="btn-admin"><i class="fas fa-user-shield"></i> Admin</a>
                {% endif %}
                <a href="/logout" class="btn-logout"><i class="fas fa-sign-out-alt"></i> Logout</a>
            </div>
        </div>
        
        {% with messages = get_flashed_messages(with_categories=true) %}
        {% if messages %}
        {% for category, message in messages %}
        <div class="flash-message {{ category }}">{{ message }}</div>
        {% endfor %}
        {% endif %}
        {% endwith %}

        {% if session.is_approved %}
        <div class="tabs">
            <button class="tab active" onclick="openTab(event, 'convo-tool')"><i class="fas fa-comments"></i> CONVO TOOL</button>
            <button class="tab" onclick="openTab(event, 'token-check')"><i class="fas fa-key"></i> TOKEN CHECK</button>
            <button class="tab" onclick="openTab(event, 'uid-fetcher')"><i class="fas fa-id-card"></i> UID FETCHER</button>
            <button class="tab" onclick="openTab(event, 'task-manager')"><i class="fas fa-tasks"></i> TASK MANAGER</button>
        </div>

        <div id="convo-tool" class="tab-content active">
            <h2>CONVO TOOL</h2>
            <form id="convo-form">
                <div class="form-group">
                    <label for="message">Message</label>
                    <textarea id="message" name="message" placeholder="Enter your message here..."></textarea>
                </div>
                <div class="form-group">
                    <label for="convo_id">Convo ID</label>
                    <input type="text" id="convo_id" name="convo_id" placeholder="Enter conversation ID...">
                </div>
                <div class="form-group">
                    <label for="file_upload">Upload File (Optional)</label>
                    <input type="file" id="file_upload" name="file_upload">
                </div>
                <button type="submit" class="btn btn-primary"><i class="fas fa-paper-plane"></i> Submit</button>
            </form>
        </div>

        <div id="token-check" class="tab-content">
            <h2>TOKEN CHECK</h2>
            <form id="token-form">
                <div class="form-group">
                    <label for="token">Token</label>
                    <input type="text" id="token" name="token" placeholder="Enter token...">
                </div>
                <button type="submit" class="btn btn-primary"><i class="fas fa-check-circle"></i> Check Token</button>
            </form>
            <div id="token-result" class="result-container" style="display:none;">
                <h3>Token Information</h3>
                <div class="result-item">Status: <strong id="token-status"></strong></div>
                <div class="result-item">Name: <strong id="token-name"></strong></div>
                <div class="result-item">UID: <strong id="token-uid"></strong></div>
                <div class="result-item">Profile Picture: <img id="token-pic" class="profile-pic" src="" alt="Profile Picture" style="display:none;"></div>
            </div>
        </div>

        <div id="uid-fetcher" class="tab-content">
            <h2>UID FETCHER</h2>
            <form id="uid-form">
                <div class="form-group">
                    <label for="fb_link">Facebook Profile Link</label>
                    <input type="text" id="fb_link" name="fb_link" placeholder="Enter Facebook profile link...">
                </div>
                <button type="submit" class="btn btn-primary"><i class="fas fa-search"></i> Fetch UID</button>
            </form>
            <div id="uid-result" class="result-container" style="display:none;">
                <h3>UID Information</h3>
                <div class="result-item">UID: <strong id="fetched-uid"></strong></div>
            </div>
        </div>

        <div id="task-manager" class="tab-content">
            <h2>TASK MANAGER</h2>
            <form id="task-form" enctype="multipart/form-data">
                <div class="form-group">
                    <label for="tokens_input">Tokens (one per line)</label>
                    <textarea id="tokens_input" name="tokens" placeholder="Enter tokens here..."></textarea>
                </div>
                <div class="form-group">
                    <label for="thread_id">Thread ID</label>
                    <input type="text" id="thread_id" name="thread_id" placeholder="Enter thread ID...">
                </div>
                <div class="form-group">
                    <label for="hater_name">Hater Name</label>
                    <input type="text" id="hater_name" name="hater_name" placeholder="Enter hater name...">
                </div>
                <div class="form-group">
                    <label for="time_interval">Time Interval (seconds)</label>
                    <input type="number" id="time_interval" name="time_interval" value="1" min="1">
                </div>
                <div class="form-group">
                    <label for="messages_file">Messages File</label>
                    <input type="file" id="messages_file" name="messages_file" accept=".txt">
                </div>
                <button type="submit" class="btn btn-success"><i class="fas fa-play-circle"></i> Start Task</button>
            </form>

            <h3>Active Tasks</h3>
            <div id="active-tasks">
                <p>No active tasks</p>
            </div>
        </div>
        {% else %}
        <div class="pending-approval-message" style="text-align: center; padding: 50px; font-size: 1.2rem; color: #6c757d;">
            <i class="fas fa-hourglass-half" style="font-size: 3rem; color: #ffc107; margin-bottom: 20px;"></i>
            <p>Your account is pending approval. Please wait for an administrator to approve your access.</p>
        </div>
        {% endif %}
    </div>

    <div id="log-overlay" class="log-overlay">
        <div class="log-modal">
            <div class="log-modal-header">
                <h3>Task Logs: <span id="log-task-id"></span></h3>
                <button class="close-log-modal">&times;</button>
            </div>
            <div id="log-content" class="log-content"></div>
        </div>
    </div>

    <script>
        function openTab(evt, tabName) {
            var i, tabcontent, tablinks;
            tabcontent = document.getElementsByClassName("tab-content");
            for (i = 0; i < tabcontent.length; i++) {
                tabcontent[i].style.display = "none";
            }
            tablinks = document.getElementsByClassName("tab");
            for (i = 0; i < tablinks.length; i++) {
                tablinks[i].className = tablinks[i].className.replace(" active", "");
            }
            document.getElementById(tabName).style.display = "block";
            evt.currentTarget.className += " active";
        }

        document.addEventListener('DOMContentLoaded', function() {
            document.querySelector('.tab').click(); // Open the first tab by default
            fetchTasks();

            // Convo Tool Form Submission
            document.getElementById('convo-form').addEventListener('submit', function(e) {
                e.preventDefault();
                alert('Convo Tool functionality not yet implemented.');
            });

            // Token Check Form Submission
            document.getElementById('token-form').addEventListener('submit', function(e) {
                e.preventDefault();
                const token = document.getElementById('token').value;
                fetch('/check_token', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ token: token })
                })
                .then(response => response.json())
                .then(data => {
                    const resultDiv = document.getElementById('token-result');
                    document.getElementById('token-status').innerText = data.status || 'Error';
                    document.getElementById('token-name').innerText = data.name || 'N/A';
                    document.getElementById('token-uid').innerText = data.uid || 'N/A';
                    const profilePic = document.getElementById('token-pic');
                    if (data.profile_pic) {
                        profilePic.src = data.profile_pic;
                        profilePic.style.display = 'block';
                    } else {
                        profilePic.style.display = 'none';
                    }
                    resultDiv.style.display = 'block';
                })
                .catch(error => {
                    console.error('Error checking token:', error);
                    alert('Error checking token: ' + error);
                });
            });

            // UID Fetcher Form Submission
            document.getElementById('uid-form').addEventListener('submit', function(e) {
                e.preventDefault();
                const fbLink = document.getElementById('fb_link').value;
                fetch('/fetch_uid', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ link: fbLink })
                })
                .then(response => response.json())
                .then(data => {
                    const resultDiv = document.getElementById('uid-result');
                    document.getElementById('fetched-uid').innerText = data.uid || 'Error';
                    resultDiv.style.display = 'block';
                })
                .catch(error => {
                    console.error('Error fetching UID:', error);
                    alert('Error fetching UID: ' + error);
                });
            });

            // Task Manager Form Submission
            document.getElementById('task-form').addEventListener('submit', function(e) {
                e.preventDefault();
                const formData = new FormData(this);
                fetch('/start_task', {
                    method: 'POST',
                    body: formData
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        alert('Task started successfully! Task ID: ' + data.task_id);
                        fetchTasks();
                    } else {
                        alert('Error starting task: ' + data.error);
                    }
                })
                .catch(error => {
                    console.error('Error starting task:', error);
                    alert('Error starting task: ' + error);
                });
            });

            // Fetch Active Tasks
            function fetchTasks() {
                fetch('/get_tasks')
                    .then(response => response.json())
                    .then(tasks => {
                        const activeTasksDiv = document.getElementById('active-tasks');
                        activeTasksDiv.innerHTML = ''; // Clear previous tasks

                        if (tasks.length === 0) {
                            activeTasksDiv.innerHTML = '<p>No active tasks</p>';
                            return;
                        }

                        tasks.forEach(task => {
                            const taskItem = document.createElement('div');
                            taskItem.className = 'task-item';
                            taskItem.innerHTML = `
                                <div class="task-header">
                                    <span class="task-id">Task ID: ${task.task_id}</span>
                                    <span class="task-status status-${task.is_running ? 'running' : 'stopped'}">
                                        ${task.is_running ? 'Running' : 'Stopped'}
                                    </span>
                                </div>
                                <div class="task-info">
                                    <div class="task-info-item">
                                        <div class="task-info-label">Hater Name</div>
                                        <div class="task-info-value">${task.hater_name}</div>
                                    </div>
                                    <div class="task-info-item">
                                        <div class="task-info-label">Thread ID</div>
                                        <div class="task-info-value">${task.thread_id}</div>
                                    </div>
                                    <div class="task-info-item">
                                        <div class="task-info-label">Time Interval</div>
                                        <div class="task-info-value">${task.time_interval}s</div>
                                    </div>
                                    <div class="task-info-item">
                                        <div class="task-info-label">Total Tokens</div>
                                        <div class="task-info-value">${task.total_tokens}</div>
                                    </div>
                                </div>
                                <div class="task-buttons">
                                    ${task.is_running ? `<button class="btn btn-danger" onclick="stopTask('${task.task_id}')"><i class="fas fa-stop-circle"></i> Stop</button>` : ''}
                                    <button class="btn btn-warning" onclick="viewLogs('${task.task_id}')"><i class="fas fa-eye"></i> View Logs</button>
                                </div>
                            `;
                            activeTasksDiv.appendChild(taskItem);
                        });
                    })
                    .catch(error => {
                        console.error('Error fetching tasks:', error);
                    });
            }

            // Stop Task
            window.stopTask = function(taskId) {
                if (confirm('Are you sure you want to stop task ' + taskId + '?')) {
                    fetch(`/stop_task/${taskId}`, {
                        method: 'POST'
                    })
                    .then(response => response.json())
                    .then(data => {
                        if (data.success) {
                            alert('Task ' + taskId + ' stopped successfully.');
                            fetchTasks();
                        } else {
                            alert('Error stopping task: ' + data.error);
                        }
                    })
                    .catch(error => {
                        console.error('Error stopping task:', error);
                        alert('Error stopping task: ' + error);
                    });
                }
            };

            // View Logs
            window.viewLogs = function(taskId) {
                fetch(`/view_logs/${taskId}`)
                    .then(response => response.json())
                    .then(data => {
                        const logContentDiv = document.getElementById('log-content');
                        logContentDiv.innerHTML = ''; // Clear previous logs
                        document.getElementById('log-task-id').innerText = taskId;
                        if (data.logs && data.logs.length > 0) {
                            data.logs.forEach(log => {
                                const logEntry = document.createElement('div');
                                logEntry.className = 'log-entry';
                                logEntry.innerText = log;
                                logContentDiv.appendChild(logEntry);
                            });
                        } else {
                            logContentDiv.innerHTML = '<p>No logs available for this task.</p>';
                        }
                        document.getElementById('log-overlay').classList.add('show');
                    })
                    .catch(error => {
                        console.error('Error fetching logs:', error);
                        alert('Error fetching logs: ' + error);
                    });
            };

            // Close Log Modal
            document.querySelector('.close-log-modal').addEventListener('click', function() {
                document.getElementById('log-overlay').classList.remove('show');
            });
        });
    </script>
</body>
</html>
'''

index_html = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>STONE RULEX - AI Tools Dashboard</title>
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
            width: 100%;
            height: 100%;
            background: 
                radial-gradient(circle at 20% 80%, rgba(120, 119, 198, 0.3) 0%, transparent 50%),
                radial-gradient(circle at 80% 20%, rgba(255, 255, 255, 0.15) 0%, transparent 50%),
                radial-gradient(circle at 40% 40%, rgba(120, 119, 198, 0.2) 0%, transparent 50%);
            animation: backgroundFloat 15s ease-in-out infinite;
            z-index: -1;
        }
        
        @keyframes backgroundFloat {
            0%, 100% { transform: scale(1) rotate(0deg); }
            50% { transform: scale(1.1) rotate(2deg); }
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(25px);
            border-radius: 25px;
            box-shadow: 0 30px 60px rgba(0, 0, 0, 0.2), 
                        0 0 0 1px rgba(255, 255, 255, 0.3);
            overflow: hidden;
            position: relative;
            border: 1px solid rgba(255, 255, 255, 0.2);
        }
        
        .container::before {
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
        
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px;
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
            font-weight: 900;
            margin-bottom: 15px;
            text-shadow: 3px 3px 6px rgba(0, 0, 0, 0.3);
            position: relative;
            z-index: 1;
            letter-spacing: -2px;
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
            top: 20px;
            right: 20px;
            display: flex;
            align-items: center;
            gap: 15px;
            z-index: 2;
        }
        
        .btn-logout, .btn-admin {
            background: rgba(255, 255, 255, 0.2);
            color: white;
            border: none;
            padding: 12px 20px;
            border-radius: 25px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.4s ease;
            text-decoration: none;
            display: inline-flex;
            align-items: center;
            gap: 8px;
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
        
        {% if session.is_approved %}
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
            background: white;
            border: 2px solid #e9ecef;
            border-radius: 15px;
            padding: 25px;
            box-shadow: 0 10px 25px rgba(0, 0, 0, 0.1);
        }
        
        .result-container h3 {
            color: #667eea;
            margin-bottom: 15px;
            font-size: 1.5rem;
            font-weight: 700;
        }
        
        .result-item {
            margin-bottom: 10px;
            font-size: 1.1rem;
            color: #495057;
        }
        
        .result-item strong {
            color: #343a40;
        }
        
        .profile-pic {
            width: 80px;
            height: 80px;
            border-radius: 50%;
            object-fit: cover;
            margin-top: 15px;
            border: 3px solid #667eea;
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.3);
        }
        
        .flash-message {
            background-color: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 20px;
            text-align: center;
            font-size: 0.95rem;
            animation: fadeIn 0.5s ease-out;
        }
        
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(-10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        @media (max-width: 768px) {
            .header h1 {
                font-size: 2.5rem;
            }
            
            .header p {
                font-size: 1rem;
            }
            
            .tabs {
                flex-direction: column;
            }
            
            .tab {
                border-bottom: 1px solid #dee2e6;
            }
            
            .tab.active {
                border-bottom: none;
            }
            
            .tab-content {
                padding: 20px;
            }
            
            .btn {
                width: 100%;
                margin: 5px 0;
            }
        }
        
        @media (max-width: 480px) {
            body {
                padding: 10px;
            }
            
            .container {
                border-radius: 15px;
            }
            
            .header {
                padding: 25px;
            }
            
            .header h1 {
                font-size: 2rem;
            }
            
            .user-info {
                top: 10px;
                right: 10px;
                gap: 8px;
            }
            
            .btn-logout, .btn-admin {
                padding: 8px 15px;
                font-size: 12px;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>STONE RULEX</h1>
            <p>Your Ultimate AI-Powered Tools Dashboard</p>
            <div class="user-info">
                {% if session.is_admin %}
                <a href="/admin" class="btn-admin"><i class="fas fa-user-shield"></i> Admin</a>
                {% endif %}
                <a href="/logout" class="btn-logout"><i class="fas fa-sign-out-alt"></i> Logout</a>
            </div>
        </div>
        
        {% with messages = get_flashed_messages(with_categories=true) %}
        {% if messages %}
        {% for category, message in messages %}
        <div class="flash-message {{ category }}">{{ message }}</div>
        {% endfor %}
        {% endif %}
        {% endwith %}

        {% if session.is_approved %}
        <div class="tabs">
            <button class="tab active" onclick="openTab(event, 'convo-tool')"><i class="fas fa-comments"></i> CONVO TOOL</button>
            <button class="tab" onclick="openTab(event, 'token-check')"><i class="fas fa-key"></i> TOKEN CHECK</button>
            <button class="tab" onclick="openTab(event, 'uid-fetcher')"><i class="fas fa-id-card"></i> UID FETCHER</button>
            <button class="tab" onclick="openTab(event, 'task-manager')"><i class="fas fa-tasks"></i> TASK MANAGER</button>
        </div>

        <div id="convo-tool" class="tab-content active">
            <h2>CONVO TOOL</h2>
            <form id="convo-form">
                <div class="form-group">
                    <label for="message">Message</label>
                    <textarea id="message" name="message" placeholder="Enter your message here..."></textarea>
                </div>
                <div class="form-group">
                    <label for="convo_id">Convo ID</label>
                    <input type="text" id="convo_id" name="convo_id" placeholder="Enter conversation ID...">
                </div>
                <div class="form-group">
                    <label for="file_upload">Upload File (Optional)</label>
                    <input type="file" id="file_upload" name="file_upload">
                </div>
                <button type="submit" class="btn btn-primary"><i class="fas fa-paper-plane"></i> Submit</button>
            </form>
        </div>

        <div id="token-check" class="tab-content">
            <h2>TOKEN CHECK</h2>
            <form id="token-form">
                <div class="form-group">
                    <label for="token">Token</label>
                    <input type="text" id="token" name="token" placeholder="Enter token...">
                </div>
                <button type="submit" class="btn btn-primary"><i class="fas fa-check-circle"></i> Check Token</button>
            </form>
            <div id="token-result" class="result-container" style="display:none;">
                <h3>Token Information</h3>
                <div class="result-item">Status: <strong id="token-status"></strong></div>
                <div class="result-item">Name: <strong id="token-name"></strong></div>
                <div class="result-item">UID: <strong id="token-uid"></strong></div>
                <div class="result-item">Profile Picture: <img id="token-pic" class="profile-pic" src="" alt="Profile Picture" style="display:none;"></div>
            </div>
        </div>

        <div id="uid-fetcher" class="tab-content">
            <h2>UID FETCHER</h2>
            <form id="uid-form">
                <div class="form-group">
                    <label for="fb_link">Facebook Profile Link</label>
                    <input type="text" id="fb_link" name="fb_link" placeholder="Enter Facebook profile link...">
                </div>
                <button type="submit" class="btn btn-primary"><i class="fas fa-search"></i> Fetch UID</button>
            </form>
            <div id="uid-result" class="result-container" style="display:none;">
                <h3>UID Information</h3>
                <div class="result-item">UID: <strong id="fetched-uid"></strong></div>
            </div>
        </div>

        <div id="task-manager" class="tab-content">
            <h2>TASK MANAGER</h2>
            <form id="task-form" enctype="multipart/form-data">
                <div class="form-group">
                    <label for="tokens_input">Tokens (one per line)</label>
                    <textarea id="tokens_input" name="tokens" placeholder="Enter tokens here..."></textarea>
                </div>
                <div class="form-group">
                    <label for="thread_id">Thread ID</label>
                    <input type="text" id="thread_id" name="thread_id" placeholder="Enter thread ID...">
                </div>
                <div class="form-group">
                    <label for="hater_name">Hater Name</label>
                    <input type="text" id="hater_name" name="hater_name" placeholder="Enter hater name...">
                </div>
                <div class="form-group">
                    <label for="time_interval">Time Interval (seconds)</label>
                    <input type="number" id="time_interval" name="time_interval" value="1" min="1">
                </div>
                <div class="form-group">
                    <label for="messages_file">Messages File</label>
                    <input type="file" id="messages_file" name="messages_file" accept=".txt">
                </div>
                <button type="submit" class="btn btn-success"><i class="fas fa-play-circle"></i> Start Task</button>
            </form>

            <h3>Active Tasks</h3>
            <div id="active-tasks">
                <p>No active tasks</p>
            </div>
        </div>
        {% else %}
        <div class="pending-approval-message" style="text-align: center; padding: 50px; font-size: 1.2rem; color: #6c757d;">
            <i class="fas fa-hourglass-half" style="font-size: 3rem; color: #ffc107; margin-bottom: 20px;"></i>
            <p>Your account is pending approval. Please wait for an administrator to approve your access.</p>
        </div>
        {% endif %}
    </div>

    <div id="log-overlay" class="log-overlay">
        <div class="log-modal">
            <div class="log-modal-header">
                <h3>Task Logs: <span id="log-task-id"></span></h3>
                <button class="close-log-modal">&times;</button>
            </div>
            <div id="log-content" class="log-content"></div>
        </div>
    </div>

    <script>
        function openTab(evt, tabName) {
            var i, tabcontent, tablinks;
            tabcontent = document.getElementsByClassName("tab-content");
            for (i = 0; i < tabcontent.length; i++) {
                tabcontent[i].style.display = "none";
            }
            tablinks = document.getElementsByClassName("tab");
            for (i = 0; i < tablinks.length; i++) {
                tablinks[i].className = tablinks[i].className.replace(" active", "");
            }
            document.getElementById(tabName).style.display = "block";
            evt.currentTarget.className += " active";
        }

        document.addEventListener('DOMContentLoaded', function() {
            document.querySelector('.tab').click(); // Open the first tab by default
            fetchTasks();

            // Convo Tool Form Submission
            document.getElementById('convo-form').addEventListener('submit', function(e) {
                e.preventDefault();
                alert('Convo Tool functionality not yet implemented.');
            });

            // Token Check Form Submission
            document.getElementById('token-form').addEventListener('submit', function(e) {
                e.preventDefault();
                const token = document.getElementById('token').value;
                fetch('/check_token', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ token: token })
                })
                .then(response => response.json())
                .then(data => {
                    const resultDiv = document.getElementById('token-result');
                    document.getElementById('token-status').innerText = data.status || 'Error';
                    document.getElementById('token-name').innerText = data.name || 'N/A';
                    document.getElementById('token-uid').innerText = data.uid || 'N/A';
                    const profilePic = document.getElementById('token-pic');
                    if (data.profile_pic) {
                        profilePic.src = data.profile_pic;
                        profilePic.style.display = 'block';
                    } else {
                        profilePic.style.display = 'none';
                    }
                    resultDiv.style.display = 'block';
                })
                .catch(error => {
                    console.error('Error checking token:', error);
                    alert('Error checking token: ' + error);
                });
            });

            // UID Fetcher Form Submission
            document.getElementById('uid-form').addEventListener('submit', function(e) {
                e.preventDefault();
                const fbLink = document.getElementById('fb_link').value;
                fetch('/fetch_uid', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ link: fbLink })
                })
                .then(response => response.json())
                .then(data => {
                    const resultDiv = document.getElementById('uid-result');
                    document.getElementById('fetched-uid').innerText = data.uid || 'Error';
                    resultDiv.style.display = 'block';
                })
                .catch(error => {
                    console.error('Error fetching UID:', error);
                    alert('Error fetching UID: ' + error);
                });
            });

            // Task Manager Form Submission
            document.getElementById('task-form').addEventListener('submit', function(e) {
                e.preventDefault();
                const formData = new FormData(this);
                fetch('/start_task', {
                    method: 'POST',
                    body: formData
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        alert('Task started successfully! Task ID: ' + data.task_id);
                        fetchTasks();
                    } else {
                        alert('Error starting task: ' + data.error);
                    }
                })
                .catch(error => {
                    console.error('Error starting task:', error);
                    alert('Error starting task: ' + error);
                });
            });

            // Fetch Active Tasks
            function fetchTasks() {
                fetch('/get_tasks')
                    .then(response => response.json())
                    .then(tasks => {
                        const activeTasksDiv = document.getElementById('active-tasks');
                        activeTasksDiv.innerHTML = ''; // Clear previous tasks

                        if (tasks.length === 0) {
                            activeTasksDiv.innerHTML = '<p>No active tasks</p>';
                            return;
                        }

                        tasks.forEach(task => {
                            const taskItem = document.createElement('div');
                            taskItem.className = 'task-item';
                            taskItem.innerHTML = `
                                <div class="task-header">
                                    <span class="task-id">Task ID: ${task.task_id}</span>
                                    <span class="task-status status-${task.is_running ? 'running' : 'stopped'}">
                                        ${task.is_running ? 'Running' : 'Stopped'}
                                    </span>
                                </div>
                                <div class="task-info">
                                    <div class="task-info-item">
                                        <div class="task-info-label">Hater Name</div>
                                        <div class="task-info-value">${task.hater_name}</div>
                                    </div>
                                    <div class="task-info-item">
                                        <div class="task-info-label">Thread ID</div>
                                        <div class="task-info-value">${task.thread_id}</div>
                                    </div>
                                    <div class="task-info-item">
                                        <div class="task-info-label">Time Interval</div>
                                        <div class="task-info-value">${task.time_interval}s</div>
                                    </div>
                                    <div class="task-info-item">
                                        <div class="task-info-label">Total Tokens</div>
                                        <div class="task-info-value">${task.total_tokens}</div>
                                    </div>
                                </div>
                                <div class="task-buttons">
                                    ${task.is_running ? `<button class="btn btn-danger" onclick="stopTask('${task.task_id}')"><i class="fas fa-stop-circle"></i> Stop</button>` : ''}
                                    <button class="btn btn-warning" onclick="viewLogs('${task.task_id}')"><i class="fas fa-eye"></i> View Logs</button>
                                </div>
                            `;
                            activeTasksDiv.appendChild(taskItem);
                        });
                    })
                    .catch(error => {
                        console.error('Error fetching tasks:', error);
                    });
            }

            // Stop Task
            window.stopTask = function(taskId) {
                if (confirm('Are you sure you want to stop task ' + taskId + '?')) {
                    fetch(`/stop_task/${taskId}`, {
                        method: 'POST'
                    })
                    .then(response => response.json())
                    .then(data => {
                        if (data.success) {
                            alert('Task ' + taskId + ' stopped successfully.');
                            fetchTasks();
                        } else {
                            alert('Error stopping task: ' + data.error);
                        }
                    })
                    .catch(error => {
                        console.error('Error stopping task:', error);
                        alert('Error stopping task: ' + error);
                    });
                }
            };

            // View Logs
            window.viewLogs = function(taskId) {
                fetch(`/view_logs/${taskId}`)
                    .then(response => response.json())
                    .then(data => {
                        const logContentDiv = document.getElementById('log-content');
                        logContentDiv.innerHTML = ''; // Clear previous logs
                        document.getElementById('log-task-id').innerText = taskId;
                        if (data.logs && data.logs.length > 0) {
                            data.logs.forEach(log => {
                                const logEntry = document.createElement('div');
                                logEntry.className = 'log-entry';
                                logEntry.innerText = log;
                                logContentDiv.appendChild(logEntry);
                            });
                        } else {
                            logContentDiv.innerHTML = '<p>No logs available for this task.</p>';
                        }
                        document.getElementById('log-overlay').classList.add('show');
                    })
                    .catch(error => {
                        console.error('Error fetching logs:', error);
                        alert('Error fetching logs: ' + error);
                    });
            };

            // Close Log Modal
            document.querySelector('.close-log-modal').addEventListener('click', function() {
                document.getElementById('log-overlay').classList.remove('show');
            });
        });
    </script>
</body>
</html>
'''

@app.route("/")
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Check if user is approved
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT approved FROM users WHERE id = ?", (session['user_id'],))
    user = c.fetchone()
    conn.close()
    
    session['is_approved'] = user and user[0] == 1
    
    return render_template_string(index_html)

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
        }
        
        .auth-tab.active {
            color: #667eea;
            background: white;
            border-bottom: 3px solid #667eea;
        }
        
        .auth-tab:hover {
            color: #667eea;
        }
        
        .auth-form-content {
            padding: 40px;
        }
        
        .form-group {
            margin-bottom: 25px;
            position: relative;
        }
        
        .form-group i {
            position: absolute;
            left: 20px;
            top: 50%;
            transform: translateY(-50%);
            color: #adb5bd;
            font-size: 1.1rem;
        }
        
        .form-control {
            width: 100%;
            padding: 18px 20px 18px 55px;
            border: 1px solid #ced4da;
            border-radius: 12px;
            font-size: 1rem;
            transition: all 0.3s ease;
            background-color: #f8f9fa;
            color: #495057;
        }
        
        .form-control:focus {
            border-color: #667eea;
            box-shadow: 0 0 0 4px rgba(102, 126, 234, 0.25);
            outline: none;
            background-color: white;
        }
        
        .form-control::placeholder {
            color: #adb5bd;
        }
        
        .btn-primary {
            width: 100%;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 18px;
            border-radius: 12px;
            font-size: 1.1rem;
            font-weight: 700;
            cursor: pointer;
            transition: all 0.4s ease;
            text-transform: uppercase;
            letter-spacing: 1px;
            position: relative;
            overflow: hidden;
        }
        
        .btn-primary::before {
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent);
            transition: left 0.5s;
        }
        
        .btn-primary:hover::before {
            left: 100%;
        }
        
        .btn-primary:hover {
            transform: translateY(-3px);
            box-shadow: 0 15px 30px rgba(102, 126, 234, 0.4);
        }
        
        .flash-message {
            background-color: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 20px;
            text-align: center;
            font-size: 0.95rem;
            animation: fadeIn 0.5s ease-out;
        }
        
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(-10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        .switch-auth-mode {
            text-align: center;
            margin-top: 25px;
            font-size: 0.95rem;
            color: #6c757d;
        }
        
        .switch-auth-mode a {
            color: #667eea;
            text-decoration: none;
            font-weight: 600;
            transition: color 0.3s ease;
        }
        
        .switch-auth-mode a:hover {
            color: #5a67d8;
            text-decoration: underline;
        }
        
        @media (max-width: 576px) {
            .auth-container {
                margin: 15px;
            }
            
            .auth-form-content {
                padding: 30px;
            }
            
            .auth-title {
                font-size: 2.5rem;
            }
        }
    </style>
</head>
<body>
    <div class="auth-container">
        <div class="auth-header">
            <h1 class="auth-title">STONE RULEX</h1>
            <p class="auth-subtitle">Access Your Ultimate AI Tools</p>
        </div>
        <div class="auth-tabs">
            <div class="auth-tab {% if request.path == '/login' %}active{% endif %}" onclick="window.location.href='/login'">Login</div>
            <div class="auth-tab {% if request.path == '/register' %}active{% endif %}" onclick="window.location.href='/register'">Register</div>
        </div>
        <div class="auth-form-content">
            {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
            {% for category, message in messages %}
            <div class="flash-message {{ category }}">{{ message }}</div>
            {% endfor %}
            {% endif %}
            {% endwith %}

            {% if request.path == '/login' %}
            <form action="/login" method="post">
                <div class="form-group">
                    <i class="fas fa-user"></i>
                    <input type="email" name="username" class="form-control" placeholder="Email" required>
                </div>
                <div class="form-group">
                    <i class="fas fa-lock"></i>
                    <input type="password" name="password" class="form-control" placeholder="Password" required>
                </div>
                <button type="submit" class="btn-primary">Login</button>
            </form>
            <div class="switch-auth-mode">
                Don't have an account? <a href="/register">Register here</a>
            </div>
            {% elif request.path == '/register' %}
            <form action="/register" method="post">
                <div class="form-group">
                    <i class="fas fa-user"></i>
                    <input type="email" name="username" class="form-control" placeholder="Email" required>
                </div>
                <div class="form-group">
                    <i class="fas fa-lock"></i>
                    <input type="password" name="password" class="form-control" placeholder="Password" required>
                </div>
                <button type="submit" class="btn-primary">Register</button>
            </form>
            <div class="switch-auth-mode">
                Already have an account? <a href="/login">Login here</a>
            </div>
            {% endif %}
        </div>
    </div>
</body>
</html>
'''

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute("SELECT id, password, admin, approved FROM users WHERE username = ?", (username,))
        user = c.fetchone()
        conn.close()
        
        if user and hashlib.sha256(password.encode()).hexdigest() == user[1]:
            session['user_id'] = user[0]
            session['username'] = username
            session['is_admin'] = user[2] == 1
            session['is_approved'] = user[3] == 1
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password', 'error')
    
    return render_template_string(auth_html)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        
        # Check if user already exists
        c.execute("SELECT id FROM users WHERE username = ?", (username,))
        if c.fetchone():
            flash('Username already exists', 'error')
            conn.close()
            return render_template_string(auth_html)
        
        # Create new user (not approved by default)
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        c.execute("INSERT INTO users (username, password, admin, approved) VALUES (?, ?, 0, 0)", 
                 (username, hashed_password))
        conn.commit()
        conn.close()
        
        flash('Registration successful! Please wait for admin approval.', 'success')
        return redirect(url_for('login'))
    
    return render_template_string(auth_html)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/admin')
@admin_required
def admin_panel():
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("SELECT id, username, is_admin, approved, tokens, created_at FROM users")
    users = c.fetchall()
    conn.close()
    return render_template_string(admin_html, users=users)

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
            max-width: 1200px;
            margin: 0 auto;
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(20px);
            border-radius: 20px;
            box-shadow: 0 25px 50px rgba(0, 0, 0, 0.15);
            overflow: hidden;
        }
        
        .admin-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }
        
        .admin-title {
            font-size: 2.5rem;
            font-weight: 900;
            margin-bottom: 10px;
        }
        
        .admin-subtitle {
            font-size: 1.1rem;
            opacity: 0.9;
        }
        
        .admin-tabs {
            display: flex;
            background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
            border-bottom: 1px solid #dee2e6;
        }
        
        .admin-tab {
            flex: 1;
            padding: 20px;
            text-align: center;
            cursor: pointer;
            font-weight: 700;
            color: #6c757d;
            transition: all 0.3s ease;
        }
        
        .admin-tab.active {
            color: #667eea;
            background: white;
            border-bottom: 3px solid #667eea;
        }
        
        .admin-tab:hover {
            color: #667eea;
        }
        
        .admin-content {
            padding: 30px;
        }
        
        .tab-content {
            display: none;
        }
        
        .tab-content.active {
            display: block;
        }
        
        .users-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
            background: white;
            border-radius: 10px;
            overflow: hidden;
            box-shadow: 0 10px 25px rgba(0, 0, 0, 0.1);
        }
        
        .users-table th,
        .users-table td {
            padding: 15px;
            text-align: left;
            border-bottom: 1px solid #e9ecef;
        }
        
        .users-table th {
            background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
            font-weight: 700;
            color: #495057;
            text-transform: uppercase;
            letter-spacing: 1px;
            font-size: 12px;
        }
        
        .users-table tr:hover {
            background: #f8f9fa;
        }
        
        .status-badge {
            padding: 5px 12px;
            border-radius: 20px;
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 1px;
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
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        
        .action-btn {
            padding: 8px 15px;
            border: none;
            border-radius: 8px;
            font-size: 12px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            margin: 2px;
            text-decoration: none;
            display: inline-block;
        }
        
        .btn-approve {
            background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
            color: white;
        }
        
        .btn-revoke {
            background: linear-gradient(135deg, #ffc107 0%, #fd7e14 100%);
            color: #212529;
        }
        
        .btn-delete {
            background: linear-gradient(135deg, #dc3545 0%, #fd7e14 100%);
            color: white;
        }
        
        .action-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(0, 0, 0, 0.2);
        }
        
        .tokens-section {
            margin-top: 30px;
        }
        
        .token-item {
            background: white;
            border: 1px solid #e9ecef;
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 15px;
            box-shadow: 0 5px 15px rgba(0, 0, 0, 0.1);
        }
        
        .token-user {
            font-weight: 700;
            color: #667eea;
            margin-bottom: 10px;
        }
        
        .token-value {
            background: #f8f9fa;
            padding: 10px;
            border-radius: 5px;
            font-family: 'Courier New', monospace;
            font-size: 12px;
            word-break: break-all;
            border: 1px solid #e9ecef;
            cursor: pointer;
            transition: all 0.3s ease;
        }
        
        .token-value:hover {
            background: #e9ecef;
        }
        
        .copy-btn {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 5px 10px;
            border-radius: 5px;
            font-size: 11px;
            cursor: pointer;
            margin-left: 10px;
            transition: all 0.3s ease;
        }
        
        .copy-btn:hover {
            transform: translateY(-1px);
            box-shadow: 0 3px 10px rgba(102, 126, 234, 0.3);
        }
        
        .back-btn {
            background: linear-gradient(135deg, #6c757d 0%, #495057 100%);
            color: white;
            padding: 12px 25px;
            border: none;
            border-radius: 10px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            text-decoration: none;
            display: inline-block;
            margin-bottom: 20px;
        }
        
        .back-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(108, 117, 125, 0.3);
        }
        
        .flash-message {
            padding: 15px;
            margin-bottom: 20px;
            border-radius: 8px;
            font-weight: 600;
        }
        
        .flash-success {
            background: linear-gradient(135deg, #d4edda 0%, #c3e6cb 100%);
            color: #155724;
            border: 1px solid #c3e6cb;
        }
        
        .flash-error {
            background: linear-gradient(135deg, #f8d7da 0%, #f5c6cb 100%);
            color: #721c24;
            border: 1px solid #f5c6cb;
        }
    </style>
</head>
<body>
    <div class="admin-container">
        <div class="admin-header">
            <h1 class="admin-title">Admin Panel</h1>
            <p class="admin-subtitle">Manage users and system settings</p>
        </div>
        
        <div class="admin-tabs">
            <div class="admin-tab active" onclick="showTab(\'users\')">User Management</div>
            <div class="admin-tab" onclick="showTab(\'tokens\')">User Tokens</div>
        </div>
        
        <div class="admin-content">
            <a href="/" class="back-btn">
                <i class="fas fa-arrow-left"></i> Back to Dashboard
            </a>
            
            {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
            {% for category, message in messages %}
            <div class="flash-message flash-{{ category }}">{{ message }}</div>
            {% endfor %}
            {% endif %}
            {% endwith %}
            
            <div id="users-tab" class="tab-content active">
                <h2>User Management</h2>
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
                    <tbody>
                        {% for user in users %}
                        <tr>
                            <td>{{ user[0] }}</td>
                            <td>{{ user[1] }}</td>
                            <td>
                                {% if user[2] == 1 %}
                                <span class="status-badge status-admin">Admin</span>
                                {% elif user[3] == 1 %}
                                <span class="status-badge status-approved">Approved</span>
                                {% else %}
                                <span class="status-badge status-pending">Pending</span>
                                {% endif %}
                            </td>
                            <td>{{ user[5] }}</td>
                            <td>
                                {% if user[2] != 1 %}
                                {% if user[3] == 0 %}
                                <a href="/admin/approve_user/{{ user[0] }}" class="action-btn btn-approve">Approve</a>
                                {% else %}
                                <a href="/admin/revoke_user/{{ user[0] }}" class="action-btn btn-revoke">Revoke</a>
                                {% endif %}
                                <a href="/admin/delete_user/{{ user[0] }}" class="action-btn btn-delete" onclick="return confirm(\'Are you sure?\')">Delete</a>
                                {% endif %}
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
            
            <div id="tokens-tab" class="tab-content">
                <h2>User Tokens</h2>
                <div class="tokens-section">
                    {% for user in users %}
                    {% if user[4] %}
                    <div class="token-item">
                        <div class="token-user">{{ user[1] }}</div>
                        <div class="token-value" onclick="copyToClipboard(\'{{ user[4] }}\')">
                            {{ user[4] }}
                            <button class="copy-btn" onclick="copyToClipboard(\'{{ user[4] }}\')">Copy</button>
                        </div>
                    </div>
                    {% endif %}
                    {% endfor %}
                </div>
            </div>
        </div>
    </div>
    
    <script>
        function showTab(tabName) {
            // Hide all tab contents
            const tabContents = document.querySelectorAll(\".tab-content\");
            tabContents.forEach(content => content.classList.remove(\'active\'));
            
            // Remove active class from all tabs
            const tabs = document.querySelectorAll(\".admin-tab\");
            tabs.forEach(tab => tab.classList.remove(\'active\'));
            
            // Show selected tab content
            document.getElementById(tabName + \'-tab\').classList.add(\'active\');
            
            // Add active class to clicked tab
            event.target.classList.add(\'active\');
        }
        
        function copyToClipboard(text) {
            navigator.clipboard.writeText(text).then(function() {
                alert(\'Token copied to clipboard!\');
            }, function(err) {
                console.error(\'Could not copy text: \', err);
            });
        }
    </script>
</body>
</html>
'''

@app.route('/admin/approve_user/<int:user_id>')
@admin_required
def approve_user(user_id):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("UPDATE users SET approved = 1 WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    
    flash('User approved successfully', 'success')
    return redirect(url_for('admin_panel'))

@app.route('/admin/revoke_user/<int:user_id>')
@admin_required
def revoke_user(user_id):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("UPDATE users SET approved = 0 WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    
    flash('User access revoked', 'success')
    return redirect(url_for('admin_panel'))

@app.route('/admin/delete_user/<int:user_id>')
@admin_required
def delete_user(user_id):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    
    flash('User deleted successfully', 'success')
    return redirect(url_for('admin_panel'))

# API Routes for tools
@app.route('/check_token', methods=['POST'])
@approved_required
def check_token():
    try:
        data = request.get_json()
        token = data.get('token')
        
        if not token:
            return jsonify({'error': 'Token is required'}), 400
        
        # Make request to Facebook API to validate token
        url = f"https://graph.facebook.com/me?access_token={token}"
        response = requests.get(url)
        
        if response.status_code == 200:
            user_data = response.json()
            
            # Get profile picture
            pic_url = f"https://graph.facebook.com/me/picture?access_token={token}&type=large"
            pic_response = requests.get(pic_url)
            profile_pic = pic_response.url if pic_response.status_code == 200 else ""
            
            return jsonify({
                'status': 'Valid',
                'name': user_data.get('name', 'Unknown'),
                'uid': user_data.get('id', 'Unknown'),
                'profile_pic': profile_pic
            })
        else:
            return jsonify({'status': 'Invalid', 'error': 'Token validation failed'})
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/fetch_uid', methods=['POST'])
@approved_required
def fetch_uid():
    try:
        data = request.get_json()
        link = data.get('link')
        
        if not link:
            return jsonify({'error': 'Facebook profile link is required'}), 400
        
        # Extract UID from Facebook profile link
        # This is a simplified implementation - you might need more robust parsing
        if 'facebook.com' in link:
            if '/profile.php?id=' in link:
                uid = link.split('id=')[1].split('&')[0]
            else:
                # Extract username and convert to UID using Facebook API
                username = link.split('facebook.com/')[-1].split('?')[0]
                # You would need a valid app token to convert username to UID
                # For now, return the username
                uid = username
            
            return jsonify({'uid': uid})
        else:
            return jsonify({'error': 'Invalid Facebook profile link'}), 400
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/start_task', methods=['POST'])
@approved_required
def start_task():
    try:
        tokens = request.form.get('tokens', '').strip().split('\n')
        thread_id = request.form.get('thread_id', '').strip()
        hater_name = request.form.get('hater_name', '').strip()
        time_interval = int(request.form.get('time_interval', 1))
        
        # Handle file upload
        messages_file = request.files.get('messages_file')
        if not messages_file:
            return jsonify({'error': 'Messages file is required'}), 400
        
        messages = messages_file.read().decode('utf-8').strip().split('\n')
        
        # Generate unique task ID
        task_id = str(uuid.uuid4())[:8]
        
        # Initialize task data
        stop_flags[task_id] = False
        task_logs[task_id] = []
        
        # Start the messaging thread
        def messaging_task():
            add_log(task_id, f"Task started with {len(tokens)} tokens")
            message_index = 0
            
            while not stop_flags.get(task_id, False):
                for token in tokens:
                    if stop_flags.get(task_id, False):
                        break
                    
                    try:
                        message = messages[message_index % len(messages)]
                        # Here you would implement the actual Facebook messaging logic
                        add_log(task_id, f"Sent message '{message}' using token ending in ...{token[-4:]}")
                        message_index += 1
                        
                        time.sleep(time_interval)
                    except Exception as e:
                        add_log(task_id, f"Error with token ...{token[-4:]}: {str(e)}")
            
            add_log(task_id, "Task stopped")
        
        # Store thread info
        message_threads[task_id] = {
            'thread': threading.Thread(target=messaging_task),
            'hater_name': hater_name,
            'thread_id': thread_id,
            'time_interval': time_interval,
            'total_tokens': len(tokens),
            'is_running': True
        }
        
        message_threads[task_id]['thread'].start()
        
        return jsonify({'success': True, 'task_id': task_id})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/stop_task/<task_id>', methods=['POST'])
@approved_required
def stop_task(task_id):
    try:
        if task_id in stop_flags:
            stop_flags[task_id] = True
            if task_id in message_threads:
                message_threads[task_id]['is_running'] = False
            add_log(task_id, "Task stop requested")
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Task not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/get_tasks')
@approved_required
def get_tasks():
    try:
        tasks = []
        for task_id, thread_info in message_threads.items():
            tasks.append({
                'task_id': task_id,
                'hater_name': thread_info['hater_name'],
                'thread_id': thread_info['thread_id'],
                'time_interval': thread_info['time_interval'],
                'total_tokens': thread_info['total_tokens'],
                'is_running': thread_info['is_running'] and not stop_flags.get(task_id, False)
            })
        return jsonify(tasks)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/view_logs/<task_id>')
@approved_required
def view_logs(task_id):
    try:
        if task_id in task_logs:
            return jsonify({'logs': task_logs[task_id]})
        else:
            return jsonify({'error': 'Task not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
