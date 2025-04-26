# ITニュース記事の要約音声配信サイト - APIサービス

## 概要

このプロジェクトは、ITニュース記事を要約して音声で配信するサービスのバックエンドAPIです。
フロントエンドアプリケーションにエピソードのメタデータや音声ファイルへのアクセスを提供します。

## ローカル開発環境のセットアップ

### 前提条件

- Python 3.8以上
- pip（Pythonパッケージマネージャ）

### インストール手順

1. 必要なパッケージのインストール:

```bash
pip install -r requirements.txt
```

2. ローカルサーバーの起動:

```bash
python local_server.py
```

## 利用可能なエンドポイント

- `GET /api/episodes` - エピソード一覧の取得
- `GET /api/episodes/<episode_id>` - 特定エピソードのメタデータ取得
- `GET /audio/<filename>` - 音声ファイルの取得
- `GET /api/health` - ヘルスチェック

## 設定

ローカルサーバーを起動する前に、必要に応じて`local_server.py`の以下の設定を修正してください：

- `LOCAL_NEWS_PATH` - メタデータJSONファイルの保存場所
- `LOCAL_AUDIO_PATH` - 音声ファイルの保存場所
- `BASE_URL` - 音声ファイルを提供するベースURL

## APIレスポンス形式

### エピソード一覧

```json
{
  "episodes": [
    {
      "episode_id": "2025-04-17",
      "title": "Tech News (2025-04-17)",
      "created_at": "2025-04-17 21:00:00"
    },
    ...
  ]
}
```

### 特定エピソード

```json
{
  "episode_id": "2025-04-17",
  "title": "Tech News (2025-04-17)",
  "created_at": "2025-04-17 21:00:00",
  "intro_audio_url": "http://localhost:5000/audio/narration/2025-04-17_intro.mp3",
  "outro_audio_url": "http://localhost:5000/audio/narration/2025-04-17_outro.mp3",
  "playlist": [
    {
      "type": "intro",
      "audio_url": "http://localhost:5000/audio/narration/2025-04-17_intro.mp3"
    },
    {
      "type": "article_intro",
      "article_id": "article1",
      "audio_url": "http://localhost:5000/audio/narration/2025-04-17_intro_1.mp3"
    },
    {
      "type": "article",
      "article_id": "article1",
      "audio_url": "http://localhost:5000/audio/2025-04-17_1.mp3"
    },
    ...
  ],
  "articles": [
    {
      "id": "article1",
      "title": "記事1のタイトル",
      "summary": "記事1の要約テキスト",
      "audio_url": "http://localhost:5000/audio/2025-04-17_1.mp3",
      "intro_audio_url": "http://localhost:5000/audio/narration/2025-04-17_intro_1.mp3",
      "duration": 180
    },
    ...
  ]
}
```
