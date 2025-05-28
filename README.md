# Facebook EAAB Token Extractor

This is a Flask web application that extracts a working EAAB access token from a valid Facebook cookie.

## How to Deploy on Render

1. Upload this project to a GitHub repo.
2. Go to [Render.com](https://render.com) and create a new Web Service.
3. Connect your GitHub repo.
4. Set Build Command: `pip install -r requirements.txt`
5. Set Start Command: `python app.py`
6. Deploy the service and visit your URL to use the app.

## How to Use

- Paste a valid Facebook cookie in the textarea.
- Click "Extract Token".
- Your EAAB token will be shown if the cookie is valid.
