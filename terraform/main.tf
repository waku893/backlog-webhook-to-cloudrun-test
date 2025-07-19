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

resource "google_project_service" "firestore" {
  service = "firestore.googleapis.com"
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

resource "google_project_iam_member" "firestore_access" {
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
      FIRESTORE_COLLECTION = var.firestore_collection
      LOG_LEVEL            = var.log_level
    }
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

resource "google_firestore_database" "default" {
  count       = var.manage_firestore_database ? 1 : 0
  name        = "(default)"
  project     = var.project
  location_id = var.region
  type        = "FIRESTORE_NATIVE"
  depends_on  = [google_app_engine_application.app]
}
