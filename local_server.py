import os
import json
import logging
from flask import Flask, request, send_from_directory, jsonify
from src.api_handler import handle_request
from src.config import LOCAL_HOST, LOCAL_PORT, LOCAL_AUDIO_DIR, LOCAL_DATA_DIR

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('local_server')

# Flaskアプリケーション初期化
app = Flask(__name__)


@app.route('/api/episodes', methods=['GET'])
def get_episodes():
    """エピソード一覧取得エンドポイント"""
    event = {
        'path': '/api/episodes',
        'httpMethod': 'GET',
        'headers': dict(request.headers),
        'queryStringParameters': request.args.to_dict()
    }
    response = handle_request(event)

    # Lambda形式のレスポンスをFlask形式に変換
    return (
        response.get('body', '{}'),
        response.get('statusCode', 200),
        response.get('headers', {})
    )


@app.route('/api/episodes/<episode_id>', methods=['GET'])
def get_episode(episode_id):
    """特定エピソード取得エンドポイント"""
    event = {
        'path': f'/api/episodes/{episode_id}',
        'httpMethod': 'GET',
        'headers': dict(request.headers),
        'queryStringParameters': request.args.to_dict()
    }
    response = handle_request(event)

    # Lambda形式のレスポンスをFlask形式に変換
    return (
        response.get('body', '{}'),
        response.get('statusCode', 200),
        response.get('headers', {})
    )


@app.route('/audio/<path:filename>', methods=['GET'])
def serve_audio(filename):
    """音声ファイル配信エンドポイント"""
    return send_from_directory(LOCAL_AUDIO_DIR, filename)


@app.route('/health', methods=['GET'])
def health_check():
    """ヘルスチェックエンドポイント"""
    return jsonify({"status": "OK", "service": "news-audio-api"})


@app.after_request
def add_cors_headers(response):
    """CORS対応ヘッダーを追加"""
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
    response.headers.add('Access-Control-Allow-Methods', 'GET, OPTIONS')
    return response


def ensure_directories():
    """ディレクトリが存在するか確認するのみで、作成は行わない"""
    # local_dataとlocal_audioディレクトリは別途作成されることを前提
    if not os.path.exists(LOCAL_DATA_DIR):
        logger.warning(f"データディレクトリが見つかりません: {LOCAL_DATA_DIR}")

    if not os.path.exists(LOCAL_AUDIO_DIR):
        logger.warning(f"音声ファイルディレクトリが見つかりません: {LOCAL_AUDIO_DIR}")

    # エピソード一覧ファイルの存在確認のみを行う
    episodes_list_file = os.path.join(LOCAL_DATA_DIR, "episodes_list.json")
    if not os.path.exists(episodes_list_file):
        logger.warning(f"エピソード一覧ファイルが見つかりません: {episodes_list_file}")


if __name__ == '__main__':
    ensure_directories()
    logger.info(f"ローカルサーバーを起動します: http://{LOCAL_HOST}:{LOCAL_PORT}")
    logger.info(f"データディレクトリ: {LOCAL_DATA_DIR}")
    logger.info(f"音声ファイルディレクトリ: {LOCAL_AUDIO_DIR}")
    app.run(host=LOCAL_HOST, port=LOCAL_PORT, debug=True)
