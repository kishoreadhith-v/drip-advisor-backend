from flask import Flask, jsonify
import traceback
from flask_cors import CORS
from pymongo import MongoClient
from dotenv import load_dotenv
import os

load_dotenv()

app = Flask(__name__)
CORS(app)

client = MongoClient(os.getenv('MONGO_URI'))
db = client['dev']


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