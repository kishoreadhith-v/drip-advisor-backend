import datetime
import hashlib
from flask import Flask, jsonify, request
import traceback
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token, get_jwt_identity
from pymongo import MongoClient
from dotenv import load_dotenv
import google.generativeai as genai
from PIL import Image # type: ignore
import os
import re
import json
import io
from google.oauth2 import service_account
from googleapiclient.discovery import build

load_dotenv()

app = Flask(__name__)
CORS(app)
jwt = JWTManager(app)

# JWT Configuration
app.config['JWT_SECRET_KEY'] = "Raju bhai"
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = datetime.timedelta(days=1)


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
# user signup route
@app.route('/users/signup', methods=['POST'])
def signup():
    try:
        new_user = {
            'email': request.json.get('email'),
            'password': request.json.get('password'),
            'name': request.json.get('name'),
            'gender': request.json.get('gender'),
            'dob': request.json.get('dob'),
            'preferences': [],
        }
        new_user['password'] = hashlib.sha256(new_user['password'].encode("utf-8")).hexdigest()
        existing_user = db.users.find_one({'email': new_user['email']})
        if existing_user:
            return jsonify({'error': 'User with email already exists'}), 400
        result = db.users.insert_one(new_user)
        return jsonify({'message': 'User created successfully', 'id': str(result.inserted_id)})
    except Exception as e:
        return error_stack(str(e))
    
# user login route
@app.route('/users/login', methods=['POST'])
def login():
    try:
        email = request.json.get('email')
        password = request.json.get('password')
        password = hashlib.sha256(password.encode("utf-8")).hexdigest()
        user = db.users.find_one({'email': email, 'password': password})
        if user:
            access_token = create_access_token(identity=email)
            return jsonify({'access_token': access_token})
        else:
            return jsonify({'error': 'Invalid credentials'}), 400
    except Exception as e:
        return error_stack(str(e))

# get user profile
@app.route('/users/profile', methods=['GET'])
def profile():
    email = email = get_jwt_identity()
    user = db.users.find_one({'email': email})
    if user:
        user['_id'] = str(user['_id'])  
        return jsonify(user)
    else:
        return jsonify({'error': 'User not found'}), 404

# update user profile
@app.route('/users/profile', methods=['PUT'])
def update_profile():
    email = email = get_jwt_identity()
    user = db.users.find_one({'email': email})
    if not user:
        return jsonify({'error': 'User not found'}), 404
    try:
        update = {
            'name': request.json.get('name'),
            'gender': request.json.get('gender'),
            'dob': request.json.get('dob'),
        }
        db.users.update_one({'email': email}, {'$set': update})
        return jsonify({'message': 'Profile updated successfully'})
    except Exception as e:
        return error_stack(str(e))
    
# delete user profile
@app.route('/users/profile', methods=['DELETE'])
def delete_profile():
    email = get_jwt_identity()
    user = db.users.find_one({'email': email})
    if not user:
        return jsonify({'error': 'User not found'}), 404
    try:
        db.users.delete_one({'email': email})
        return jsonify({'message': 'Profile deleted successfully'})
    except Exception as e:
        return error_stack(str(e))
    
# add user preferences
@app.route('/users/preferences', methods=['POST'])
def add_preferences():
    email = get_jwt_identity()
    user = db.users.find_one({'email': email})
    if not user:
        return jsonify({'error': 'User not found'}), 404
    try:
        preferences = request.json.get('preferences')
        # add date and time to the preference as a string at the end of each
        preferences = [preference + ' on ' + str(datetime.datetime.now()) for preference in preferences]
        db.users.update_one({'email': email}, {'$push': {'preferences': {'$each': preferences}}})
        return jsonify({'message': 'Preferences added successfully'})
    except Exception as e:
        return error_stack(str(e))


# clothing item routes ---
@app.route('/add_clothing_item', methods=['POST'])
def add_clothing_item():
    email = get_jwt_identity()
    user = db.users.find_one({'email': email})
    if not user:
        return jsonify({'error': 'User must be logged in, please log in to use this api'}), 404
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

        # Create a new clothing item document
        new_clothing_item = {
            'user_id': user['_id'],
            'description': description,
            'image': image_file.filename,
            'created_at': datetime.datetime.now(),
            'frequency': 0,
            'available': True
        }

        # Insert the new clothing item into the database
        result = db.clothing_items.insert_one(new_clothing_item)

        return jsonify({'message': 'Clothing item added successfully', 'id': str(result.inserted_id)})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/search_clothing', methods=['POST'])
def search_clothing():
    description = request.json.get('description')
    if not description:
        return jsonify({"error": "Description is required"}), 400

    try:
        # Fetch all clothing items from the database
        clothing_items = list(db.clothing_items.find())
        if not clothing_items:
            return jsonify({"error": "No clothing items found"}), 404

        # Extract descriptions
        descriptions = [item['description'] for item in clothing_items]

        # Use TF-IDF Vectorizer to convert descriptions to vectors
        vectorizer = TfidfVectorizer().fit_transform(descriptions + [description])
        vectors = vectorizer.toarray()

        # Calculate cosine similarity between the input description and all clothing item descriptions
        cosine_similarities = cosine_similarity([vectors[-1]], vectors[:-1]).flatten()

        # Get the indices of the most similar descriptions
        similar_indices = cosine_similarities.argsort()[-5:][::-1]

        # Get the corresponding clothing items
        similar_clothing_items = [clothing_items[i] for i in similar_indices]

        # Return the IDs of the most similar clothing items
        result = [{'id': str(item['_id']), 'description': item['description']} for item in similar_clothing_items]

        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    

# outfit routes ---


# weather routes ---
@app.route('/weather', methods=['GET'])
def get_weather():
    location = request.args.get('location')
    if not location:
        return jsonify({'error': 'Location parameter is required'}), 400

    weather_api_key = os.getenv('WEATHER_API_KEY')
    weather_url = f'http://api.openweathermap.org/data/2.5/weather?q={location}&appid={weather_api_key}&units=metric'

    try:
        response = requests.get(weather_url)
        response.raise_for_status()
        weather_data = response.json()

        temperature = weather_data['main']['temp']
        weather_description = weather_data['weather'][0]['description']

        outfit_recommendation = get_outfit_recommendation(temperature, weather_description)

        return jsonify({
            'location': location,
            'temperature': temperature,
            'weather_description': weather_description,
            'outfit_recommendation': outfit_recommendation
        })
    except requests.exceptions.RequestException as e:
        return jsonify({'error': str(e)}), 500

def get_outfit_recommendation(temperature, weather_description):
    if temperature < 10:
        return 'Wear a heavy coat, scarf, and gloves.'
    elif 10 <= temperature < 20:
        return 'Wear a light jacket or sweater.'
    elif 20 <= temperature < 30:
        return 'Wear a t-shirt and jeans.'
    else:
        return 'Wear shorts and a tank top.'

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