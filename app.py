from flask import Flask, request, render_template_string
import requests
import re
import os

app = Flask(__name__)

HTML = """
<!DOCTYPE html>
<html>
<head><title>Facebook Token Extractor</title></head>
<body style="background-color:#121212; color:white; font-family:sans-serif; text-align:center;">
    <h2>Paste Your Facebook Cookie</h2>
    <form method="POST">
        <textarea name="cookie" rows="6" cols="100" required style="margin-bottom:10px;"></textarea><br>
        <input type="submit" value="Extract Token" style="padding:10px 20px; font-size:16px;">
    </form>
    {% if token %}
        <h3>Extracted Token:</h3>
        <textarea rows="4" cols="100">{{ token }}</textarea>
    {% elif error %}
        <p style="color:red;">{{ error }}</p>
    {% endif %}
</body>
</html>
"""

@app.route('/', methods=['GET', 'POST'])
def index():
    token = None
    error = None
    if request.method == 'POST':
        cookie = request.form['cookie']
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept": "text/html",
            "Cookie": cookie,
        }
        try:
            response = requests.get(
                "https://business.facebook.com/business_locations",
                headers=headers
            )
            match = re.search(r'"EAAB\w+"', response.text)
            if match:
                token = match.group(0).strip('"')
            else:
                error = "Token not found. Make sure cookie is valid and contains 'c_user' and 'xs'."
        except Exception as e:
            error = f"Error: {str(e)}"

    return render_template_string(HTML, token=token, error=error)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
