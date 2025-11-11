from flask import Flask, request, render_template_string
import requests
import time
from typing import List, Dict, Any

app = Flask(__name__)

# --- Core Logic from the original script, adapted for web output ---

BASE_URL = "https://graph.facebook.com/v17.0/me/accounts"
FIELDS = "name,id,access_token"

def mask_token(t: str) -> str:
    """Masks the token for display."""
    if not t:
        return "<empty>"
    if len(t) <= 12:
        return t[0:3] + "..." + t[-3:]
    return t[:6] + "..." + t[-6:]

def fetch_pages(user_token: str) -> List[Dict[str, Any]]:
    """Fetches pages associated with the user token."""
    params = {"fields": FIELDS, "access_token": user_token}
    url = BASE_URL
    pages: List[Dict[str, Any]] = []
    while url:
        try:
            # Note: The original script's logic for handling 'next' URL params is slightly complex
            # We simplify the request for the initial call and subsequent 'next' URLs
            resp = requests.get(url, params=params if url == BASE_URL else None, timeout=15)
        except requests.RequestException:
            # In a web app, we'll handle errors in the main route function
            return pages

        if resp.status_code != 200:
            # Error handling will be done in the main route
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

    output_html += f"<p class='success'>✔ Found {len(pages)} page(s).</p>"
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

# --- HTML Template (Embedded) ---

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Facebook Pages Token Extractor</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f4f4f9;
            color: #333;
        }
        .container {
            max-width: 800px;
            margin: auto;
            background: #fff;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        }
        h1 {
            color: #3b5998;
            border-bottom: 2px solid #eee;
            padding-bottom: 10px;
        }
        form {
            background: #f9f9f9;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 20px;
            border: 1px solid #ddd;
        }
        input[type="text"] {
            width: 100%;
            padding: 10px;
            margin: 8px 0;
            display: inline-block;
            border: 1px solid #ccc;
            border-radius: 4px;
            box-sizing: border-box;
        }
        input[type="submit"] {
            background-color: #4CAF50;
            color: white;
            padding: 10px 15px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 16px;
        }
        input[type="submit"]:hover {
            background-color: #45a049;
        }
        .page-card {
            border: 1px solid #ccc;
            padding: 15px;
            margin-top: 10px;
            border-radius: 5px;
            background-color: #e9ebee;
        }
        .page-card h3 {
            color: #3b5998;
            margin-top: 0;
        }
        .token {
            background-color: #fff;
            padding: 2px 5px;
            border-radius: 3px;
            font-size: 0.9em;
            color: #d9534f; /* Red for tokens */
            word-break: break-all;
        }
        .error {
            color: #d9534f;
            font-weight: bold;
        }
        .success {
            color: #5cb85c;
            font-weight: bold;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Facebook Pages Token Extractor (Web Version)</h1>
        <p>Enter your Facebook User Access Token below to retrieve the list of pages and their corresponding Page Access Tokens.</p>
        
        <form method="POST">
            <label for="user_token"><strong>User Access Token:</strong></label>
            <input type="text" id="user_token" name="user_token" placeholder="Paste your long-lived user access token here" required>
            <input type="submit" value="Fetch Pages">
        </form>
        
        {% if results_html %}
            <hr>
            <h2>Extraction Results</h2>
            {{ results_html | safe }}
        {% endif %}
    </div>
</body>
</html>
"""

# --- Flask Routes ---

@app.route("/", methods=["GET", "POST"])
def index():
    results_html = None
    if request.method == "POST":
        user_token = request.form.get("user_token", "").strip()
        results_html = process_token_for_web(user_token)
        
    return render_template_string(HTML_TEMPLATE, results_html=results_html)

if __name__ == "__main__":
    # Note: In a real-world scenario, you should not run with debug=True in production.
    # We use it here for simplicity in the sandbox environment.
    app.run(host="0.0.0.0", port=5000, debug=True)
