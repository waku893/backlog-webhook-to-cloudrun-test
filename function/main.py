import os
from google.cloud import firestore

collection = os.environ.get("FIRESTORE_COLLECTION", "backlog_webhooks")

db = firestore.Client()

def webhook_handler(request):
    if request.method != "POST":
        return ("Method Not Allowed", 405)

    data = request.get_json(silent=True)
    if data is None:
        return ("Bad Request: no JSON payload", 400)

    db.collection(collection).add({"payload": data})
    return ("OK", 200)
