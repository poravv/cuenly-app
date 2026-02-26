
import os
from pymongo import MongoClient
from datetime import datetime

MONGO_URL = "mongodb://cuenlyapp:cuenlyapp2025_seguro@localhost:27017/admin"
DB_NAME = "cuenlyapp_warehouse"

def find_specifics():
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    headers_coll = db.invoice_headers
    processed_coll = db.processed_emails
    
    print("--- Searching for ERR_31170 ---")
    query = {"numero_documento": {"$regex": "31170"}}
    for doc in headers_coll.find(query):
        print(f"Header ID: {doc.get('_id')}")
        print(f"Factura: {doc.get('numero_documento')}")
        print(f"Emisor: {doc.get('emisor', {}).get('nombre')}")
        print(f"Status: {doc.get('status')}")
        print(f"Error: {doc.get('processing_error')}")
        print(f"Sender Email Origen: {doc.get('email_origen')}")
        print("-" * 30)

    print("\n--- Searching for 'Indutex' in processed_emails ---")
    query_p = {"$or": [
        {"subject": {"$regex": "Indutex", "$options": "i"}},
        {"sender": {"$regex": "Indutex", "$options": "i"}}
    ]}
    for doc in processed_coll.find(query_p):
         print(f"Registry ID: {doc.get('_id')}")
         print(f"Account: {doc.get('account_email')}")
         print(f"Status: {doc.get('status')}")
         print(f"Subject: {doc.get('subject')}")
         print(f"Reason: {doc.get('reason')}")
         print("-" * 30)
         
    print("\n--- Searching for 'Indutex' in invoice_headers ---")
    query_h = {"emisor.nombre": {"$regex": "Indutex", "$options": "i"}}
    for doc in headers_coll.find(query_h):
        print(f"Header ID: {doc.get('_id')}")
        print(f"Factura: {doc.get('numero_documento')}")
        print(f"Status: {doc.get('status')}")
        print("-" * 30)

if __name__ == "__main__":
    find_specifics()
