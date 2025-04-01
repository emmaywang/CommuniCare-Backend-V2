#sudo pip install firebase-admin
import firebase_admin
from firebase_admin import credentials
import os
import base64
import json
# from dotenv import load_dotenv

# load_dotenv()

firebase_json_b64 = os.getenv("FIREBASE_ENCODED_CREDENTIALS")
# Decode credentials back to JSON
firebase_json = base64.b64decode(firebase_json_b64).decode("utf-8")
# Convert to dictionary and use it directly
firebase_dict = json.loads(firebase_json)

cred = credentials.Certificate(firebase_dict)
# cred = credentials.Certificate("FIREBASE_SERVICE_ACCOUNT")
firebase_app=firebase_admin.initialize_app(cred)