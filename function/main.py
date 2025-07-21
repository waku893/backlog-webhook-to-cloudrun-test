import os
import json
import base64
import logging
from google.cloud import datastore
from google.cloud import pubsub_v1

# Logging setup
log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=getattr(logging, log_level, logging.INFO))

USE_PUBSUB = os.environ.get("USE_PUBSUB", "false").lower() == "true"
PUBSUB_TOPIC = os.environ.get("PUBSUB_TOPIC", "backlog-webhook")
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("GCP_PROJECT")

# Datastore client
ds = datastore.Client(project=PROJECT_ID)

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

    if event_type in ("issue_created", "issue_updated"):
        store_issue(content)
    elif event_type == "issue_deleted":
        delete_issue(content)
    elif event_type == "comment_created":
        store_comment(content)
    elif event_type == "comment_deleted":
        delete_comment(content)
    elif event_type == "comment_notification":
        store_comment_notif(content)
    else:
        logging.warning("Unknown event type: %s", event_type)

def store_issue(issue):
    issue_id = str(issue.get("issue_id") or issue.get("id"))
    key = ds.key("backlog-issue", issue_id)
    entity = datastore.Entity(key=key)
    entity.update(issue)
    ds.put(entity)
    logging.info("Stored/updated issue %s", issue_id)

def delete_issue(issue):
    issue_id = str(issue.get("issue_id") or issue.get("id"))
    key = ds.key("backlog-issue", issue_id)
    ds.delete(key)
    logging.info("Deleted issue %s", issue_id)

def store_comment(comment):
    comment_id = str(comment.get("key") or comment.get("comment_id") or comment.get("id"))
    key = ds.key("backlog-comment", comment_id)
    entity = datastore.Entity(key=key)
    entity.update(comment)
    ds.put(entity)
    logging.info("Stored/updated comment %s", comment_id)

def delete_comment(comment):
    comment_id = str(comment.get("key") or comment.get("comment_id") or comment.get("id"))
    key = ds.key("backlog-comment", comment_id)
    ds.delete(key)
    logging.info("Deleted comment %s", comment_id)

def store_comment_notif(notif):
    notif_id = str(notif.get("notification_id") or notif.get("id"))
    key = ds.key("backlog-comment-notif", notif_id)
    entity = datastore.Entity(key=key)
    entity.update(notif)
    ds.put(entity)
    logging.info("Stored/updated notification %s", notif_id)
