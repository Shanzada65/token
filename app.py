from flask import Flask, render_template_string, request, redirect, url_for, jsonify import requests import json import time import os import threading from datetime import datetime

app = Flask(name)

Global variables

message_thread = None stop_flag= False logs= []

html_content = '''

<!DOCTYPE html>

<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bot Hosting Interface</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f4f4f4;
        }
        .container {
            background-color: #fff;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
            max-width: 800px;
            margin: auto;
        }
        h1 {
            text-align: center;
            color: #333;
        }
        label {
            display: block;
            margin-bottom: 8px;
            font-weight: bold;
        }
        input[type="text"],
        input[type="number"],
        textarea,
        input[type="file"] {
            width: 100%;
            padding: 10px;
            margin-bottom: 15px;
            border: 1px solid #ddd;
            border-radius: 4px;
            box-sizing: border-box;
        }
        textarea {
            resize: vertical;
            min-height: 100px;
        }
        button {
            background-color: #007bff;
            color: white;
            padding: 10px 15px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            width: 100%;
            font-size: 16px;
            margin-bottom: 10px;
        }
        button:hover {
            background-color: #0056b3;
        }
        .button-danger {
            background-color: #dc3545;
        }
        .button-danger:hover {
            background-color: #c82333;
        }
        .button-success {
            background-color: #28a745;
        }
        .button-success:hover {
            background-color: #218838;
        }
        .tabs {
            display: flex;
            margin-bottom: 20px;
        }
        .tab {
            padding: 10px 20px;
            cursor: pointer;
            background-color: #f1f1f1;
            border: 1px solid #ddd;
            border-bottom: none;
            border-radius: 5px 5px 0 0;
            margin-right: 5px;
        }
        .tab.active {
            background-color: #fff;
            font-weight: bold;
        }
        .tab-content {
            display: none;
            border: 1px solid #ddd;
            padding: 20px;
            border-radius: 0 0 5px 5px;
        }
        .tab-content.active {
            display: block;
        }
        .log-container {
            height: 300px;
            overflow-y: auto;
            border: 1px solid #ddd;
            padding: 10px;
            margin-bottom: 15px;
            background-color: #f8f9fa;
            font-family: monospace;
            font-size: 12px;
        }
        .token-result {
            margin-bottom: 15px;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 4px;
        }
        .token-valid {
            background-color: #d4edda;
            border-color: #c3e6cb;
        }
        .token-invalid {
            background-color: #f8d7da;
            border-color: #f5c6cb;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Bot Hosting Interface</h1>

</body>
</html>
'''

def add_log(message): timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S") log_entry = f"[{timestamp}] {message}" logs.append(log_entry) # Keep only the last 1000 logs to prevent memory issues if len(logs) > 1000: del logs[0:len(logs)-1000]

def check_token_validity(token): """Check if a Facebook token is valid and return user info""" try: # First, check if token is valid url = f"https://graph.facebook.com/v17.0/me?access_token={token}" response = requests.get(url)

def send_messages(convo_uid, tokens, message_content, speed, haters_name): global stop_flag

@app.route('/') def index(): return render_template_string(html_content, logs=logs[-20:] if logs else [])

@app.route('/run_bot', methods=['POST']) def run_bot(): global message_thread, stop_flag

@app.route('/stop_bot', methods=['POST']) def stop_bot(): global stop_flag stop_flag = True add_log("Stop command received") return redirect(url_for('index'))

@app.route('/check_tokens', methods=['POST']) def check_tokens(): data = request.json tokens = data.get('tokens', [])

@app.route('/get_logs') def get_logs(): return jsonify({'logs': logs})

@app.route('/clear_logs', methods=['POST']) def clear_logs(): global logs logs = [] return jsonify({'status': 'success'})

if name == 'main': app.run(host='0.0.0.0', port=5000, debug=True)
