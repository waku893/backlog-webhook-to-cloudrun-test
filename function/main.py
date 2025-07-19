import os
import logging
from google.cloud import firestore
from google.cloud import datastore
from google.api_core import exceptions

collection = os.environ.get("FIRESTORE_COLLECTION", "backlog_webhooks")
log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=getattr(logging, log_level, logging.INFO))

db = firestore.Client()
ds = datastore.Client()

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
        # Firestore is in Datastore mode. Use Datastore client instead.
        logging.warning("Firestore in Datastore mode; using Datastore client")
        try:
            key = ds.key(collection)
            entity = datastore.Entity(key=key)
            entity.update({"payload": data})
            ds.put(entity)
            logging.debug("Stored Datastore entity: %s", entity.key.id_or_name)
        except Exception:
            logging.exception("Failed to store payload in Datastore")
            return ("Internal Server Error", 500)
    except Exception:
        logging.exception("Failed to store payload")
        return ("Internal Server Error", 500)
    return ("OK", 200)
