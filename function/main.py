import os
import logging
from google.cloud import firestore
from google.cloud import datastore
from google.api_core import exceptions

collection = os.environ.get("FIRESTORE_COLLECTION", "backlog_webhooks")
log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=getattr(logging, log_level, logging.INFO))

project_id = os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("GCP_PROJECT")
database_id = os.environ.get("FIRESTORE_DATABASE", "(default)")
db = firestore.Client(project=project_id, database=database_id)
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
        update_time, doc_ref = db.collection(collection).add({"payload": data})
        logging.info(
            "Stored document %s at %s", doc_ref.id, update_time.isoformat()
        )
    except exceptions.FailedPrecondition:
        # Firestore is in Datastore mode. Use Datastore client instead.
        logging.warning("Firestore in Datastore mode; using Datastore client")
        try:
            key = ds.key(collection)
            entity = datastore.Entity(key=key)
            entity.update({"payload": data})
            ds.put(entity)
            logging.debug("Stored Datastore entity: %s", entity.key.id_or_name)
        except Exception as e:
            logging.exception("Failed to store payload in Datastore: %s", e)
            return ("Internal Server Error", 500)
    except Exception as e:
        logging.exception("Failed to store payload: %s", e)
        return ("Internal Server Error", 500)
    return ("OK", 200)
