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

# Service account for Cloud Function
resource "google_service_account" "function_sa" {
  account_id   = "function-sa"
  display_name = "Cloud Function SA"
}

resource "google_project_iam_member" "firestore_access" {
  role   = "roles/datastore.user"
  member = "serviceAccount:${google_service_account.function_sa.email}"
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

resource "google_cloudfunctions_function" "function" {
  name        = var.function_name
  runtime     = "python39"
  entry_point = "webhook_handler"
  region      = var.region

  source_archive_bucket = google_storage_bucket.function_bucket.name
  source_archive_object = google_storage_bucket_object.function_archive.name
  service_account_email = google_service_account.function_sa.email

  trigger_http = true

  environment_variables = {
    FIRESTORE_COLLECTION = var.firestore_collection
  }
}

resource "google_app_engine_application" "app" {
  project     = var.project
  location_id = var.region
}

resource "google_firestore_database" "default" {
  name        = "(default)"
  project     = var.project
  location_id = var.region
  type        = "FIRESTORE_NATIVE"
  depends_on  = [google_app_engine_application.app]
}
