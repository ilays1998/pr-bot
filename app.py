from flask import Flask, request, render_template_string, redirect
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import json
import tempfile

app = Flask(__name__)

# --- GOOGLE SHEETS SETUP ---
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
google_creds_json = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON")
if google_creds_json:
    with tempfile.NamedTemporaryFile(delete=False, mode='w', suffix='.json') as temp_json:
        temp_json.write(google_creds_json)
        temp_json.flush()
        creds = ServiceAccountCredentials.from_json_keyfile_name(temp_json.name, scope)
        client = gspread.authorize(creds)
        sheet = client.open("Code Review Feedback").sheet1
else:
    raise Exception("Google credentials not found in environment variables.")

# --- FEEDBACK FORM PAGE ---
FEEDBACK_FORM_HTML = '''
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Code Review Feedback</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
</head>
<body>
  <h2>Code Review Feedback</h2>
  <form method="post">
    <label>Rating (1 - Poor, 5 - Excellent):</label><br>
    <input type="number" name="rating" min="1" max="5" required><br><br>

    <label>Your feedback or suggestions:</label><br>
    <textarea name="feedback" rows="4" cols="50"></textarea><br><br>

    <input type="hidden" name="pr_url" value="{{ pr_url }}">
    <input type="hidden" name="reviewer" value="{{ reviewer }}">

    <input type="submit" value="Submit Feedback">
  </form>
</body>
</html>
'''

# --- THANK YOU PAGE ---
THANK_YOU_HTML = '''
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Thank You!</title>
</head>
<body>
  <h2>Thank you for your feedback!</h2>
</body>
</html>
'''

# --- ROUTE TO DISPLAY FORM ---
@app.route("/feedback", methods=["GET", "POST"])
def feedback():
    if request.method == "POST":
        rating = request.form.get("rating")
        feedback_text = request.form.get("feedback")
        pr_url = request.form.get("pr_url")
        reviewer = request.form.get("reviewer")

        # Store in Google Sheets
        sheet.append_row([pr_url, reviewer, rating, feedback_text])

        return render_template_string(THANK_YOU_HTML)

    else:
        pr_url = request.args.get("pr_url", "")
        reviewer = request.args.get("reviewer", "")
        return render_template_string(FEEDBACK_FORM_HTML, pr_url=pr_url, reviewer=reviewer)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
