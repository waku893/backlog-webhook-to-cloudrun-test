import os
import logging
from google.cloud import firestore
from google.api_core import exceptions

collection = os.environ.get("FIRESTORE_COLLECTION", "backlog_webhooks")
log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=getattr(logging, log_level, logging.INFO))

db = firestore.Client()

def webhook_handler(request):
    logging.debug("Received %s request", request.method)
    if request.method != "POST":
        logging.warning("Invalid method: %s", request.method)
        return ("Method Not Allowed", 405)

    data = request.get_json(silent=True)
    if data is None:
        logging.warning("No JSON payload")
        return ("Bad Request: no JSON payload", 400)

    try:
        doc_ref = db.collection(collection).add({"payload": data})
        logging.debug("Stored document: %s", doc_ref[1].id)
    except exceptions.FailedPrecondition:
        # Raised if the project uses Firestore in Datastore mode
        logging.exception("Firestore in Datastore mode")
        return ("Firestore in Datastore mode is not supported", 500)
    except Exception:
        logging.exception("Failed to store payload")
        return ("Internal Server Error", 500)
    return ("OK", 200)
