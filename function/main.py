import os
import json
import base64
import logging
from google.cloud import firestore
from google.cloud import pubsub_v1
from google.api_core import exceptions as gexc
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
        except gexc.FailedPrecondition as e:
            logging.error("Firestore in Datastore mode: %s", e)
            return ("Firestore in Datastore mode", 503)
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

    if str(event_type) in ("1", "2"):
        store_issue(data, content)
    elif str(event_type) == "14":
        store_bulk_update(data, content)
    elif str(event_type) == "4":
        delete_issue(content)
    elif str(event_type) == "3":
        store_comment(data, content)
    elif str(event_type) == "17":
        store_comment_notif(data, content)
    else:
        logging.warning("Unknown event type: %s", event_type)

def store_issue(root, issue):
    """Save issue fields to Firestore."""
    issue_id = str(issue.get("id"))
    doc = {
        "issue_id": issue_id,
        "project_id": root.get("project", {}).get("id"),
        "project_key": root.get("project", {}).get("projectKey"),
        "issue_key": f"{root.get('project', {}).get('projectKey')}-{issue.get('key_id')}" if issue.get("key_id") else None,
        "title": issue.get("summary"),
        "status_id": issue.get("status", {}).get("id"),
        "status": issue.get("status", {}).get("name"),
        "assignee_id": (issue.get("assignee") or {}).get("id"),
        "assignee_name": (issue.get("assignee") or {}).get("name"),
        "issue_type_id": issue.get("issueType", {}).get("id"),
        "issue_type_name": issue.get("issueType", {}).get("name"),
        "priority_id": issue.get("priority", {}).get("id"),
        "priority_name": issue.get("priority", {}).get("name"),
        "description": issue.get("description"),
        "created_at": root.get("created"),
    }
    db.collection("backlog-issue").document(issue_id).set(doc)
    logging.info("Stored/updated issue %s", issue_id)

def store_bulk_update(root, content):
    """Update multiple issues based on bulk update payload."""
    changes = content.get("changes", [])
    update_doc = {}
    for change in changes:
        field = change.get("field")
        new = change.get("new_value")
        # new_value may be an object or a simple value
        if isinstance(new, dict):
            new_id = new.get("id")
            new_name = new.get("name")
        else:
            # when only ID is provided, map to id field
            new_id = new
            new_name = None
        if field == "status":
            update_doc["status_id"] = new_id
            update_doc["status"] = new_name
        elif field == "resolution":
            update_doc["resolution_id"] = new_id
            update_doc["resolution"] = new_name
        elif field == "assignee":
            update_doc["assignee_id"] = new_id
            update_doc["assignee_name"] = new_name
        elif field == "priority":
            update_doc["priority_id"] = new_id
            update_doc["priority_name"] = new_name
    update_doc["updated_at"] = root.get("created")

    for link in content.get("link", []):
        issue_id = str(link.get("id"))
        doc = {
            "issue_id": issue_id,
            "issue_key": (
                f"{root.get('project', {}).get('projectKey')}-{link.get('key_id')}"
                if link.get("key_id") is not None
                else None
            ),
            "title": link.get("title") or link.get("summary"),
        }
        doc.update(update_doc)
        db.collection("backlog-issue").document(issue_id).set(doc, merge=True)
        logging.info("Processed bulk update for issue %s", issue_id)

def delete_issue(issue):
    issue_id = str(issue.get("issue_id") or issue.get("id"))
    db.collection("backlog-issue").document(issue_id).delete()
    logging.info("Deleted issue %s", issue_id)

def store_comment(root, content):
    """Save issue comment details."""
    comment = content.get("comment", {})
    comment_id = str(comment.get("id"))
    issue_key = None
    if content.get("key_id") is not None:
        issue_key = f"{root.get('project', {}).get('projectKey')}-{content.get('key_id')}"
    doc = {
        "comment_id": comment_id,
        "issue_key": issue_key,
        "author_id": root.get("createdUser", {}).get("id"),
        "author_name": root.get("createdUser", {}).get("name"),
        "content": comment.get("content"),
        "created_at": root.get("created"),
    }
    db.collection("backlog-comment").document(comment_id).set(doc)
    logging.info("Stored/updated comment %s", comment_id)

def delete_comment(comment):
    comment_id = str(comment.get("key") or comment.get("comment_id") or comment.get("id"))
    db.collection("backlog-comment").document(comment_id).delete()
    logging.info("Deleted comment %s", comment_id)

def store_comment_notif(root, content):
    """Save notification entries."""
    comment_id = (content.get("comment") or {}).get("id")
    for notif in root.get("notifications", []):
        notif_id = str(notif.get("id"))
        doc = {
            "comment_id": comment_id,
            "notification_id": notif_id,
            "user_id": notif.get("user", {}).get("id"),
            "user_name": notif.get("user", {}).get("name"),
            "already_read": notif.get("alreadyRead"),
            "resource_already_read": notif.get("resourceAlreadyRead"),
            "reason": notif.get("reason"),
            "notified_at": root.get("created"),
        }
        db.collection("backlog-comment-notif").document(notif_id).set(doc)
        logging.info("Stored/updated notification %s", notif_id)
