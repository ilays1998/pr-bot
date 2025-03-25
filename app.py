from flask import Flask, request, render_template_string
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import json
import tempfile
from openai import OpenAI

app = Flask(__name__)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

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
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap" rel="stylesheet">
  <style>
    body {
      font-family: 'Inter', sans-serif;
      background: linear-gradient(135deg, #fdfbfb 0%, #ebedee 100%);
      display: flex;
      justify-content: center;
      align-items: center;
      height: 100vh;
      margin: 0;
    }
    .form-container {
      background: white;
      padding: 2rem;
      border-radius: 16px;
      box-shadow: 0 10px 25px rgba(0, 0, 0, 0.05);
      width: 100%;
      max-width: 400px;
    }
    h2 {
      text-align: center;
      color: #4f46e5;
      margin-bottom: 1.5rem;
    }
    label {
      font-weight: 600;
      display: block;
      margin-bottom: 0.5rem;
      color: #333;
    }
    input[type="number"],
    textarea {
      width: 100%;
      padding: 0.75rem;
      border: 1px solid #ddd;
      border-radius: 10px;
      margin-bottom: 1.5rem;
      transition: border 0.2s;
      box-sizing: border-box;
      font-size: 1rem;
    }
    input[type="number"]:focus,
    textarea:focus {
      border-color: #4f46e5;
      outline: none;
    }
    input[type="submit"] {
      width: 100%;
      padding: 0.8rem;
      border: none;
      border-radius: 10px;
      background-color: #4f46e5;
      color: white;
      font-weight: 600;
      font-size: 1rem;
      cursor: pointer;
      transition: background-color 0.2s, transform 0.1s;
    }
    input[type="submit"]:hover {
      background-color: #4338ca;
    }
    input[type="submit"]:active {
      transform: scale(0.97);
    }
  </style>
</head>
<body>
  <div class="form-container">
    <h2>Code Review Feedback</h2>
    <form method="post">
      <label>Rating (1 - Poor, 5 - Excellent):</label>
      <input type="number" name="rating" min="1" max="5" required>

      <label>Your feedback or suggestions:</label>
      <textarea name="feedback" rows="4" placeholder="Write your thoughts..."></textarea>

      <input type="hidden" name="pr_url" value="{{ pr_url }}">
      <input type="hidden" name="reviewer" value="{{ reviewer }}">

      <input type="submit" value="Submit Feedback">
    </form>
  </div>
</body>
</html>
'''

# --- FUNCTION TO GENERATE SUMMARY AND DALLE PROMPT ---

def get_gpt_summary_and_prompt(feedback_text):
    response = client.chat.completions.create(
        model="gpt-4-1106-preview",
        messages=[
            {"role": "system", "content": "You are a helpful assistant that summarizes feedback and generates a creative visual prompt for DALL·E."},
            {"role": "user", "content": f"Summarize this feedback in one sentence and generate a DALL·E prompt that visually represents it: '{feedback_text}'"}
        ]
    )
    result = response.choices[0].message.content
    lines = result.split("\\n")
    summary = lines[0].replace("Summary:", "").strip()
    dalle_prompt = lines[1].replace("DALL·E Prompt:", "").strip()
    return summary, dalle_prompt

# --- FUNCTION TO GENERATE DALL·E IMAGE ---
def generate_dalle_image(prompt):
    image_response = client.images.generate(
        model="dall-e-3",
        prompt=prompt,
        size="1024x1024",
        n=1
    )
    image_url = image_response.data[0].url
    return image_url

# --- THANK YOU TEMPLATE WITH IMAGE ---
THANK_YOU_WITH_IMAGE_HTML = '''
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Thank You!</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap" rel="stylesheet">
  <style>
    body {
      font-family: 'Inter', sans-serif;
      background: linear-gradient(135deg, #fdfbfb 0%, #ebedee 100%);
      display: flex;
      justify-content: center;
      align-items: center;
      height: 100vh;
      margin: 0;
    }
    .thankyou-container {
      background: white;
      padding: 2rem;
      border-radius: 16px;
      box-shadow: 0 10px 25px rgba(0, 0, 0, 0.05);
      width: 100%;
      max-width: 500px;
      text-align: center;
    }
    h2 { color: #4f46e5; margin-bottom: 1rem; }
    p { color: #333; margin-bottom: 1rem; }
    img { border-radius: 12px; margin-top: 1rem; max-width: 100%; }
  </style>
</head>
<body>
  <div class="thankyou-container">
    <h2>Thank you for your feedback!</h2>
    <p><strong>Summary:</strong> {{ summary }}</p>
    <p><strong>Your Feedback:</strong> {{ feedback }}</p>
    <img src="{{ image_url }}" alt="Generated image based on feedback">
  </div>
</body>
</html>
'''

# --- ROUTE TO HANDLE FEEDBACK ---
@app.route("/feedback", methods=["GET", "POST"])
def feedback():
    if request.method == "POST":
        rating = request.form.get("rating")
        feedback_text = request.form.get("feedback")
        pr_url = request.form.get("pr_url")
        reviewer = request.form.get("reviewer")

        summary, dalle_prompt = get_gpt_summary_and_prompt(feedback_text)
        image_url = generate_dalle_image(dalle_prompt)

        # Store all data
        sheet.append_row([pr_url, reviewer, rating, feedback_text, summary, dalle_prompt, image_url])

        return render_template_string(THANK_YOU_WITH_IMAGE_HTML, summary=summary, feedback=feedback_text, image_url=image_url)
    else:
        pr_url = request.args.get("pr_url", "")
        reviewer = request.args.get("reviewer", "")
        return render_template_string(FEEDBACK_FORM_HTML, pr_url=pr_url, reviewer=reviewer)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
