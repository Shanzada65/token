from flask import Flask, render_template_string, request, jsonify, session, redirect, url_for
import requests
import json
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os
import secrets
import threading
import time
import uuid
from functools import wraps

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///site.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)
app.secret_key = secrets.token_hex(16)

# Global dictionary to store running tasks and their threads
running_tasks = {}


# Database Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    is_approved = db.Column(db.Boolean, default=False, nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    tasks = db.relationship('Task', backref='author', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"User(\'{self.username}\', Approved: {self.is_approved}, Admin: {self.is_admin})"

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    task_type = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    logs = db.relationship('TaskLog', backref='task', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f"Task(\'{self.task_type}\', \'{self.status}\', User: {self.user_id})"

class TaskLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('task.id'), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    message = db.Column(db.Text, nullable=False)

    def __repr__(self):
        return f"TaskLog(\'{self.message}\', Task: {self.task_id})"

# Create database tables if they don\'t exist
with app.app_context():
    db.create_all()

    # Create a default admin user if one doesn't exist
    if not User.query.filter_by(username='admin').first():
        admin_user = User(username='admin', is_admin=True, is_approved=True)
        admin_user.set_password('adminpassword')  # Change this to a strong password in production
        db.session.add(admin_user)
        db.session.commit()
        print("Default admin user 'admin' created with password 'adminpassword'")

# In-memory storage for demonstration (replace with database in production)
# tasks_storage = {}
# users_storage = {}

# HTML Template with embedded CSS and JavaScript
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Facebook Automation Tool</title>
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
            color: #333;
        }

        .navbar {
            background: rgba(0, 0, 0, 0.8);
            padding: 15px 30px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.3);
            position: sticky;
            top: 0;
            z-index: 1000;
        }

        .navbar-brand {
            color: #fff;
            font-size: 24px;
            font-weight: bold;
            text-decoration: none;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .navbar-brand:hover {
            color: #667eea;
        }

        .navbar-links {
            display: flex;
            gap: 20px;
            align-items: center;
        }

        .navbar-links a, .navbar-links button {
            color: #fff;
            text-decoration: none;
            padding: 8px 15px;
            border-radius: 5px;
            transition: all 0.3s ease;
            border: none;
            background: transparent;
            cursor: pointer;
            font-size: 14px;
        }

        .navbar-links a:hover, .navbar-links button:hover {
            background: #667eea;
            transform: translateY(-2px);
        }

        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 30px 20px;
        }

        .home-header {
            text-align: center;
            color: white;
            margin-bottom: 50px;
            animation: slideDown 0.6s ease;
        }

        .home-header h1 {
            font-size: 48px;
            margin-bottom: 15px;
            text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.3);
        }

        .home-header p {
            font-size: 18px;
            opacity: 0.9;
        }

        .tools-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 30px;
            margin-bottom: 40px;
        }

        .tool-card {
            background: white;
            border-radius: 15px;
            overflow: hidden;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
            transition: all 0.3s ease;
            cursor: pointer;
            animation: fadeInUp 0.6s ease;
        }

        .tool-card:hover {
            transform: translateY(-10px);
            box-shadow: 0 15px 40px rgba(0, 0, 0, 0.3);
        }

        .tool-image-new {
            width: 100%;
            height: 200px;
            object-fit: cover;
        }

        .tool-content {
            padding: 20px;
            text-align: center;
        }

        .tool-content h3 {
            margin-bottom: 15px;
            color: #333;
            font-size: 20px;
        }

        .tool-btn {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 12px 25px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 16px;
            font-weight: bold;
            transition: all 0.3s ease;
            width: 100%;
        }

        .tool-btn:hover {
            transform: scale(1.05);
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
        }

        .tool-btn.green {
            background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
        }

        .tool-btn.yellow {
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        }

