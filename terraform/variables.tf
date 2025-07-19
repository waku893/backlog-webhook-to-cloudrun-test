variable "project" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "us-central1"
}

variable "function_name" {
  description = "Name of the Cloud Function"
  type        = string
  default     = "backlog-webhook-handler"
}

variable "firestore_collection" {
  description = "Firestore collection name"
  type        = string
  default     = "backlog_webhooks"
}
