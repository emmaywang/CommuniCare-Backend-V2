#sudo pip install firebase-admin
import firebase_admin
from firebase_admin import credentials
import os
# import base64
import json
from dotenv import load_dotenv

load_dotenv()

# Get the current directory
current_dir = os.path.dirname(os.path.abspath(__file__))

# Join it with this filename to get the correct absolute path
service_account = os.path.join(current_dir, "service_account.json")

# service_account=os.getenv("FIREBASE_SERVICE_ACCOUNT")
cred = credentials.Certificate(service_account)
firebase_app=firebase_admin.initialize_app(cred)