# Cloud Functions (第2世代) で Backlog Webhook を Firestore に保存する例

このリポジトリは、Backlog から送られる Webhook を Google Cloud Functions **第2世代** (Python 3.13) で受け取り、Firestore ネイティブモード に保存するサンプルです。オプションで Pub/Sub を利用して非同期処理に切り替えることもできます。インフラは Terraform で構築します。

## 構成

- `function/` – Cloud Functions の Python コード
- `terraform/` – GCP リソースを作成する Terraform 設定

## デプロイ手順

1. [Terraform](https://www.terraform.io/) をインストールし、Google Cloud に認証します。
2. Terraform を初期化して適用します。

```bash
cd terraform
terraform init
terraform apply -var="project=<YOUR_GCP_PROJECT>"
```

デフォルトのリージョンは `asia-northeast1` です。別のリージョンを使う場合は `-var="region=<REGION>"` を指定してください。`use_pubsub=true` を渡すと Pub/Sub 経由で処理されます。
Firestore データベースを自動作成したい場合は `-var="manage_firestore_database=true"` を、すでに存在する場合は `false` を指定してください。
Firestore のデータベース名は `firestore_database_id` 変数で変更でき、Cloud Function には `FIRESTORE_DATABASE` 環境変数として渡されます。

関数の URL が出力されるので、Backlog の Webhook 先として設定してください。`log_level` を `DEBUG` にすると詳細なログが得られます。

## 処理概要

Webhook 受信関数は JSON ペイロードを受け取り、`USE_PUBSUB` 環境変数が `true` の場合は Pub/Sub トピックへメッセージを publish します。`false` の場合はそのまま Firestore へ保存します。Pub/Sub を使用する場合は、`pubsub_handler` 関数がメッセージを購読して Firestore への書き込みを行います。
イベントタイプは [Backlog API の "最近の更新情報" ドキュメント](https://developer.nulab.com/ja/docs/backlog/api/2/get-recent-updates/) を参照しています。
主な数値は次の通りです。

| 値  | 内容                       |
|-----|----------------------------|
| 1   | 課題の追加                 |
| 2   | 課題の更新                 |
| 3   | 課題にコメント             |
| 4   | 課題の削除                 |
| 14  | 課題をまとめて更新         |
| 17  | コメントにお知らせを追加   |

Firestore では次の 3 つのコレクションを利用します。

- `backlog-issue`
- `backlog-comment`
- `backlog-comment-notif`

イベントタイプ (課題追加・更新・コメント・削除など) に応じてそれぞれのコレクションへデータを追加・更新・削除します。各コレクションでは主なフィールドを抜き出して保存しており、例えば `backlog-issue` では課題 ID やステータス、担当者に加えて `projectKey` と `issueKey` も文字列として保存します。`backlog-comment` と `backlog-comment-notif` でも `projectKey` と `projectName` を含め、コメント ID・発言者・本文や通知先ユーザー情報を保存します。

Terraform ではデフォルトで必要な API を有効化し、Cloud Function 用のサービスアカウントと Pub/Sub トピック (必要な場合) を作成します。Artifact Registry へのアクセス権も自動で付与されます。

`.gitignore` には Terraform の状態ファイルや `function.zip` などの生成物を除外する設定が含まれています。

## 注意点

このサンプルは **Firestore ネイティブモード** を前提としています。プロジェクトのデータベースが Datastore モードの場合、Cloud Function は `Firestore in Datastore mode` というメッセージと共に HTTP 503 を返します。ネイティブモードのデータベースを作成してからご利用ください。

