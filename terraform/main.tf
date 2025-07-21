terraform {
  required_version = ">= 1.2"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project
  region  = var.region
}

# Lookup project info (number needed for service agent email)
data "google_project" "current" {
  project_id = var.project
}

# Enable required services
resource "google_project_service" "cloudfunctions" {
  service = "cloudfunctions.googleapis.com"
}

resource "google_project_service" "datastore" {
  service = "datastore.googleapis.com"
}

resource "google_project_service" "cloudbuild" {
  service = "cloudbuild.googleapis.com"
}

# Grant Artifact Registry read access to the Cloud Functions service agent
resource "google_project_iam_member" "cloudfunctions_artifact_registry" {
  project    = var.project
  role       = "roles/artifactregistry.reader"
  member     = "serviceAccount:service-${data.google_project.current.number}@gcf-admin-robot.iam.gserviceaccount.com"
  depends_on = [google_project_service.cloudfunctions]
}

# Service account for Cloud Function
resource "google_service_account" "function_sa" {
  account_id   = "function-sa"
  display_name = "Cloud Function SA"
}

resource "google_project_iam_member" "datastore_access" {
  project = var.project
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.function_sa.email}"
}

# Storage bucket for function source
resource "google_storage_bucket" "function_bucket" {
  name          = "${var.project}-function-source"
  location      = var.region
  force_destroy = true
}

resource "google_pubsub_topic" "webhook" {
  count   = var.use_pubsub ? 1 : 0
  name    = var.pubsub_topic
  project = var.project
}

resource "google_project_iam_member" "pubsub_publisher" {
  count   = var.use_pubsub ? 1 : 0
  project = var.project
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.function_sa.email}"
}

resource "google_project_iam_member" "pubsub_subscriber" {
  count   = var.use_pubsub ? 1 : 0
  project = var.project
  role    = "roles/pubsub.subscriber"
  member  = "serviceAccount:${google_service_account.function_sa.email}"
}

data "archive_file" "function_zip" {
  type        = "zip"
  source_dir  = "../function"
  output_path = "${path.module}/function.zip"
}

resource "google_storage_bucket_object" "function_archive" {
  name   = "function-${data.archive_file.function_zip.output_md5}.zip"
  bucket = google_storage_bucket.function_bucket.name
  source = data.archive_file.function_zip.output_path
}

resource "google_cloudfunctions2_function" "function" {
  name     = var.function_name
  location = var.region

  build_config {
    runtime     = "python313"
    entry_point = "webhook_handler"

    source {
      storage_source {
        bucket = google_storage_bucket.function_bucket.name
        object = google_storage_bucket_object.function_archive.name
      }
    }
  }

  service_config {
    service_account_email = google_service_account.function_sa.email
    environment_variables = {
      LOG_LEVEL    = var.log_level
      USE_PUBSUB   = tostring(var.use_pubsub)
      PUBSUB_TOPIC = var.pubsub_topic
    }
  }
}

resource "google_cloudfunctions2_function" "processor" {
  count    = var.use_pubsub ? 1 : 0
  name     = "${var.function_name}-processor"
  location = var.region

  build_config {
    runtime     = "python313"
    entry_point = "pubsub_handler"

    source {
      storage_source {
        bucket = google_storage_bucket.function_bucket.name
        object = google_storage_bucket_object.function_archive.name
      }
    }
  }

  service_config {
    service_account_email = google_service_account.function_sa.email
    environment_variables = {
      LOG_LEVEL    = var.log_level
      USE_PUBSUB   = tostring(var.use_pubsub)
      PUBSUB_TOPIC = var.pubsub_topic
    }
  }

  event_trigger {
    trigger_region = var.region
    event_type     = "google.cloud.pubsub.topic.v1.messagePublished"
    pubsub_topic   = google_pubsub_topic.webhook[0].id
  }
}

resource "google_cloud_run_service_iam_member" "invoker" {
  project    = var.project
  location   = var.region
  service    = google_cloudfunctions2_function.function.name
  role       = "roles/run.invoker"
  member     = "allUsers"
  depends_on = [google_cloudfunctions2_function.function]
}

resource "google_app_engine_application" "app" {
  project     = var.project
  location_id = var.region
}
