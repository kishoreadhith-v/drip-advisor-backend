import datetime
import hashlib
from flask import Flask, jsonify, request
import traceback
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token, get_jwt_identity, jwt_required
from pymongo import MongoClient
from dotenv import load_dotenv
import google.generativeai as genai
from PIL import Image
import os
import re
import json
import io
from google.oauth2 import service_account
from googleapiclient.discovery import build
from apscheduler.schedulers.background import BackgroundScheduler
import requests
from bson import ObjectId

# from sklearn.feature_extraction.text import TfidfVectorizer
# from sklearn.metrics.pairwise import cosine_similarity

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
@jwt_required()
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
@jwt_required()
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
@jwt_required()
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
@jwt_required()
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
@jwt_required()
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

# Helper function to recursively convert ObjectId fields to strings
def convert_objectid(data):
    if isinstance(data, list):
        return [convert_objectid(item) for item in data]
    elif isinstance(data, dict):
        return {key: convert_objectid(value) for key, value in data.items()}
    elif isinstance(data, ObjectId):
        return str(data)
    else:
        return data

@app.route('/outfits/generate/<location>', methods=['GET'])
@jwt_required()
def generate_outfit(location):
    email = get_jwt_identity()
    user = db.users.find_one({'email': email})
    
    if not user:
        return jsonify({'error': 'User must be logged in, please log in to use this api'}), 404
    
    # Fetch all available clothing items for the user
    clothing_items = list(db.clothing_items.find({'user_id': user['_id'], 'available': True}))
    
    if not clothing_items:
        return jsonify({'error': 'No clothing items found for user'}), 404
    
    # Sort clothing items by frequency (ascending)
    clothing_items.sort(key=lambda x: x['frequency'])
    
    # Extract id, description, and frequency fields for each clothing item
    clothing_items = [{'id': str(item['_id']), 'description': item['description'], 'frequency': item['frequency']} for item in clothing_items]
    
    # Ensure location is provided
    if not location:
        return jsonify({'error': 'Location is required'}), 400
    
    weather_api_key = os.getenv('OPENWEATHERMAP_API_KEY')
    weather_url = f"http://api.openweathermap.org/data/2.5/weather?q={location}&appid={weather_api_key}&units=metric"
    
    try:
        weather_response = requests.get(weather_url)
        weather_data = weather_response.json()
        print(weather_data)
        
        if weather_response.status_code != 200:
            return jsonify({'error': 'Failed to get weather data'}), 500
        
        weather_description = weather_data['weather'][0]['description']
        temperature = weather_data['main']['temp']
        
    except Exception as e:
        return jsonify({'error': f'Weather API error: {str(e)}'}), 500
    
    # Use Gemini to generate outfit recommendations
    try:
        model = genai.GenerativeModel("models/gemini-1.5-flash")
        prompt = (
            "You are a fashion expert. Generate an outfit recommendation based on the following clothing items. "
            "Read the description of each item and generate 3 different outfits from them. Make sure to keep in mind "
            "the color combinations, the style of the clothing items, and the current weather conditions. "
            "The weather is described as follows: {weather_description} with a temperature of {temperature}°C. "
            "The output should contain a JSON array, with each object having one outfit. Each outfit object should have "
            "a name, description, list of ids of clothing items in the outfits, and additional styling tips. \n\n"
            + str(clothing_items)
        ).format(weather_description=weather_description, temperature=temperature)
        
        outfit_description = query_gemini(prompt)
        
        # Validate that outfit_description is a list and contains valid items
        if not isinstance(outfit_description, list) or not all('id' in outfit for outfit in outfit_description):
            return jsonify({'error': 'Invalid outfit data returned from Gemini'}), 500
        
        # Save each generated outfit to the database
        for outfit in outfit_description:
            outfit['user_id'] = user['_id']
            outfit['created_at'] = datetime.datetime.now()
            db.outfits.insert_one(outfit)
        
        # Fetch the latest 3 outfits for the user
        outfits = list(db.outfits.find({'user_id': user['_id']}).sort('created_at', -1).limit(3))
        
        # Convert ObjectId fields to strings
        outfits = convert_objectid(outfits)
        
        return jsonify(outfits)
    
    except Exception as e:
        return jsonify({'error': f'Gemini model error: {str(e)}'}), 500
    
