# Cloud Functions (第2世代) で Backlog の Webhook を Firestore に保存する例

このリポジトリは、Backlog から送られる Webhook を Google Cloud Functions **第2世代** (Python 3.13) で受け取り、Firestore に保存するサンプルです。Firestore が Datastore モードの場合は自動的に Datastore API に切り替えて保存します。インフラは Terraform で構築します。

## 構成

- `function/` – Cloud Function の Python ソースコード
- `terraform/` – Cloud Function (第2世代) や Firestore、サービスアカウントなどを作成する Terraform 設定

## デプロイ手順

1. [Terraform](https://www.terraform.io/) をインストールし、Google Cloud に認証します。
2. Terraform を初期化して適用します。

```bash
cd terraform
terraform init
terraform apply -var="project=<YOUR_GCP_PROJECT>"
```

デフォルトのリージョンは `asia-northeast1` です。別のリージョンを使う場合は `-var="region=<REGION>"` を指定してください。適用後、関数の URL が出力されます。

`gcf-artifacts` へのアクセス権がなく 403 エラーになる場合は、Cloud Functions のサービス エージェントに `roles/artifactregistry.reader` 権限を付与してください。Terraform では関数作成後に自動的にこの権限を付与します。

既に Firestore データベースが存在する場合、`Database already exists` というエラーが出ることがあります。Terraform では `manage_firestore_database` 変数を `false` (デフォルト) にすることでデータベース作成をスキップできます。新規作成が必要な場合のみ `true` に設定してください。

`log_level` 変数で関数のログレベルを変更できます。`DEBUG` に設定するとリクエスト内容や Firestore のエラーを詳細に記録し、`500` エラーの原因を調査しやすくなります。

プロジェクトが **Firestore の Datastore モード** を使用している場合、関数は自動的に Datastore API に切り替えます。ログには次のように表示されます。

```
Firestore in Datastore mode; using Datastore client
```

この場合もデータは Datastore に保存されます。

Backlog の Webhook URL としてこの関数のエンドポイントを指定すると、受け取った JSON ペイロードが `FIRESTORE_COLLECTION` (デフォルトは `backlog_webhooks`) に保存されます。

`LOG_LEVEL` を `DEBUG` にすると、予期しない `500` エラーの原因を追跡するための詳細なログが出力されます。Terraform の `log_level` 変数から設定できます。

Terraform の状態ファイルや `function.zip` などのビルド成果物は `.gitignore` で除外しています。不要なファイルがリポジトリに含まれないよう確認してください。

