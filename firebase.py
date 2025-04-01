#sudo pip install firebase-admin
import firebase_admin
from firebase_admin import credentials
import os
from dotenv import load_dotenv

load_dotenv()

cred = credentials.Certificate("FIREBASE_SERVICE_ACCOUNT")
firebase_app=firebase_admin.initialize_app(cred)