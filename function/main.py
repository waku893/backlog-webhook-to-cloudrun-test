import os
from google.cloud import firestore
from google.api_core import exceptions

collection = os.environ.get("FIRESTORE_COLLECTION", "backlog_webhooks")

db = firestore.Client()

def webhook_handler(request):
    if request.method != "POST":
        return ("Method Not Allowed", 405)

    data = request.get_json(silent=True)
    if data is None:
        return ("Bad Request: no JSON payload", 400)

    try:
        db.collection(collection).add({"payload": data})
    except exceptions.FailedPrecondition:
        # Raised if the project uses Firestore in Datastore mode
        return ("Firestore in Datastore mode is not supported", 500)
    return ("OK", 200)