.tool-btn.orange {
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        }
        .tool-btn.red {
            background: linear-gradient(135deg, #ff416c 0%, #ff4b2b 100%);
        }
        .task-card {
            background: white;
            border-radius: 15px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 5px 15px rgba(0, 0, 0, 0.1);
        }
        .task-card h3 {
            margin-bottom: 10px;
            color: #333;
        }
        .task-card p {
            color: #666;
            font-size: 14px;
            margin-bottom: 10px;
        }
        .task-logs {
            background: #f8f9fa;
            border: 1px solid #eee;
            border-radius: 8px;
            padding: 15px;
            margin-top: 15px;
            max-height: 300px;
            overflow-y: auto;
            font-family: 'Courier New', Courier, monospace;
            font-size: 12px;
            white-space: pre-wrap;
            word-wrap: break-word;
        }
        .task-running {
            border-left: 5px solid #667eea;
        }
        .task-completed {
            border-left: 5px solid #38ef7d;
        }
        .task-stopped {
            border-left: 5px solid #f5576c;
        }
        .tool-btn.small {
            padding: 5px 10px;
            font-size: 12px;
            width: auto;
            display: inline-block;
            margin: 0 5px;
        }
        .user-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }
        .user-table th, .user-table td {
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
        }
        .user-table th {
            background-color: #f2f2f2;
            font-weight: bold;
        }

        .tool-section {
            display: none;
            animation: fadeIn 0.4s ease;
        }

        .tool-section.active {
            display: block;
        }

        .form-group {
            margin-bottom: 20px;
            text-align: left;
        }

        .form-group label {
            display: block;
            margin-bottom: 8px;
            font-weight: bold;
            color: #333;
        }

        .form-group input,
        .form-group textarea,
        .form-group select {
            width: 100%;
            padding: 12px;
            border: 2px solid #ddd;
            border-radius: 8px;
            font-size: 14px;
            transition: border-color 0.3s ease;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }

        .form-group input:focus,
        .form-group textarea:focus,
        .form-group select:focus {
            outline: none;
            border-color: #667eea;
            box-shadow: 0 0 10px rgba(102, 126, 234, 0.2);
        }

        .form-group textarea {
            resize: vertical;
            min-height: 100px;
        }

        .submit-btn {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 14px 30px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 16px;
            font-weight: bold;
            transition: all 0.3s ease;
            width: 100%;
        }

        .submit-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(102, 126, 234, 0.3);
        }

        .submit-btn:active {
            transform: translateY(0);
        }

        .home-btn {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 12px 25px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 16px;
            font-weight: bold;
            margin-bottom: 30px;
            transition: all 0.3s ease;
        }

        .home-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
        }

        .result-box {
            background: #f8f9fa;
            border-left: 4px solid #667eea;
            padding: 20px;
            border-radius: 8px;
            margin-top: 20px;
            display: none;
        }

        .result-box.show {
            display: block;
            animation: slideIn 0.4s ease;
        }

        .result-box.success {
            border-left-color: #38ef7d;
            background: #f0fdf4;
        }

        .result-box.error {
            border-left-color: #f5576c;
            background: #fdf0f0;
        }

        .result-box h4 {
            margin-bottom: 10px;
            color: #333;
        }

        .result-box p {
            color: #666;
            line-height: 1.6;
            word-break: break-all;
        }

        .loading {
            display: none;
            text-align: center;
            margin: 20px 0;
        }

        .spinner {
            border: 4px solid #f3f3f3;
            border-top: 4px solid #667eea;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 0 auto;
        }

        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }

        @keyframes slideDown {
            from {
                opacity: 0;
                transform: translateY(-30px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
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

        @keyframes fadeIn {
            from {
                opacity: 0;
            }
            to {
                opacity: 1;
            }
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

        .tool-wrapper {
            background: white;
            border-radius: 15px;
            padding: 40px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
            max-width: 600px;
            margin: 0 auto;
        }

        .tool-wrapper h2 {
            color: #333;
            margin-bottom: 30px;
            text-align: center;
            font-size: 28px;
        }

        .developer-link {
            display: inline-block;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 10px 20px;
            border-radius: 8px;
            text-decoration: none;
            font-weight: bold;
            transition: all 0.3s ease;
            margin-left: 10px;
        }

        .developer-link:hover {
            transform: scale(1.05);
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
        }

        .token-result {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 8px;
            margin-top: 15px;
            display: none;
        }

        .token-result.show {
            display: block;
        }

        .token-valid {
            border-left: 4px solid #38ef7d;
            background: #f0fdf4;
        }

        .token-invalid {
            border-left: 4px solid #f5576c;
            background: #fdf0f0;
        }

        .profile-info {
            display: grid;
            grid-template-columns: 100px 1fr;
            gap: 20px;
            align-items: center;
            margin-top: 15px;
        }

        .profile-pic {
            width: 100px;
            height: 100px;
            border-radius: 50%;
            object-fit: cover;
            border: 3px solid #667eea;
        }

        .profile-details h4 {
            color: #333;
            margin-bottom: 5px;
        }

        .profile-details p {
            color: #666;
            margin: 5px 0;
            font-size: 14px;
        }

        .tasks-container {
            background: white;
            border-radius: 15px;
            padding: 30px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
        }

        .task-item {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 15px;
            border-left: 4px solid #667eea;
        }

        .task-item h4 {
            color: #333;
            margin-bottom: 10px;
        }

        .task-info {
            color: #666;
            font-size: 14px;
            line-height: 1.6;
        }

        @media (max-width: 768px) {
            .tools-grid {
                grid-template-columns: 1fr;
            }

            .home-header h1 {
                font-size: 32px;
            }

            .tool-wrapper {
                padding: 20px;
            }

            .navbar {
                flex-direction: column;
                gap: 15px;
            }

            .navbar-links {
                flex-direction: column;
                width: 100%;
            }

            .navbar-links a, .navbar-links button {
                width: 100%;
                text-align: center;
            }
        }
    </style>
</head>
<body>
    <nav class="navbar">
        <div class="navbar-brand">
            📱 FB Automation Tool
        </div>
        <div class="navbar-links">
            {% if session.get("user_id") %}
                <a href="/" onclick="goHome(event)">🏠 Home</a>
                <a href="/tasks">📊 My Tasks</a>
                {% if session.get("is_admin") %}
                    <a href="/admin">⚙️ Admin Panel</a>
                {% endif %}
                <a href="/logout">👋 Logout ({{ session.get("username") }})</a>
            {% else %}
                <a href="/login">🔑 Login</a>
                <a href="/signup">📝 Signup</a>
            {% endif %}

        </div>
    </nav>

    <div class="container">
        {% if pending_approval %}
            <div class="result-box show orange">
                <h4>⏳ Account Pending Approval</h4>
                <p>Your account is awaiting approval from an administrator. You will gain access to the tools once approved.</p>
                <p>Please check back later or contact an administrator.</p>
            </div>
        {% elif show_signup %}
            <div id="signup-section" class="tool-section active">
                <div class="tool-wrapper">
                    <h2>📝 Signup</h2>
                    <form action="/signup" method="POST">
                        <div class="form-group">
                            <label for="signup-username">Username:</label>
                            <input type="text" id="signup-username" name="username" required>
                        </div>
                        <div class="form-group">
                            <label for="signup-password">Password:</label>
                            <input type="password" id="signup-password" name="password" required>
                        </div>
                        <button type="submit" class="submit-btn">Signup</button>
                    </form>
                    {% if signup_error %}
                        <div class="result-box show error">
                            <p>{{ signup_error }}</p>
                        </div>
                    {% endif %}
                </div>
            </div>
        {% elif show_login %}
            <div id="login-section" class="tool-section active">
                <div class="tool-wrapper">
                    <h2>🔑 Login</h2>
                    <form action="/login" method="POST">
                        <div class="form-group">
                            <label for="login-username">Username:</label>
                            <input type="text" id="login-username" name="username" required>
                        </div>
                        <div class="form-group">
                            <label for="login-password">Password:</label>
                            <input type="password" id="login-password" name="password" required>
                        </div>
                        <button type="submit" class="submit-btn">Login</button>
                    </form>
                    {% if login_error %}
                        <div class="result-box show error">
                            <p>{{ login_error }}</p>
                        </div>
                    {% endif %}
                    {% if signup_success %}
                        <div class="result-box show success">
                            <p>{{ signup_success }}</p>
                        </div>
                    {% endif %}
                </div>
            </div>
        {% else %}
            <!-- Home Section -->
            <div id="home-section" class="tool-section active"></div>
        {% endif %}
        {% elif show_tasks %}
            <div id="tasks-section" class="tool-section active">
                <button class="home-btn" onclick="goHome()">← Back to Home</button>
                <div class="tool-wrapper">
                    <h2>📊 My Running Tasks</h2>
                    {% if user_tasks %}
                        {% for task in user_tasks %}
                            <div class="task-card {% if task.status == 'running' %}task-running{% elif task.status == 'completed' %}task-completed{% else %}task-stopped{% endif %}">
                                <h3>Task #{{ task.id }} ({{ task.task_type.capitalize() }}) - Status: {{ task.status.capitalize() }}</h3                                <p>Started: {{ task.created_at.strftime(\"%Y-%m-%d %H:%M:%S\") }} ({{ (datetime.utcnow() - task.created_at).days }} days ago)</p>
                                {% if task.status == 'running' %}
                                    <button class="tool-btn red small" onclick="stopTask({{ task.id }})">Stop Task</button>
                                {% endif %}
                                <button class="tool-btn green small" onclick="toggleLogs({{ task.id }})">View Logs</button>
                                <script>
                                    // Immediately show logs for running tasks
                                    if ("{{ task.status }}" === "running") {
                                        toggleLogs({{ task.id }});
                                    }
                                </script>
                                <div id="logs-{{ task.id }}" class="task-logs" style="display: none;">
                                    <h4>Logs (last hour):</h4>
                                    <pre id="log-content-{{ task.id }}"></pre>
                                </div>
                            </div>
                        {% endfor %}
                    {% else %}
                        <p>No tasks found.</p>
                    {% endif %}
                </div>
            </div>
        {% elif show_admin_panel %}
            <div id="admin-panel-section" class="tool-section active">
                <button class="home-btn" onclick="goHome()">← Back to Home</button>
                <div class="tool-wrapper">
                    <h2>⚙️ Admin Panel</h2>
                    <h3>User Management</h3>
                    <table class="user-table">
                        <thead>
                            <tr>
                                <th>ID</th>
                                <th>Username</th>
                                <th>Approved</th>
                                <th>Admin</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for user in users %}
                            <tr>
                                <td>{{ user.id }}</td>
                                <td>{{ user.username }}</td>
                                <td>{{ 'Yes' if user.is_approved else 'No' }}</td>
                                <td>{{ 'Yes' if user.is_admin else 'No' }}</td>
                                <td>
                                    {% if not user.is_admin %}
                                        {% if user.is_approved %}
                                            <a href="/admin/revoke/{{ user.id }}" class="tool-btn orange small">Revoke</a>
                                        {% else %}
                                            <a href="/admin/approve/{{ user.id }}" class="tool-btn green small">Approve</a>
                                        {% endif %}
                                        <a href="/admin/delete/{{ user.id }}" class="tool-btn red small">Delete</a>
                                    {% else %}
                                        Admin
                                    {% endif %}
                                </td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            </div>
        {% else %}
            <div class="home-header">
                <h1>🎯 Facebook Automation Suite</h1>
                <p>All-in-one tool for Facebook automation tasks</p>
            </div>

            <div class="tools-grid">
                <!-- Conversation Tool -->
                <div class="tool-card">
                    <img src="https://i.ibb.co/jvHqh7QD/13fb6dc6b204872d1040a1e94aeff66f.jpg" alt="Conversation Tool" class="tool-image-new">
                    <div class="tool-content">
                        <button class="tool-btn" onclick="showTool('convo-section')">CONVO TOOL</button>
                    </div>
                </div>



                <!-- Token Checker -->
                <div class="tool-card">
                    <img src="https://i.ibb.co/jvHqh7QD/13fb6dc6b204872d1040a1e94aeff66f.jpg" alt="Token Checker" class="tool-image-new">
                    <div class="tool-content">
                        <button class="tool-btn green" onclick="showTool('token-section')">TOKEN CHECK</button>
                    </div>
                </div>

                <!-- UID Fetcher -->
                <div class="tool-card">
                    <img src="https://i.ibb.co/jvHqh7QD/13fb6dc6b204872d1040a1e94aeff66f.jpg" alt="UID Fetcher" class="tool-image-new">
                    <div class="tool-content">
                        <button class="tool-btn yellow" onclick="showTool('uid-section')">UID FETCHER</button>
                    </div>
                </div>

                <!-- Task Manager Tool -->
                <div class="tool-card">
                    <img src="https://i.ibb.co/jvHqh7QD/13fb6dc6b204872d1040a1e94aeff66f.jpg" alt="Task Manager" class="tool-image-new">
                    <div class="tool-content">
                        <button class="tool-btn green" onclick="window.location.href='/tasks'">TASK MANAGER</button>
                    </div>
                </div>

                <!-- Developer Info -->
                <div class="tool-card">
                    <img src="https://i.ibb.co/jvHqh7QD/13fb6dc6b204872d1040a1e94aeff66f.jpg" alt="Developer" class="tool-image-new">
                    <div class="tool-content">
                        <h3>Developer</h3>
                        <button class="tool-btn" onclick="window.open(\'https://www.facebook.com/SH33T9N.BOII.ONIFR3\', \'_blank\')">View Profile</button>
                    </div>
                </div>
            </div>
        </div>

        <!-- Conversation Tool Section -->
        <div id="convo-section" class="tool-section">
            <button class="home-btn" onclick="goHome()">← Back to Home</button>
            <div class="tool-wrapper">
                <h2>💬 Conversation Message Sender</h2>
                <form onsubmit="sendConversationMessage(event)">
                    <div class="form-group">
                        <label for="convo-token">Facebook Token:</label>
                        <input type="password" id="convo-token" name="token" required placeholder="Enter your Facebook token">
                    </div>
                    <div class="form-group">
                        <label for="convo-uid">Recipient UID:</label>
                        <input type="text" id="convo-uid" name="uid" required placeholder="Enter recipient user ID">
                    </div>
                    <div class="form-group">
                        <div class="form-group">
                            <label for="convo-prefix">Prefix Name (Optional):</label>
                            <input type="text" id="convo-prefix" name="prefix" placeholder="e.g., [Bot] or Your Name">
                        </div>
                        <div class="form-group">
                            <label for="convo-speed">Sending Speed (seconds per message):</label>
                            <input type="number" id="convo-speed" name="speed" value="1" min="0.1" step="0.1" required>
                        </div>
                        <label for="convo-message">Message:</label>
                        <textarea id="convo-message" name="message" required placeholder="Enter your message here..."></textarea>
                    </div>
                    <div class="loading" id="convo-loading">
                        <div class="spinner"></div>
                        <p>Sending message...</p>
                    </div>
                    <button type="submit" class="submit-btn">Send Message</button>
                </form>
                <div class="result-box" id="convo-result"></div>
            </div>
        </div>

        <!-- Post Comment Tool Section -->
        <div id="comment-section" class="tool-section">
            <button class="home-btn" onclick="goHome()">← Back to Home</button>
            <div class="tool-wrapper">
                <h2>💭 Post Comment Tool</h2>
                <form onsubmit="postComment(event)">
                    <div class="form-group">
                        <label for="comment-token">Facebook Token:</label>
                        <input type="password" id="comment-token" name="token" required placeholder="Enter your Facebook token">
                    </div>
                    <div class="form-group">
                        <label for="post-id">Post ID:</label>
                        <input type="text" id="post-id" name="post_id" required placeholder="Enter post ID">
                    </div>
                    <div class="form-group">
                        <div class="form-group">
                            <label for="comment-prefix">Prefix Name (Optional):</label>
                            <input type="text" id="comment-prefix" name="prefix" placeholder="e.g., [Bot] or Your Name">
                        </div>
                        <div class="form-group">
                            <label for="comment-speed">Sending Speed (seconds per message):</label>
                            <input type="number" id="comment-speed" name="speed" value="1" min="0.1" step="0.1" required>
                        </div>
                        <label for="comment-text">Comment Text:</label>
                        <textarea id="comment-text" name="comment" required placeholder="Enter your comment..."></textarea>
                    </div>
                    <div class="loading" id="comment-loading">
                        <div class="spinner"></div>
                        <p>Posting comment...</p>
                    </div>
                    <button type="submit" class="submit-btn">Post Comment</button>
                </form>
                <div class="result-box" id="comment-result"></div>
            </div>
        </div>

        <!-- Token Checker Section -->
        <div id="token-section" class="tool-section">
            <button class="home-btn" onclick="goHome()">← Back to Home</button>
            <div class="tool-wrapper">
                <h2>🔐 Token Checker</h2>
                <form onsubmit="checkToken(event)">
                    <div class="form-group">
                        <label for="check-token">Facebook Token:</label>
                        <input type="password" id="check-token" name="token" required placeholder="Enter your Facebook token">
                    </div>
                    <div class="loading" id="token-loading">
                        <div class="spinner"></div>
                        <p>Checking token...</p>
                    </div>
                    <button type="submit" class="submit-btn">Check Token</button>
                </form>
                <div class="token-result" id="token-result"></div>
            </div>
        </div>

        <!-- UID Fetcher Section -->
        <div id="uid-section" class="tool-section">
            <button class="home-btn" onclick="goHome()">← Back to Home</button>
            <div class="tool-wrapper">
                <h2>🔍 Messenger Groups UID Fetcher</h2>
                <form onsubmit="fetchMessengerGroups(event)">
                    <div class="form-group">
                        <label for="uid-token">Facebook Token:</label>
                        <input type="password" id="uid-token" name="token" required placeholder="Enter your Facebook token">
                    </div>
                    <div class="loading" id="uid-loading">
                        <div class="spinner"></div>
                        <p>Fetching groups...</p>
                    </div>
                    <button type="submit" class="submit-btn">Fetch Groups</button>
                </form>
                <div class="result-box" id="uid-result"></div>
            </div>
        </div>
    {% endif %}
    </body>
</html>

<script>
    // Function to stop a task
    function stopTask(taskId) {
        if (confirm('Are you sure you want to stop this task?')) {
            fetch(`/api/stop-task/${taskId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert(data.message);
                    location.reload(); // Reload to update task list
                } else {
                    alert('Error stopping task: ' + data.error);
                }
            })
            .catch(error => {
                console.error('Error stopping task:', error);
                alert('An error occurred while stopping the task.');
            });
        }
    }

    // Function to toggle and fetch logs
    const logIntervals = {};

    function toggleLogs(taskId) {
        const logsDiv = document.getElementById(`logs-${taskId}`);
        const logContentPre = document.getElementById(`log-content-${taskId}`);

        if (logsDiv.style.display === 'none') {
            logsDiv.style.display = 'block';
            logContentPre.innerHTML = 'Loading logs...';
            fetchLogs(taskId, logContentPre);
            // Start polling for new logs every 5 seconds
            logIntervals[taskId] = setInterval(() => fetchLogs(taskId, logContentPre), 5000);
            // Refresh the entire task list every 15 seconds to update status
            setInterval(() => {
                if (document.getElementById("tasks-section").classList.contains("active")) {
                    location.reload();
                }
            }, 15000);
        } else {
            logsDiv.style.display = 'none';
            // Stop polling for logs
            clearInterval(logIntervals[taskId]);
            delete logIntervals[taskId];
        }
    }

    function fetchLogs(taskId, logContentPre) {
        fetch(`/api/task-logs/${taskId}`)
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    logContentPre.innerHTML = data.logs.map(log => `[${log.timestamp}] ${log.message}`).join('\n');
                    logContentPre.scrollTop = logContentPre.scrollHeight; // Auto-scroll to bottom
                } else {
                    logContentPre.innerHTML = 'Error fetching logs: ' + data.error;
                }
            })
            .catch(error => {
                console.error('Error fetching logs:', error);
                logContentPre.innerHTML = 'An error occurred while fetching logs.';
            });
    }

    // Ensure goHome is defined globally or within the script context
    if (typeof goHome !== 'function') {
        function goHome(event) {
            if (event) event.preventDefault();
            const sections = document.querySelectorAll('.tool-section');
            sections.forEach(section => section.classList.remove('active'));
            document.getElementById('home-section').classList.add('active');
            document.querySelectorAll('.result-box, .token-result').forEach(box => {
                box.classList.remove('show');
            });
            window.scrollTo(0, 0);
        }
    }
</script>
    // Ensure goHome is defined globally or within the script context
    if (typeof goHome !== 'function') {
        function goHome(event) {
            if (event) event.preventDefault();
            const sections = document.querySelectorAll('.tool-section');
            sections.forEach(section => section.classList.remove('active'));
            document.getElementById('home-section').classList.add('active');
            document.querySelectorAll('.result-box, .token-result').forEach(box => {
                box.classList.remove('show');
            });
            window.scrollTo(0, 0);
        }
    }
</script>
 <script>
        function showTool(toolId) {
            // Hide all sections
            const sections = document.querySelectorAll('.tool-section');
            sections.forEach(section => section.classList.remove('active'));
            
            // Show selected tool
            document.getElementById(toolId).classList.add('active');
            
            // Scroll to top
            window.scrollTo(0, 0);
        }

        function goHome(event) {
            if (event) event.preventDefault();
            
            // Hide all sections
            const sections = document.querySelectorAll('.tool-section');
            sections.forEach(section => section.classList.remove('active'));
            
            // Show home section
            document.getElementById('home-section').classList.add('active');
            
            // Clear all results
            document.querySelectorAll('.result-box, .token-result').forEach(box => {
                box.classList.remove('show');
            });
            
            // Scroll to top
            window.scrollTo(0, 0);
        }

        function showResult(elementId, message, isSuccess = true, isTokenResult = false) {
            const resultBox = document.getElementById(elementId);
            resultBox.innerHTML = `
                <h4>${isSuccess ? '✅ Success' : '❌ Error'}</h4>
                <p>${message}</p>
            `;
            resultBox.classList.add('show');
            resultBox.classList.add(isSuccess ? 'success' : 'error');
            if (isTokenResult) {
                resultBox.classList.add(isSuccess ? 'token-valid' : 'token-invalid');
            }
        }

        function sendConversationMessage(event) {
            event.preventDefault();
            
            const token = document.getElementById('convo-token').value;
            const uid = document.getElementById('convo-uid').value;
            const message = document.getElementById('convo-message').value;
            const loading = document.getElementById('convo-loading');
            const resultBox = document.getElementById('convo-result');
            
            loading.style.display = 'block';
            resultBox.classList.remove('show');
            
            fetch('/api/send-message', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                    body: JSON.stringify({
                        token: token,
                        uid: uid,
                        message: message,
                        prefix: document.getElementById("convo-prefix").value,
                        speed: parseFloat(document.getElementById("convo-speed").value)
                    })
            })
            .then(response => response.json())
            .then(data => {
                loading.style.display = 'none';
                if (data.success) {
                    showResult('convo-result', `Message sent successfully! Message ID: ${data.message_id}`);
                    document.getElementById('convo-message').value = '';
                } else {
                    showResult('convo-result', data.error, false);
                }
            })
            .catch(error => {
                loading.style.display = 'none';
                showResult('convo-result', `Error: ${error.message}`, false);
            });
        }

        function postComment(event) {
            event.preventDefault();
            
            const token = document.getElementById('comment-token').value;
            const postId = document.getElementById('post-id').value;
            const comment = document.getElementById('comment-text').value;
            const loading = document.getElementById('comment-loading');
            const resultBox = document.getElementById('comment-result');
            
            loading.style.display = 'block';
            resultBox.classList.remove('show');
            
            fetch('/api/post-comment', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                    body: JSON.stringify({
                        token: token,
                        post_id: postId,
                        comment: comment,
                        prefix: document.getElementById("comment-prefix").value,
                        speed: parseFloat(document.getElementById("comment-speed").value)
                    })
            })
            .then(response => response.json())
            .then(data => {
                loading.style.display = 'none';
                if (data.success) {
                    showResult('comment-result', `Comment posted successfully! Comment ID: ${data.comment_id}`);
                    document.getElementById('comment-text').value = '';
                } else {
                    showResult('comment-result', data.error, false);
                }
            })
            .catch(error => {
                loading.style.display = 'none';
                showResult('comment-result', `Error: ${error.message}`, false);
            });
        }

        function checkToken(event) {
            event.preventDefault();
            
            const token = document.getElementById('check-token').value;
            const loading = document.getElementById('token-loading');
            const resultBox = document.getElementById('token-result');
            
            loading.style.display = 'block';
            resultBox.classList.remove('show');
            
            fetch('/api/check-token', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    token: token
                })
            })
            .then(response => response.json())
            .then(data => {
                loading.style.display = 'none';
                if (data.valid) {
                    const profileHtml = `
                        <h4>✅ Token is Valid</h4>
                        <div class="profile-info">
                            <img src="${data.profile_pic}" alt="Profile" class="profile-pic" onerror="this.src='https://via.placeholder.com/100'">
                            <div class="profile-details">
                                <h4>${data.name}</h4>
                                <p><strong>UID:</strong> ${data.uid}</p>
                                <p><strong>Email:</strong> ${data.email || 'N/A'}</p>
                            </div>
                        </div>
                    `;
                    resultBox.innerHTML = profileHtml;
                    resultBox.classList.add('show', 'token-valid');
                } else {
                    resultBox.innerHTML = `
                        <h4>❌ Token is Invalid</h4>
                        <p>${data.error}</p>
                    `;
                    resultBox.classList.add('show', 'token-invalid');
                }
            })
            .catch(error => {
                loading.style.display = 'none';
                resultBox.innerHTML = `
                    <h4>❌ Error</h4>
                    <p>${error.message}</p>
                `;
                resultBox.classList.add('show', 'token-invalid');
            });
        }

        function fetchMessengerGroups(event) {
            event.preventDefault();
            
            const token = document.getElementById('uid-token').value;
            const loading = document.getElementById('uid-loading');
            const resultBox = document.getElementById('uid-result');
            
            loading.style.display = 'block';
            resultBox.classList.remove('show');
            
            fetch('/api/fetch-groups', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    token: token
                })
            })
            .then(response => response.json())
            .then(data => {
                loading.style.display = 'none';
                if (data.success) {
                    let groupsHtml = '<h4>✅ Groups Found</h4>';
                    if (data.groups && data.groups.length > 0) {
                        groupsHtml += '<div style="max-height: 400px; overflow-y: auto;">';
                        data.groups.forEach(group => {
                            groupsHtml += `
                                <div style="background: #f0f0f0; padding: 10px; margin: 10px 0; border-radius: 5px;">
                                    <strong>${group.name}</strong><br>
                                    <small>UID: ${group.id}</small>
                                </div>
                            `;
                        });
                        groupsHtml += '</div>';
                    } else {
                        groupsHtml += '<p>No groups found.</p>';
                    }
                    resultBox.innerHTML = groupsHtml;
                    resultBox.classList.add('show', 'success');
                } else {
                    resultBox.innerHTML = `
                        <h4>❌ Error</h4>
                        <p>${data.error}</p>
                    `;
                    resultBox.classList.add('show', 'error');
                }
            })
            .catch(error => {
                loading.style.display = 'none';
                resultBox.innerHTML = `
                    <h4>❌ Error</h4>
                    <p>${error.message}</p>
                `;
                resultBox.classList.add('show', 'error');
            });
        }
    </script>
</body>
</html>
'''

# Routes

# Helper functions for authentication
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        user = User.query.get(session['user_id'])
        if not user or not user.is_admin:
            return redirect(url_for('home')) # Or an unauthorized page
        return f(*args, **kwargs)
    return decorated_function


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            return render_template_string(HTML_TEMPLATE, signup_error='Username already exists')
        
        new_user = User(username=username)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login', signup_success='Account created. Please wait for admin approval.'))
    return render_template_string(HTML_TEMPLATE, show_signup=True)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            session['user_id'] = user.id
            session['username'] = user.username
            session['is_admin'] = user.is_admin
            session['is_approved'] = user.is_approved
            return redirect(url_for('home'))
        else:
            return render_template_string(HTML_TEMPLATE, login_error='Invalid username or password', show_login=True)
    return render_template_string(HTML_TEMPLATE, show_login=True)

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    session.pop('is_admin', None)
    session.pop('is_approved', None)
    return redirect(url_for('home'))

@app.route("/")
@login_required
def home():
    user = User.query.get(session["user_id"])
    if not user.is_approved and not user.is_admin:
        return render_template_string(HTML_TEMPLATE, user=user, pending_approval=True)
    return render_template_string(HTML_TEMPLATE, user=user, session=session)

@app.route('/admin')
@admin_required
def admin_panel():
    users = User.query.all()
    return render_template_string(HTML_TEMPLATE, users=users, show_admin_panel=True)

@app.route('/admin/approve/<int:user_id>')
@admin_required
def admin_approve_user(user_id):
    user = User.query.get_or_404(user_id)
    user.is_approved = True
    db.session.commit()
    return redirect(url_for('admin_panel'))

@app.route('/admin/revoke/<int:user_id>')
@admin_required
def admin_revoke_user(user_id):
    user = User.query.get_or_404(user_id)
    user.is_approved = False
    # Stop all tasks for this user if their approval is revoked
    # tasks_to_stop = Task.query.filter_by(user_id=user.id, status='running').all()
    # for task in tasks_to_stop:
    #     task.status = 'stopped'
    #     # Add a log entry for task stoppage
    #     new_log = TaskLog(task_id=task.id, message=f'Task stopped due to user approval revocation by admin.')
    #     db.session.add(new_log)
    db.session.commit()
    return redirect(url_for('admin_panel'))

@app.route('/admin/delete/<int:user_id>')
@admin_required
def admin_delete_user(user_id):
    user = User.query.get_or_404(user_id)
    # Delete associated tasks and logs first due to cascade
    db.session.delete(user)
    db.session.commit()
    return redirect(url_for('admin_panel'))

@app.route('/api/send-message', methods=['POST'])
@login_required
def send_message():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'success': False, 'error': 'User not logged in'}), 401

    try:
        data = request.json
        token = data.get('token')
        uid = data.get('uid')
        message_content = data.get('message')
        prefix = data.get('prefix', '')
        speed = float(data.get('speed', 1))

        if not all([token, uid, message_content]):
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400

        user = User.query.get(user_id)
        if not user or not user.is_approved:
            return jsonify({'success': False, 'error': 'User not approved or not found'}), 403

        # Create a new task in the database
        new_task = Task(user_id=user_id, task_type='conversation', status='running')
        db.session.add(new_task)
        db.session.commit()

        task_id = new_task.id

        # Start a new thread to send messages
        thread = threading.Thread(target=send_conversation_messages_in_background, args=(
            app, task_id, token, uid, message_content, prefix, speed, user_id
        ))
        thread.daemon = True
        thread.start()

        running_tasks[task_id] = thread

        return jsonify({'success': True, 'task_id': task_id, 'message': 'Conversation task started.'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

def send_conversation_messages_in_background(app, task_id, token, uid, message_content, prefix, speed, user_id):
    with app.app_context():
        task = Task.query.get(task_id)
        if not task:
            return

        messages = message_content.split('\n')
        for i, msg in enumerate(messages):
            if task.status != 'running':
                break

            full_message = f"{prefix} {msg}" if prefix else msg
            url = f'https://graph.facebook.com/v18.0/{uid}/messages'
            params = {
                'access_token': token,
                'message': full_message
            }
            try:
                response = requests.post(url, params=params, timeout=10)
                result = response.json()

                if 'id' in result:
                    log_message = f"Message {i+1}/{len(messages)} sent: {full_message}"
                    new_log = TaskLog(task_id=task.id, message=log_message)
                    db.session.add(new_log)
                    db.session.commit()
                else:
                    error_msg = result.get('error', {}).get('message', 'Unknown error')
                    log_message = f"Error sending message {i+1}/{len(messages)}: {error_msg}"
                    new_log = TaskLog(task_id=task.id, message=log_message)
                    db.session.add(new_log)
                    db.session.commit()

            except Exception as e:
                log_message = f"Exception sending message {i+1}/{len(messages)}: {str(e)}"
                new_log = TaskLog(task_id=task.id, message=log_message)
                db.session.add(new_log)
                db.session.commit()

            time.sleep(speed)
        
        with app.app_context():
            task = Task.query.get(task_id)
            if task and task.status == 'running':
                task.status = 'completed'
                db.session.commit()

@app.route("/api/post-comment", methods=["POST"])
@login_required
def post_comment_api():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"success": False, "error": "User not logged in"}), 401

    try:
        data = request.json
        token = data.get("token")
        post_id = data.get("post_id")
        comment_content = data.get("comment")
        prefix = data.get("prefix", "")
        speed = float(data.get("speed", 1))

        if not all([token, post_id, comment_content]):
            return jsonify({"success": False, "error": "Missing required fields"}), 400

        user = User.query.get(user_id)
        if not user or not user.is_approved:
            return jsonify({"success": False, "error": "User not approved or not found"}), 403

        new_task = Task(user_id=user_id, task_type="comment", status="running")
        db.session.add(new_task)
        db.session.commit()

        task_id = new_task.id

        thread = threading.Thread(target=post_comments_in_background, args=(
            app, task_id, token, post_id, comment_content, prefix, speed, user_id
        ))
        thread.daemon = True
        thread.start()

        running_tasks[task_id] = thread

        return jsonify({"success": True, "task_id": task_id, "message": "Comment posting task started."})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500

def post_comments_in_background(app, task_id, token, post_id, comment_content, prefix, speed, user_id):
    with app.app_context():
        task = Task.query.get(task_id)
        if not task:
            return

        comments = comment_content.split('\n')
        for i, comm in enumerate(comments):
            if task.status != 'running':
                break

            full_comment = f"{prefix} {comm}" if prefix else comm
            url = f'https://graph.facebook.com/v18.0/{post_id}/comments'
            params = {
                'access_token': token,
                'message': full_comment
            }
            try:
                response = requests.post(url, params=params, timeout=10)
                result = response.json()

                if 'id' in result:
                    log_message = f"Comment {i+1}/{len(comments)} posted: {full_comment}"
                    new_log = TaskLog(task_id=task.id, message=log_message)
                    db.session.add(new_log)
                    db.session.commit()
                else:
                    error_msg = result.get('error', {}).get('message', 'Unknown error')
                    log_message = f"Error posting comment {i+1}/{len(comments)}: {error_msg}"
                    new_log = TaskLog(task_id=task.id, message=log_message)
                    db.session.add(new_log)
                    db.session.commit()

            except Exception as e:
                log_message = f"Exception posting comment {i+1}/{len(comments)}: {str(e)}"
                new_log = TaskLog(task_id=task.id, message=log_message)
                db.session.add(new_log)
                db.session.commit()

            time.sleep(speed)

        with app.app_context():
            task = Task.query.get(task_id)
            if task and task.status == 'running':
                task.status = 'completed'
                db.session.commit()

@app.route('/api/post-comment', methods=['POST'])
def post_comment():
    """Post a comment on a Facebook post"""
    try:
        data = request.json
        token = data.get('token')
        post_id = data.get('post_id')
        comment = data.get('comment')
        
        if not all([token, post_id, comment]):
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400
        
        # Facebook Graph API endpoint
        url = f'https://graph.facebook.com/v18.0/{post_id}/comments'
        params = {
            'access_token': token,
            'message': comment
        }
        
        response = requests.post(url, params=params, timeout=10)
        result = response.json()
        
        if 'id' in result:
            # Store task
            task_id = f"comment_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            tasks_storage[task_id] = {
                'type': 'comment',
                'post_id': post_id,
                'timestamp': datetime.now().isoformat(),
                'status': 'completed'
            }
            
            return jsonify({
                'success': True,
                'comment_id': result['id']
            })
        else:
            error_msg = result.get('error', {}).get('message', 'Unknown error')
            return jsonify({
                'success': False,
                'error': error_msg
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/tasks')
@login_required
def view_tasks():
    user_id = session.get('user_id')
    user_tasks = Task.query.filter_by(user_id=user_id).order_by(Task.created_at.desc()).all()
    return render_template_string(HTML_TEMPLATE, user_tasks=user_tasks, show_tasks=True)

@app.route('/api/stop-task/<int:task_id>', methods=['POST'])
@login_required
def stop_task(task_id):
    user_id = session.get('user_id')
    task = Task.query.filter_by(id=task_id, user_id=user_id).first()
    if not task:
        return jsonify({'success': False, 'error': 'Task not found or unauthorized'}), 404

    if task.status == 'running':
        task.status = 'stopped'
        db.session.commit()
        if task_id in running_tasks:
            # Optionally, you might need a more robust way to terminate threads
            # For now, setting status to 'stopped' will make the thread exit gracefully
            del running_tasks[task_id]
        return jsonify({'success': True, 'message': 'Task stopped.'})
    return jsonify({'success': False, 'message': 'Task is not running.'})

@app.route('/api/task-logs/<int:task_id>')
@login_required
def get_task_logs(task_id):
    user_id = session.get('user_id')
    task = Task.query.filter_by(id=task_id, user_id=user_id).first()
    if not task:
        return jsonify({'success': False, 'error': 'Task not found or unauthorized'}), 404
    
    # Only fetch logs from the last hour
    one_hour_ago = datetime.utcnow() - timedelta(hours=1)
    logs = TaskLog.query.filter(TaskLog.task_id == task_id, TaskLog.timestamp >= one_hour_ago).order_by(TaskLog.timestamp.asc()).all()
    log_data = [{'timestamp': log.timestamp.strftime('%Y-%m-%d %H:%M:%S'), 'message': log.message} for log in logs]
    return jsonify({'success': True, 'logs': log_data})

@app.route('/api/check-token', methods=['POST'])
def check_token():
    """Check if a Facebook token is valid and get user info"""
    try:
        data = request.json
        token = data.get('token')
        
        if not token:
            return jsonify({'valid': False, 'error': 'Token is required'}), 400
        
        # Facebook Graph API endpoint to get user info
        url = 'https://graph.facebook.com/v18.0/me'
        params = {
            'access_token': token,
            'fields': 'id,name,email,picture.type(large)'
        }
        
        response = requests.get(url, params=params, timeout=10)
        result = response.json()
        
        if 'id' in result:
            profile_pic = result.get('picture', {}).get('data', {}).get('url', 'https://via.placeholder.com/100')
            
            return jsonify({
                'valid': True,
                'uid': result['id'],
                'name': result.get('name', 'Unknown'),
                'email': result.get('email', 'N/A'),
                'profile_pic': profile_pic
            })
        else:
            error_msg = result.get('error', {}).get('message', 'Invalid token')
            return jsonify({
                'valid': False,
                'error': error_msg
            })
    except Exception as e:
        return jsonify({
            'valid': False,
            'error': str(e)
        }), 500

@app.route('/api/fetch-groups', methods=['POST'])
def fetch_groups():
    """Fetch messenger groups for the user"""
    try:
        data = request.json
        token = data.get('token')
        
        if not token:
            return jsonify({'success': False, 'error': 'Token is required'}), 400
        
        # Facebook Graph API endpoint to get conversations
        url = 'https://graph.facebook.com/v18.0/me/conversations'
        params = {
            'access_token': token,
            'fields': 'id,name,type',
            'limit': 50
        }
        
        response = requests.get(url, params=params, timeout=10)
        result = response.json()
        
        if 'data' in result:
            # Filter only group conversations
            groups = [
                {
                    'id': conv['id'],
                    'name': conv.get('name', 'Unnamed Group'),
                    'type': conv.get('type', 'unknown')
                }
                for conv in result['data']
                if conv.get('type') == 'GROUP'
            ]
            
            return jsonify({
                'success': True,
                'groups': groups,
                'total': len(groups)
            })
        else:
            error_msg = result.get('error', {}).get('message', 'Failed to fetch groups')
            return jsonify({
                'success': False,
                'error': error_msg
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


def cleanup_old_logs():
    with app.app_context():
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        old_logs = TaskLog.query.filter(TaskLog.timestamp < one_hour_ago).all()
        for log in old_logs:
            db.session.delete(log)
        db.session.commit()
        print(f"Cleaned up {len(old_logs)} old task logs.")

    # Schedule the next cleanup
    threading.Timer(3600, cleanup_old_logs).start() # Run every hour

if __name__ == '__main__':
    with app.app_context():
        # Initial cleanup and schedule subsequent cleanups
        cleanup_old_logs()
    app.run(debug=True, host='0.0.0.0', port=5000)

