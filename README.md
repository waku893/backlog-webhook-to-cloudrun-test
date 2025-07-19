# Backlog Webhook to Firestore via Cloud Functions (2nd gen)

This repository contains an example setup to receive Backlog webhooks with a Google Cloud Function **2nd gen** running on **Python 3.13** and store the payload in Firestore. The infrastructure is provisioned using Terraform.

## Structure

- `function/` – Python source code for the Cloud Function.
- `terraform/` – Terraform configuration to create the Cloud Function (2nd gen), Firestore database, service account and other required resources.

## Deployment

1. Install [Terraform](https://www.terraform.io/) and authenticate with Google Cloud.
2. Initialize Terraform and apply the configuration:

```bash
cd terraform
terraform init
terraform apply -var="project=<YOUR_GCP_PROJECT>"
```

The default region is `asia-northeast1`. Use `-var="region=<REGION>"` to override
it. The function URL will be printed in the outputs after apply.

If deployment fails with a 403 error about accessing `gcf-artifacts`,
grant the built‑in Cloud Functions service agent the
`roles/artifactregistry.reader` role. The Terraform configuration
grants this permission automatically when the function is created.

If a Firestore database already exists in your project, Terraform may
error with `Database already exists`. Database creation is disabled by
default via the `manage_firestore_database` variable. Set it to `true`
only when you need Terraform to create the database for you.

You can adjust the function's verbosity with the `log_level` variable. When set
to `DEBUG` the function logs request details and Firestore errors to help
diagnose issues.

This example expects **Firestore in Native mode**. If your project
uses Datastore mode you will see an error like:

```
FailedPrecondition: 400 The Cloud Firestore API is not available for
Firestore in Datastore Mode database
```

Create a new project or switch to Native mode to use this example.

Backlog can be configured to POST webhooks to this URL. Each payload will be stored in the Firestore collection defined by `FIRESTORE_COLLECTION` (defaults to `backlog_webhooks`).

To troubleshoot unexpected `500` responses, set the environment variable `LOG_LEVEL` to `DEBUG` so the function emits detailed logs. The Terraform configuration exposes a `log_level` variable that controls this setting.

Terraform state and build artifacts (such as `function.zip`) are ignored via `.gitignore` so they don’t clutter your repository. You can review that file for the exact list.
