variable "project" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "asia-northeast1"
}

variable "function_name" {
  description = "HTTP Cloud Function name"
  type        = string
  default     = "backlog-webhook-handler"
}

variable "use_pubsub" {
  description = "Publish webhook payloads to Pub/Sub"
  type        = bool
  default     = false
}

variable "pubsub_topic" {
  description = "Pub/Sub topic name when use_pubsub is true"
  type        = string
  default     = "backlog-webhook"
}

variable "log_level" {
  description = "Logging level for the Cloud Function"
  type        = string
  default     = "INFO"
}