# build an outfit around a specific clothing item
@app.route('/outfits/build/<clothing_item_id>', methods=['POST'])
@jwt_required()
def build_outfit(clothing_item_id):
    email = get_jwt_identity()
    user = db.users.find_one({'email': email})
    if not user:
        return jsonify({'error': 'User must be logged in, please log in to use this api'}), 404
    base_item = db.clothing_items.find_one({'_id': clothing_item_id, 'user_id': user['_id']})
    if not base_item:
        return jsonify({'error': 'Base Clothing item not found'}), 404
    # get all clothing items from the database for the user which are available
    clothing_items = list(db.clothing_items.find({'user_id': user['_id'], 'available': True}))
    if not clothing_items:
        return jsonify({'error': 'No clothing items found for user'}), 404
    # sort the clothing items by frequency in increasing order
    clothing_items.sort(key=lambda x: x['frequency'])
    # get only the id, description and frequency of the clothing items
    clothing_items = [{'id': str(item['_id']), 'description': item['description'], 'frequency': item['frequency']} for item in clothing_items]
    # ask gemini for outfit recommendation
    try:
        model = genai.GenerativeModel("models/gemini-1.5-flash")
        prompt = "You are a fashion expert, Generate an outfit recommendation based on the following clothing items. the outfits you generate should all consist of this one, this one should be the base of outfits\n" + str(base_item) + "\n\nread the description of each item and generate 3 different outfits from them. make sure to keep in mind the color combinations and the style of the clothing items. the output should contain a json array, with each object having one outfit. each outfit object should have a name, description, list of ids of clothing items in the outfits and additional styling tips. \n\n" + str(clothing_items)
        outfit_description = query_gemini(prompt)
        # add user id to each outfit and save the outfit in the database
        for outfit in outfit_description:
            outfit['user_id'] = user['_id']
            outfit['created_at'] = datetime.datetime.now()
            db.outfits.insert_one(outfit)
        # return the outfits with the outfit ids, sort by time and get first 3 outfits
        outfits = list(db.outfits.find({'user_id': user['_id']}).sort('created_at', -1).limit(3))
        for outfit in outfits:
            outfit['_id'] = str(outfit['_id'])
        return jsonify(outfits)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# get all outfits for the user
@app.route('/outfits', methods=['GET'])
@jwt_required()
def get_outfits():
    email = get_jwt_identity()
    user = db.users.find_one({'email': email})
    if not user:
        return jsonify({'error': 'User must be logged in, please log in to use this api'}), 404
    outfits = list(db.outfits.find({'user_id': user['_id']}))
    for outfit in outfits:
        outfit['_id'] = str(outfit['_id'])
    return jsonify(outfits)

# get outfit by id
@app.route('/outfits/<id>', methods=['GET'])
@jwt_required() 
def get_outfit(id):
    email = get_jwt_identity()
    user = db.users.find_one({'email': email})
    if not user:
        return jsonify({'error': 'User must be logged in, please log in to use this api'}), 404
    outfit = db.outfits.find_one({'_id': id, 'user_id': user['_id']})
    if not outfit:
        return jsonify({'error': 'Outfit not found'}), 404
    outfit['_id'] = str(outfit['_id'])
    return jsonify(outfit)

# Initialize the scheduler
scheduler = BackgroundScheduler()
scheduler.start()

def set_clothing_items_available(clothing_item_ids):
    db.clothing_items.update_many(
        {'_id': {'$in': clothing_item_ids}},
        {'$set': {'available': True}}
    )

# use the outfit and set laundry timeout for the clothing items
@app.route('/outfits/use/<id>', methods=['POST'])
@jwt_required()
def use_outfit(id):
    email = get_jwt_identity()
    user = db.users.find_one({'email': email})
    if not user:
        return jsonify({'error': 'User must be logged in, please log in to use this api'}), 404
    outfit = db.outfits.find_one({'_id': id, 'user_id': user['_id']})
    if not outfit:
        return jsonify({'error': 'Outfit not found'}), 404
    # get the clothing items in the outfit
    clothing_items = list(db.clothing_items.find({'_id': {'$in': outfit['clothing_item_ids']}}))
    clothing_item_ids = [item['_id'] for item in clothing_items]
    # set the clothing items to unavailable and increase the frequency
    for item in clothing_items:
        db.clothing_items.update_one({'_id': item['_id']}, {'$set': {'available': False}, '$inc': {'frequency': 1}})
    
    # Schedule a job to set the clothing items back to available after a timeout (e.g., 48 hours)
    scheduler.add_job(
        set_clothing_items_available,
        'date',
        run_date=datetime.datetime.now() + datetime.timedelta(hours=48),
        args=[clothing_item_ids]
    )
    
    return jsonify({'message': 'Outfit used successfully'})


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