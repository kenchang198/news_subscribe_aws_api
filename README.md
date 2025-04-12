# News Subscribe AWS API

ITニュース記事の要約音声配信サイト用のAPI Lambdaプロジェクト

## 概要

このプロジェクトは、ITニュースの最新記事を自動で要約し、音声合成（TTS）で配信するためのAPI部分を提供します。

API Gatewayを通じて以下のエンドポイントを公開します：

- `/api/episodes` - エピソード一覧を取得
- `/api/episodes/{episode_id}` - 特定のエピソードを取得
- `/api/articles/{article_id}/summary` - 記事の要約を取得
- `/api/articles/{article_id}/audio` - 記事の音声URLを取得

## 開発環境のセットアップ

### 必要条件

- Python 3.9以上
- AWS CLI
- AWS SAM CLI

### 環境構築

1. リポジトリをクローンする

```bash
git clone <repository-url>
cd news_subscribe_aws_api
```

2. 仮想環境を作成してアクティベートする

```bash
python -m venv env
source env/bin/activate  # macOS/Linux
env\Scripts\activate     # Windows
```

3. 依存関係をインストールする

```bash
pip install -r requirements.txt
```

4. 環境変数を設定する

```bash
cp .env.example .env
# .envファイルを編集して適切な設定を行う
```

## ローカル開発

ローカルのFlaskサーバーを使用して開発することができます：

```bash
python local_api_server.py
```

これにより、http://localhost:3001/ でAPIサーバーが起動します。

## AWSへのデプロイ

AWS SAMを使用してデプロイします：

```bash
# SAMビルド
sam build

# 初回デプロイ（対話式）
sam deploy --guided

# 2回目以降のデプロイ
sam deploy
```

## APIエンドポイント

### エピソード一覧を取得

```
GET /api/episodes?page=1&limit=10
```

### 特定のエピソードを取得

```
GET /api/episodes/{episode_id}
```

### 記事の要約を取得

```
GET /api/articles/{article_id}/summary?language=ja
```

### 記事の音声URLを取得

```
GET /api/articles/{article_id}/audio?language=ja
```

## フロントエンドとの連携

このAPIは、Next.jsベースのフロントエンドアプリケーションと連携するように設計されています。フロントエンドは別リポジトリ（news-audio-frontend）にあります。
# news_subscribe_aws_api
