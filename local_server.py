import os
import json
import logging
import glob
from flask import Flask, request, send_from_directory, jsonify, Response
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


@app.route('/health', methods=['GET'])
def health_check():
    """ヘルスチェックエンドポイント"""
    return jsonify({"status": "OK", "service": "news-audio-api"})


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
    return Response(
        response=response.get('body', '{}'),
        status=response.get('statusCode', 200),
        headers=response.get('headers', {}),
        mimetype='application/json'
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
    return Response(
        response=response.get('body', '{}'),
        status=response.get('statusCode', 200),
        headers=response.get('headers', {}),
        mimetype='application/json'
    )


@app.route('/audio/<path:filename>', methods=['GET'])
def serve_audio(filename):
    """音声ファイル配信エンドポイント (旧形式)"""
    logger.info(f"Serving audio file: {filename}")
    # 音声ファイルを部分的に読み込む場合のヘッダー設定
    headers = {}
    if request.headers.get('Range'):
        headers['Range'] = request.headers.get('Range')

    audio_path = os.path.join(LOCAL_AUDIO_DIR, filename)
    if not os.path.exists(audio_path):
        logger.warning(f"Audio file not found: {audio_path}")
        return jsonify({"error": f"Audio file {filename} not found"}), 404

    try:
        return send_from_directory(LOCAL_AUDIO_DIR, filename, conditional=True,
                                   as_attachment=False, mimetype='audio/mpeg', headers=headers)
    except Exception as e:
        logger.error(f"Error serving audio file {filename}: {str(e)}")
        return jsonify({"error": f"Error serving audio file: {str(e)}"}), 500


@app.route('/api/articles/<article_id>/audio', methods=['GET'])
def get_article_audio(article_id):
    """記事の音声ファイル配信エンドポイント (本番と同じ形式)"""
    logger.info(f"Requested audio for article: {article_id}")
    language = request.args.get('language', 'ja')

    # まずlocal_audioディレクトリ内のファイルを一覧
    try:
        audio_files = os.listdir(LOCAL_AUDIO_DIR)
        logger.info(f"Available audio files: {audio_files}")
    except Exception as e:
        logger.error(f"Error listing audio directory: {str(e)}")
        audio_files = []

    # 簡単な実装として、article_idがファイル名に含まれるファイルを探す
    matching_files = [
        f for f in audio_files if article_id in f and f.endswith('.mp3')]

    if matching_files:
        filename = matching_files[0]  # 最初に見つかったファイルを使用
        logger.info(f"Found matching audio file: {filename}")

        # 音声ファイルを部分的に読み込む場合のヘッダー設定
        headers = {}
        if request.headers.get('Range'):
            headers['Range'] = request.headers.get('Range')

        return send_from_directory(LOCAL_AUDIO_DIR, filename, conditional=True,
                                   as_attachment=False, mimetype='audio/mpeg', headers=headers)
    else:
        logger.warning(
            f"No matching audio file found for article_id: {article_id}")
        return jsonify({"error": f"Audio file for article {article_id} not found"}), 404


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
