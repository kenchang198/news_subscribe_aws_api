import json
import os
import argparse
from flask import Flask, request, jsonify
from flask_cors import CORS
from src.api_handler import handle_api_request

# Flaskアプリケーションの初期化
app = Flask(__name__)
CORS(app)  # CORSを有効化（開発環境用）

# APIルート
@app.route('/api/episodes', methods=['GET'])
def get_episodes():
    # クエリパラメータの取得
    page = request.args.get('page', '1')
    limit = request.args.get('limit', '10')
    
    # APIイベントの作成
    event = {
        'httpMethod': 'GET',
        'path': '/api/episodes',
        'queryStringParameters': {
            'page': page,
            'limit': limit
        }
    }
    
    # API処理
    response = handle_api_request(event, None)
    
    # レスポンスの返却
    return jsonify(json.loads(response['body'])), response['statusCode']

@app.route('/api/episodes/<episode_id>', methods=['GET'])
def get_episode(episode_id):
    # APIイベントの作成
    event = {
        'httpMethod': 'GET',
        'path': f'/api/episodes/{episode_id}',
        'queryStringParameters': {}
    }
    
    # API処理
    response = handle_api_request(event, None)
    
    # レスポンスの返却
    return jsonify(json.loads(response['body'])), response['statusCode']

@app.route('/api/articles/<article_id>/summary', methods=['GET'])
def get_article_summary(article_id):
    # クエリパラメータの取得
    language = request.args.get('language', 'ja')
    
    # APIイベントの作成
    event = {
        'httpMethod': 'GET',
        'path': f'/api/articles/{article_id}/summary',
        'queryStringParameters': {
            'language': language
        }
    }
    
    # API処理
    response = handle_api_request(event, None)
    
    # レスポンスの返却
    return jsonify(json.loads(response['body'])), response['statusCode']

@app.route('/api/articles/<article_id>/audio', methods=['GET'])
def get_article_audio(article_id):
    # クエリパラメータの取得
    language = request.args.get('language', 'ja')
    
    # APIイベントの作成
    event = {
        'httpMethod': 'GET',
        'path': f'/api/articles/{article_id}/audio',
        'queryStringParameters': {
            'language': language
        }
    }
    
    # API処理
    response = handle_api_request(event, None)
    
    # レスポンスの返却
    return jsonify(json.loads(response['body'])), response['statusCode']

# 開発用サーバー起動
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='ローカルAPI開発サーバー')
    parser.add_argument('--port', type=int, default=3001, help='サーバーポート（デフォルト: 3001）')
    args = parser.parse_args()
    
    print(f"ローカルAPI開発サーバーを起動しています... http://localhost:{args.port}/")
    app.run(host='0.0.0.0', port=args.port, debug=True)
