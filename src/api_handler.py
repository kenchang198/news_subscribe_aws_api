import json
import os
import logging
import boto3
import re
from src.config import S3_BUCKET_NAME, AWS_REGION, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# S3クライアント - 明示的に認証情報を指定
s3_client = boto3.client(
    's3'
)

# CORS用のレスポンスヘッダー
CORS_HEADERS = {
    'Access-Control-Allow-Origin': '*',  # 本番環境では実際のドメインに制限
    'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
    'Access-Control-Allow-Methods': 'GET,OPTIONS'
}


def create_response(status_code, body):
    """
    レスポンスを生成する
    """
    return {
        'statusCode': status_code,
        'headers': CORS_HEADERS,
        'body': json.dumps(body, ensure_ascii=False)
    }


def get_episodes_list(page=1, limit=10):
    """
    エピソード一覧を取得する
    """
    try:
        # S3からエピソードリストを取得
        response = s3_client.get_object(
            Bucket=S3_BUCKET_NAME,
            Key='data/episodes_list.json'
        )

        episodes_list = json.loads(response['Body'].read().decode('utf-8'))

        # ページネーション
        total_episodes = len(episodes_list)
        total_pages = (total_episodes + limit - 1) // limit  # 切り上げ

        start_idx = (page - 1) * limit
        end_idx = min(start_idx + limit, total_episodes)

        paginated_episodes = episodes_list[start_idx:end_idx]

        return create_response(200, {
            'episodes': paginated_episodes,
            'totalPages': total_pages,
            'currentPage': page,
            'totalEpisodes': total_episodes
        })

    except Exception as e:
        logger.error(f"エピソードリスト取得エラー: {str(e)}")
        return create_response(500, {'error': 'エピソードリストの取得に失敗しました'})


def get_episode(episode_id):
    """
    特定のエピソードを取得する
    """
    try:
        # S3からエピソードデータを取得
        response = s3_client.get_object(
            Bucket=S3_BUCKET_NAME,
            Key=f'data/episodes/episode_{episode_id}.json'
        )

        episode_data = json.loads(response['Body'].read().decode('utf-8'))

        return create_response(200, episode_data)

    except Exception as e:
        logger.error(f"エピソード取得エラー: {str(e)}")
        return create_response(404, {'error': 'エピソードが見つかりません'})


def get_article_summary(article_id, language):
    """
    記事の要約を取得する
    """
    try:
        # article_idからepisode_idを抽出する正規表現
        # 例: article_20230101_001 から 20230101 を抽出
        match = re.search(r'article_(\d+)_', article_id)
        if not match:
            return create_response(400, {'error': '不正なarticle_idです'})

        episode_id = match.group(1)

        # S3からエピソードデータを取得
        response = s3_client.get_object(
            Bucket=S3_BUCKET_NAME,
            Key=f'data/episodes/episode_{episode_id}.json'
        )

        episode_data = json.loads(response['Body'].read().decode('utf-8'))

        # 該当記事を検索
        for article in episode_data['articles']:
            if article['id'] == article_id:
                # 言語に応じた要約を返す
                if language == 'en':
                    return create_response(200, {'summary': article['english_summary']})
                else:
                    return create_response(200, {'summary': article['japanese_summary']})

        return create_response(404, {'error': '記事が見つかりません'})

    except Exception as e:
        logger.error(f"記事要約取得エラー: {str(e)}")
        return create_response(500, {'error': '記事要約の取得に失敗しました'})


def get_article_audio(article_id, language):
    """
    記事の音声URLを取得する
    """
    try:
        # article_idからepisode_idを抽出する正規表現
        match = re.search(r'article_(\d+)_', article_id)
        if not match:
            return create_response(400, {'error': '不正なarticle_idです'})

        episode_id = match.group(1)

        # S3からエピソードデータを取得
        response = s3_client.get_object(
            Bucket=S3_BUCKET_NAME,
            Key=f'data/episodes/episode_{episode_id}.json'
        )

        episode_data = json.loads(response['Body'].read().decode('utf-8'))

        # 該当記事を検索
        for article in episode_data['articles']:
            if article['id'] == article_id:
                # 言語に応じた音声URLを返す
                if language == 'en':
                    return create_response(200, {'audioUrl': article['english_audio_url']})
                else:
                    return create_response(200, {'audioUrl': article['japanese_audio_url']})

        return create_response(404, {'error': '記事が見つかりません'})

    except Exception as e:
        logger.error(f"記事音声URL取得エラー: {str(e)}")
        return create_response(500, {'error': '記事音声URLの取得に失敗しました'})


def handle_api_request(event, context):
    """
    APIリクエストを処理する
    """
    # プレフライトリクエスト（OPTIONS）の処理
    if event['httpMethod'] == 'OPTIONS':
        return create_response(200, {})

    # パスとクエリパラメータの取得
    path = event['path']
    query_params = event.get('queryStringParameters', {}) or {}

    # エンドポイントに応じた処理
    if path == '/api/episodes':
        # エピソード一覧の取得
        page = int(query_params.get('page', 1))
        limit = int(query_params.get('limit', 10))
        return get_episodes_list(page, limit)

    elif path.startswith('/api/episodes/'):
        # 特定のエピソードの取得
        episode_id = path.split('/')[-1]
        return get_episode(episode_id)

    elif path.startswith('/api/articles/') and path.endswith('/summary'):
        # 記事の要約の取得
        article_id = path.split('/')[-2]
        language = query_params.get('language', 'ja')
        return get_article_summary(article_id, language)

    elif path.startswith('/api/articles/') and path.endswith('/audio'):
        # 記事の音声URLの取得
        article_id = path.split('/')[-2]
        language = query_params.get('language', 'ja')
        return get_article_audio(article_id, language)

    else:
        # 未対応のエンドポイント
        return create_response(404, {'error': 'エンドポイントが見つかりません'})
