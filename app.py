import os
import requests
from flask import Flask, request, render_template_string, redirect, url_for
from typing import List, Dict, Any

app = Flask(__name__)
# A secret key is required for session management, even if not explicitly used for sessions
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'a_very_secret_key_for_dev')

# --- Facebook Graph API Configuration ---
GRAPH_API_VERSION = "v17.0"
BASE_URL = f"https://graph.facebook.com/{GRAPH_API_VERSION}"
PAGES_ENDPOINT = "/me/accounts"
# Fields requested: name, id (UID), access_token (page token), and picture (profile picture)
FIELDS = "name,id,access_token,picture.type(large)"

# --- HTML Templates ---
# Simple form to input the user access token
FORM_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Facebook Page Token Extractor</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background-color: #f4f4f9; color: #333; }
        .container { max-width: 800px; margin: auto; background: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        h1 { color: #4267B2; border-bottom: 2px solid #4267B2; padding-bottom: 10px; }
        form { display: flex; flex-direction: column; }
        label { margin-top: 10px; font-weight: bold; }
        textarea { padding: 10px; margin-top: 5px; border: 1px solid #ccc; border-radius: 4px; resize: vertical; }
        button { background-color: #4267B2; color: white; padding: 10px 15px; border: none; border-radius: 4px; cursor: pointer; margin-top: 20px; font-size: 16px; }
        button:hover { background-color: #365899; }
        .error { color: red; font-weight: bold; margin-top: 10px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Facebook Page Token Extractor</h1>
        <p>Enter your Facebook User Access Token below to retrieve a list of pages you manage, along with their Page Access Tokens, UIDs, Names, and Profile Pictures.</p>
        {% if error %}
            <p class="error">{{ error }}</p>
        {% endif %}
        <form method="POST" action="{{ url_for('get_pages') }}">
            <label for="user_token">User Access Token:</label>
            <textarea id="user_token" name="user_token" rows="5" required></textarea>
            <button type="submit">Get Page Tokens</button>
        </form>
        <p style="margin-top: 30px; font-size: 0.9em; color: #666;">
            <strong>Note:</strong> The User Access Token must have the <code>manage_pages</code> or <code>pages_show_list</code> permission, and the <code>pages_read_engagement</code> or <code>pages_manage_posts</code> permission to retrieve the Page Access Token.
        </p>
    </div>
</body>
</html>
"""

# Template to display the results
RESULTS_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Page Tokens Result</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background-color: #f4f4f9; color: #333; }
        .container { max-width: 1000px; margin: auto; background: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        h1 { color: #4267B2; border-bottom: 2px solid #4267B2; padding-bottom: 10px; }
        .page-card { border: 1px solid #ddd; padding: 15px; margin-bottom: 15px; border-radius: 6px; display: flex; align-items: center; background-color: #fff; }
        .page-card img { width: 80px; height: 80px; border-radius: 50%; margin-right: 20px; object-fit: cover; border: 3px solid #4267B2; }
        .page-info { flex-grow: 1; }
        .page-info h2 { margin: 0 0 5px 0; color: #333; }
        .page-info p { margin: 5px 0; font-size: 0.9em; word-break: break-all; }
        .token-box { background-color: #eee; padding: 8px; border-radius: 4px; font-family: monospace; font-size: 0.85em; color: #000; }
        .back-link { display: block; margin-top: 20px; color: #4267B2; text-decoration: none; font-weight: bold; }
        .back-link:hover { text-decoration: underline; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Page Tokens Result ({{ pages|length }} Pages Found)</h1>
        <a href="{{ url_for('index') }}" class="back-link">← Go Back</a>
        {% for page in pages %}
            <div class="page-card">
                <img src="{{ page.picture_url }}" alt="{{ page.name }} Profile Picture">
                <div class="page-info">
                    <h2>{{ page.name }}</h2>
                    <p><strong>UID:</strong> {{ page.id }}</p>
                    <p><strong>Page Access Token:</strong></p>
                    <div class="token-box">{{ page.access_token }}</div>
                </div>
            </div>
        {% endfor %}
        {% if not pages %}
            <p>No pages found or the token is invalid/expired. Please check your token and its permissions.</p>
        {% endif %}
        <a href="{{ url_for('index') }}" class="back-link">← Go Back</a>
    </div>
</body>
</html>
"""

def fetch_pages_data(user_token: str) -> tuple[List[Dict[str, Any]], str | None]:
    """
    Fetches page data (name, id, access_token, picture) from the Facebook Graph API.
    """
    params = {"fields": FIELDS, "access_token": user_token}
    url = BASE_URL + PAGES_ENDPOINT
    pages: List[Dict[str, Any]] = []

    while url:
        try:
            # Use params only for the first request, as the 'next' URL is complete
            current_params = params if url.endswith(PAGES_ENDPOINT) else None
            resp = requests.get(url, params=current_params, timeout=15)
            resp.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)
        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Network/request error: {e}")
            return [], f"Network or API error: {e}"

        try:
            data = resp.json()
        except ValueError:
            print(f"[ERROR] Failed to parse JSON response: {resp.text}")
            return [], "Failed to parse API response. Invalid token or server error."

        if "error" in data:
            error_msg = data["error"].get("message", "Unknown API Error")
            print(f"[ERROR] Facebook API Error: {error_msg}")
            return [], f"Facebook API Error: {error_msg}"

        if "data" in data:
            for page in data["data"]:
                # Extract the profile picture URL
                picture_url = page.get("picture", {}).get("data", {}).get("url", "https://via.placeholder.com/80?text=No+Pic")
                
                pages.append({
                    "name": page.get("name", "N/A"),
                    "id": page.get("id", "N/A"),
                    "access_token": page.get("access_token", "N/A"),
                    "picture_url": picture_url
                })
        
        paging = data.get("paging", {})
        url = paging.get("next")
        
        # Clear params for subsequent paged requests as the 'next' URL is complete
        if url:
            params = None # Ensure params is None for subsequent requests if 'next' URL is present
        
    return pages, None

@app.route('/', methods=['GET'])
def index():
    """
    Displays the token input form.
    """
    return render_template_string(FORM_TEMPLATE, error=request.args.get('error'))

@app.route('/get_pages', methods=['POST'])
def get_pages():
    """
    Processes the token, fetches page data, and displays results.
    """
    user_token = request.form.get('user_token', '').strip()
    
    if not user_token:
        return redirect(url_for('index', error="Please provide a User Access Token."))

    pages, error = fetch_pages_data(user_token)
    
    if error:
        return redirect(url_for('index', error=error))
        
    return render_template_string(RESULTS_TEMPLATE, pages=pages)

if __name__ == '__main__':
    # The Flask app requires 'Flask' and 'requests' libraries.
    # On most bot hosting services, you will need to ensure these are installed
    # (e.g., by having a requirements.txt file with 'Flask' and 'requests' and running 'pip install -r requirements.txt').
    # The app will run on port 5000 by default, or the port specified by the hosting environment's PORT environment variable.
    print("Starting Flask application...")
    app.run(host='0.0.0.0', port=os.environ.get('PORT', 5000))
