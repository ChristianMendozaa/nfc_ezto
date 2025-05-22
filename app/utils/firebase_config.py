import firebase_admin
from firebase_admin import credentials, firestore

# Inicializa SDK de Firestore
cred = credentials.Certificate("firebase_credentials.json")
firebase_admin.initialize_app(cred)
db = firestore.client()
