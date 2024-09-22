from flask import Flask, jsonify, request
import traceback
from flask_cors import CORS
from pymongo import MongoClient
from dotenv import load_dotenv
import google.generativeai as genai
from PIL import Image # type: ignore
import os
import re
import json
import io

load_dotenv()

app = Flask(__name__)
CORS(app)

client = MongoClient(os.getenv('MONGO_URI'))
db = client['dev']

# Configure Gemini API
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# test routes ---------------------
@app.route('/')
def home():
    return 'Hello, New World!'

@app.route('/about')
def about():
    return 'About'

@app.route('/env', methods=['GET'])
def env():
    return os.getenv('TEST_VAR')

@app.route('/test_get', methods=['GET'])
def test_get():
    users = db.users.find()
    userlist = list(users)
    for user in userlist:
        del user['_id']
    
    return jsonify(userlist)

# user authentication routes ---------------------


# clothing item routes ---


# outfit routes ---


# weather routes ---


# calendar routes ---


# gemini prompt and parse json response
def query_gemini(prompt):
    model = genai.GenerativeModel(model_name="models/gemini-1.5-flash")
    response = model.generate_content([prompt])

    if not response.candidates or not response.candidates[0].content.parts:
        return {"error": "Invalid response structure from API"}

    response_text = response.candidates[0].content.parts[0].text.strip()

    if not response_text:
        return {"error": "Empty response from API"}

    # Extract JSON from the response text
    json_pattern = r'```json\s*([\s\S]*?)\s*```'
    match = re.search(json_pattern, response_text)
    
    if match:
        json_content = match.group(1).strip()
        try:
            result = json.loads(json_content)
            return result
        except json.JSONDecodeError:
            return {"error": "Invalid JSON in response"}
    else:
        return {"error": "No JSON found in response"}

@app.route('/gemini', methods=['POST'])
def ask_gemini():
    prompt = request.json.get('prompt')

    try:
        result = query_gemini(prompt)
        return jsonify(result)
    except Exception as e:
        return {'error': str(e)}, 400

# when the user sends an image, generate tags for the clothing item
@app.route('/generate_tags', methods=['POST'])
def generate_tags():
    if 'image' not in request.files:
        return jsonify({"error": "No image file provided"}), 400
    
    image_file = request.files['image']
    
    try:
        # Open the image using PIL
        image = Image.open(io.BytesIO(image_file.read()))
        
        # Initialize Gemini model
        model = genai.GenerativeModel("gemini-1.5-flash")
        
        # Generate content
        response = model.generate_content([
            "Describe this clothing item in a single, detailed sentence. Include color, style, material, and any distinctive features.",
            image
        ])
        
        # Extract the description
        description = response.text.strip()
        
        return jsonify({"description": description})
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500



# error handling and error stack ---------------------

def error_stack(error):
    stack_trace = traceback.format_exc()
    response = {
        'error': error,
        'stack_trace': stack_trace
    }
    return jsonify(response), 500

@app.errorhandler(Exception)
def handle_exception(e):
    return error_stack(str(e))