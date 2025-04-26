import json
import os
import logging
import boto3
from botocore.exceptions import ClientError
import traceback

from src.config import (
    IS_LAMBDA, CORS_HEADERS, get_metadata_path, 
    get_episodes_list_path, LOCAL_DATA_DIR, LOCAL_HOST, LOCAL_PORT
)

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# S3クライアント（Lambda環境でのみ初期化）
s3_client = boto3.client('s3') if IS_LAMBDA else None
s3_bucket = os.environ.get('S3_BUCKET', 'news-audio-content')

def build_response(status_code, body):
    """API Gatewayレスポンスの構築
    
    Args:
        status_code: HTTPステータスコード
        body: レスポンスボディ（dict）
        
    Returns:
        dict: API Gatewayレスポンス形式
    """
    return {
        'statusCode': status_code,
        'headers': CORS_HEADERS,
        'body': json.dumps(body, ensure_ascii=False)
    }

def get_episodes():
    """全エピソード一覧を取得
    
    Returns:
        dict: APIレスポンス
    """
    try:
        episodes_path = get_episodes_list_path()
        
        if IS_LAMBDA:
            # AWS環境: S3からデータ取得
            try:
                response = s3_client.get_object(Bucket=s3_bucket, Key=episodes_path)
                episodes = json.loads(response['Body'].read().decode('utf-8'))
            except ClientError as e:
                logger.error(f"S3からのエピソード一覧取得エラー: {str(e)}")
                return build_response(404, {"error": "Episodes list not found"})
        else:
            # ローカル環境: ファイルシステムからデータ取得
            try:
                with open(episodes_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                # episodes_list.jsonの場合は配列形式、episodes.jsonは{"episodes": []}形式
                if isinstance(data, list):
                    episodes = {"episodes": data}
                else:
                    episodes = data
            except FileNotFoundError:
                logger.error(f"エピソード一覧ファイルが見つかりません: {episodes_path}")
                # ファイルが見つからない場合は空のリストを返す
                episodes = {"episodes": []}
        
        return build_response(200, episodes)
    
    except Exception as e:
        logger.error(f"エピソード一覧取得エラー: {str(e)}")
        logger.error(traceback.format_exc())
        return build_response(500, {"error": "Internal server error"})

def get_episode(episode_id):
    """特定のエピソード詳細を取得
    
    Args:
        episode_id: エピソードID
        
    Returns:
        dict: APIレスポンス
    """
    try:
        metadata_path = get_metadata_path(episode_id)
        
        if IS_LAMBDA:
            # AWS環境: S3からデータ取得
            try:
                response = s3_client.get_object(Bucket=s3_bucket, Key=metadata_path)
                episode = json.loads(response['Body'].read().decode('utf-8'))
            except ClientError as e:
                logger.error(f"S3からのエピソード取得エラー: {str(e)}")
                return build_response(404, {"error": f"Episode {episode_id} not found"})
        else:
            # ローカル環境: ファイルシステムからデータ取得
            try:
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    episode = json.load(f)
                    
                # S3のURLをローカル環境用に置き換える
                for article in episode.get('articles', []):
                    if 'audio_url' in article and article['audio_url'].startswith('https://'):
                        # S3 URLからファイル名を抽出
                        filename = article['audio_url'].split('/')[-1]
                        article['audio_url'] = f"http://{LOCAL_HOST}:{LOCAL_PORT}/audio/{filename}"
                
                # ナレーション音声URLの置き換え
                if 'intro_audio_url' in episode and episode['intro_audio_url'].startswith('https://'):
                    filename = episode['intro_audio_url'].split('/')[-1]
                    episode['intro_audio_url'] = f"http://{LOCAL_HOST}:{LOCAL_PORT}/audio/{filename}"
                    
                if 'outro_audio_url' in episode and episode['outro_audio_url'].startswith('https://'):
                    filename = episode['outro_audio_url'].split('/')[-1]
                    episode['outro_audio_url'] = f"http://{LOCAL_HOST}:{LOCAL_PORT}/audio/{filename}"
                    
            except FileNotFoundError:
                logger.error(f"エピソードファイルが見つかりません: {metadata_path}")
                return build_response(404, {"error": f"Episode {episode_id} not found"})
        
        return build_response(200, episode)
    
    except Exception as e:
        logger.error(f"エピソード取得エラー: {str(e)}")
        logger.error(traceback.format_exc())
        return build_response(500, {"error": "Internal server error"})

def handle_request(event, context=None):
    """API Gatewayリクエストハンドラー
    
    Args:
        event: API Gatewayイベント
        context: Lambda実行コンテキスト
        
    Returns:
        dict: API Gatewayレスポンス
    """
    try:
        # パスパラメータ取得
        path = event.get('path', '').rstrip('/')
        http_method = event.get('httpMethod', 'GET')
        
        # CORSプリフライトリクエスト対応
        if http_method == 'OPTIONS':
            return build_response(200, {})
        
        # GET以外のメソッドは拒否
        if http_method != 'GET':
            return build_response(405, {"error": "Method not allowed"})
        
        # パスによるルーティング
        if path == '/episodes' or path == '/api/episodes':
            return get_episodes()
        elif path.startswith('/episodes/') or path.startswith('/api/episodes/'):
            episode_id = path.split('/')[-1]
            return get_episode(episode_id)
        else:
            return build_response(404, {"error": "Not found"})
    
    except Exception as e:
        logger.error(f"リクエスト処理エラー: {str(e)}")
        logger.error(traceback.format_exc())
        return build_response(500, {"error": "Internal server error"})
