import os
import json
import base64
import logging
from google.cloud import firestore
from google.cloud import pubsub_v1
import google.auth

# Logging setup
log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=getattr(logging, log_level, logging.INFO))

USE_PUBSUB = os.environ.get("USE_PUBSUB", "false").lower() == "true"
PUBSUB_TOPIC = os.environ.get("PUBSUB_TOPIC", "backlog-webhook")
try:
    _, default_project = google.auth.default()
except Exception:
    default_project = None
PROJECT_ID = (
    os.environ.get("PROJECT_ID")
    or os.environ.get("GOOGLE_CLOUD_PROJECT")
    or os.environ.get("GCP_PROJECT")
    or default_project
)
FIRESTORE_DATABASE = os.environ.get("FIRESTORE_DATABASE", "(default)")

# Firestore client
db = firestore.Client(project=PROJECT_ID, database=FIRESTORE_DATABASE)

# Pub/Sub client only when needed
publisher = pubsub_v1.PublisherClient() if USE_PUBSUB else None
if USE_PUBSUB:
    topic_path = publisher.topic_path(PROJECT_ID, PUBSUB_TOPIC)
else:
    topic_path = None

def webhook_handler(request):
    """HTTP entry point for Backlog webhook."""
    logging.debug("Received %s request", request.method)
    if request.method != "POST":
        logging.warning("Invalid method: %s", request.method)
        return ("Method Not Allowed", 405)

    data = request.get_json(silent=True)
    if data is None:
        logging.warning("No JSON payload")
        return ("Bad Request: no JSON payload", 400)

    if USE_PUBSUB:
        try:
            payload = json.dumps(data).encode()
            future = publisher.publish(topic_path, payload)
            future.result()
            logging.info("Published message to Pub/Sub")
            return ("OK", 200)
        except Exception as e:
            logging.exception("Failed to publish message: %s", e)
            return ("Internal Server Error", 500)
    else:
        try:
            process_event(data)
            return ("OK", 200)
        except Exception as e:
            logging.exception("Failed to process event: %s", e)
            return ("Internal Server Error", 500)

def pubsub_handler(event, context):
    """Triggered from Pub/Sub when USE_PUBSUB is true."""
    try:
        payload = base64.b64decode(event["data"]).decode()
        data = json.loads(payload)
        process_event(data)
    except Exception as e:
        logging.exception("Failed to handle Pub/Sub message: %s", e)
        raise

def process_event(data):
    """Process a Backlog webhook payload."""
    event_type = data.get("type")
    content = data.get("content", {})
    logging.debug("Processing event %s", event_type)

    if str(event_type) in ("1", "2", "14"):
        store_issue(content)
    elif str(event_type) == "4":
        delete_issue(content)
    elif str(event_type) == "3":
        store_comment(content)
    elif str(event_type) == "17":
        store_comment_notif(content)
    else:
        logging.warning("Unknown event type: %s", event_type)

def store_issue(issue):
    issue_id = str(issue.get("issue_id") or issue.get("id"))
    db.collection("backlog-issue").document(issue_id).set(issue)
    logging.info("Stored/updated issue %s", issue_id)

def delete_issue(issue):
    issue_id = str(issue.get("issue_id") or issue.get("id"))
    db.collection("backlog-issue").document(issue_id).delete()
    logging.info("Deleted issue %s", issue_id)

def store_comment(comment):
    comment_id = str(comment.get("key") or comment.get("comment_id") or comment.get("id"))
    db.collection("backlog-comment").document(comment_id).set(comment)
    logging.info("Stored/updated comment %s", comment_id)

def delete_comment(comment):
    comment_id = str(comment.get("key") or comment.get("comment_id") or comment.get("id"))
    db.collection("backlog-comment").document(comment_id).delete()
    logging.info("Deleted comment %s", comment_id)

def store_comment_notif(notif):
    notif_id = str(notif.get("notification_id") or notif.get("id"))
    db.collection("backlog-comment-notif").document(notif_id).set(notif)
    logging.info("Stored/updated notification %s", notif_id)
