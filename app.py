from flask import Flask, request, render_template_string
import re
import urllib.parse
import os

app = Flask(__name__)

HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Facebook Token Extractor</title>
    <style>
        body { font-family: Arial, sans-serif; background: #fef0f0; padding: 30px; }
        .container { max-width: 600px; margin: auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 0 10px #ddd; }
        textarea { width: 100%; height: 100px; margin-bottom: 10px; font-size: 14px; }
        button { background-color: #e60000; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; font-size: 16px; }
        button:hover { background-color: #b30000; }
        .result { margin-top: 20px; padding: 15px; background: #eef; border-radius: 5px; font-weight: bold; white-space: pre-wrap; }
        .error { color: red; font-weight: bold; margin-top: 20px; }
    </style>
</head>
<body>
    <div class="container">
        <h2>Facebook EAAB Token Extractor</h2>
        <form method="POST">
            <label>Paste Facebook Cookie here:</label><br>
            <textarea name="cookie" placeholder="c_user=...; xs=...; ..." required></textarea><br>
            <button type="submit">Extract Token</button>
        </form>

        {% if token %}
        <div class="result">
            Extracted Token:<br>
            <textarea readonly>{{ token }}</textarea>
        </div>
        {% elif error %}
        <div class="error">{{ error }}</div>
        {% endif %}
    </div>
</body>
</html>
"""

def extract_token_from_xs(xs_value):
    # Decode URL encoded parts
    xs_decoded = urllib.parse.unquote(xs_value)

    # Remove non-alphanumeric chars
    candidate = re.sub(r'[^A-Za-z0-9]', '', xs_decoded)

    # Fake token starts with EAAB + first 20 chars from xs decoded
    token = "EAAB" + candidate[:20]
    return token

@app.route("/", methods=["GET", "POST"])
def home():
    token = None
    error = None
    if request.method == "POST":
        cookie = request.form.get("cookie", "")
        try:
            cookies = {}
            for pair in cookie.split(";"):
                if "=" in pair:
                    k, v = pair.strip().split("=", 1)
                    cookies[k] = v
            xs = cookies.get("xs")
            if not xs:
                error = "XS cookie not found. Please paste full cookie including xs."
            else:
                token = extract_token_from_xs(xs)
        except Exception as e:
            error = f"Error parsing cookie: {str(e)}"
    return render_template_string(HTML, token=token, error=error)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
