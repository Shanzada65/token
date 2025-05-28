from flask import Flask, request, render_template_string
import requests

app = Flask(__name__)

HTML = '''
<!doctype html>
<title>Facebook EAAB Token Extractor</title>
<h2>Facebook Cookie Se Full Token Nikaalein</h2>
<form method="POST">
  <textarea name="cookie" rows="6" cols="80" placeholder="Apni full Facebook cookie yahan paste karein..."></textarea><br><br>
  <input type="submit" value="Token Nikalein">
</form>

{% if token %}
  <h3>🎉 Extracted Token:</h3>
  <textarea rows="2" cols="80">{{ token }}</textarea>
{% elif error %}
  <p style="color:red;"><b>{{ error }}</b></p>
{% endif %}
'''

@app.route('/', methods=['GET', 'POST'])
def extract():
    token = None
    error = None

    if request.method == 'POST':
        cookie = request.form['cookie']

        headers = {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 11; Mobile)',
            'Accept': '*/*',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Cookie': cookie,
        }

        try:
            r = requests.get("https://m.facebook.com/composer/ocelot/async_loader/?publisher=feed", headers=headers)
            if 'accessToken' in r.text:
                token = r.text.split('accessToken\\":\\"')[1].split('\\"')[0]
            else:
                error = "❌ Token not found. Make sure cookie is valid and account is not checkpointed."
        except Exception as e:
            error = f"⚠️ Error: {str(e)}"

    return render_template_string(HTML, token=token, error=error)

if __name__ == '__main__':
    app.run(debug=True)
