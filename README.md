# Backlog Webhook to Firestore via Cloud Functions

This repository contains an example setup to receive Backlog webhooks with a Google Cloud Function and store the payload in Firestore. The infrastructure is provisioned using Terraform.

## Structure

- `function/` – Python source code for the Cloud Function.
- `terraform/` – Terraform configuration to create the Cloud Function, Firestore database, service account and other required resources.

## Deployment

1. Install [Terraform](https://www.terraform.io/) and authenticate with Google Cloud.
2. Initialize Terraform and apply the configuration:

```bash
cd terraform
terraform init
terraform apply -var="project=<YOUR_GCP_PROJECT>"
```

The function URL will be printed in the outputs after apply.

If Cloud Functions deployment fails with a 403 error about accessing
`gcf-artifacts`, grant the built-in Cloud Functions service agent the
`roles/artifactregistry.reader` role. Terraform configuration in this
repository does this automatically.

If a Firestore database already exists in your project, Terraform may
error with `Database already exists`. In that case you can safely
comment out the `google_firestore_database` resource in
`terraform/main.tf`.

Backlog can be configured to POST webhooks to this URL. Each payload will be stored in the Firestore collection defined by `FIRESTORE_COLLECTION` (defaults to `backlog_webhooks`).
