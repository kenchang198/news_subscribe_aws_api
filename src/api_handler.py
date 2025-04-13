import json
import os
import logging
import boto3
import re
from botocore.config import Config
from src.config import S3_BUCKET_NAME, AWS_REGION, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# S3クライアント - IAMロールを使用
s3_client = boto3.client(
    's3',
    config=Config(signature_version='s3v4')
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


def get_s3_path_from_url(url, bucket_name):
    """
    S3のURLからオブジェクトキーを抽出する
    
    Args:
        url (str): S3のURL
        bucket_name (str): S3バケット名
        
    Returns:
        str: オブジェクトキー
    """
    try:
        # 標準的なAmazon S3のURL形式
        standard_pattern = f"https://{bucket_name}.s3.amazonaws.com/"
        if standard_pattern in url:
            return url.split(standard_pattern)[1]
        
        # リージョン指定のURL形式
        region_pattern = f"https://{bucket_name}.s3.ap-northeast-1.amazonaws.com/"
        if region_pattern in url:
            return url.split(region_pattern)[1]
        
        # もう一つのバリエーション
        alt_pattern = f"https://s3.ap-northeast-1.amazonaws.com/{bucket_name}/"
        if alt_pattern in url:
            return url.split(alt_pattern)[1]
        
        # 新しいバリエーション
        new_pattern = f"https://{bucket_name}.s3.{AWS_REGION}.amazonaws.com/"
        if new_pattern in url:
            return url.split(new_pattern)[1]
        
        logger.warning(f"認識できないS3のURL形式: {url}")
        return None
    except Exception as e:
        logger.error(f"S3パス抽出エラー: {str(e)}")
        return None


def generate_presigned_url(bucket_name, object_key, expiration=3600):
    """
    S3オブジェクトへの署名付きURLを生成する
    
    Args:
        bucket_name (str): S3バケット名
        object_key (str): S3オブジェクトキー
        expiration (int): URLの有効期限（秒）
        
    Returns:
        str: 署名付きURL
    """
    try:
        presigned_url = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': bucket_name,
                'Key': object_key
            },
            ExpiresIn=expiration
        )
        return presigned_url
    except Exception as e:
        logger.error(f"署名付きURL生成エラー: {str(e)}")
        return None


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
        
        # 各エピソードに署名付きURLを追加
        for episode in paginated_episodes:
            # 日本語音声のPresigned URL（既存URLがある場合は置き換え）
            if 'japanese_audio_url' in episode and episode['japanese_audio_url']:
                object_key = get_s3_path_from_url(episode['japanese_audio_url'], S3_BUCKET_NAME)
                if object_key:
                    episode['japanese_audio_url'] = generate_presigned_url(
                        S3_BUCKET_NAME,
                        object_key,
                        expiration=3600  # 1時間有効
                    )
            # 古い方式との互換性
            elif 'japanese_audio_path' in episode and episode['japanese_audio_path']:
                episode['japanese_audio_url'] = generate_presigned_url(
                    S3_BUCKET_NAME,
                    episode['japanese_audio_path'],
                    expiration=3600  # 1時間有効
                )
            
            # 英語音声のPresigned URL（既存URLがある場合は置き換え）
            if 'english_audio_url' in episode and episode['english_audio_url']:
                object_key = get_s3_path_from_url(episode['english_audio_url'], S3_BUCKET_NAME)
                if object_key:
                    episode['english_audio_url'] = generate_presigned_url(
                        S3_BUCKET_NAME,
                        object_key,
                        expiration=3600  # 1時間有効
                    )
            # 古い方式との互換性
            elif 'english_audio_path' in episode and episode['english_audio_path']:
                episode['english_audio_url'] = generate_presigned_url(
                    S3_BUCKET_NAME,
                    episode['english_audio_path'],
                    expiration=3600  # 1時間有効
                )

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
        
        # エピソード全体の音声ファイルに署名付きURLを追加
        if 'japanese_audio_url' in episode_data and episode_data['japanese_audio_url']:
            object_key = get_s3_path_from_url(episode_data['japanese_audio_url'], S3_BUCKET_NAME)
            if object_key:
                episode_data['japanese_audio_url'] = generate_presigned_url(
                    S3_BUCKET_NAME,
                    object_key,
                    expiration=3600  # 1時間有効
                )
        # 古い方式との互換性
        elif 'japanese_audio_path' in episode_data and episode_data['japanese_audio_path']:
            episode_data['japanese_audio_url'] = generate_presigned_url(
                S3_BUCKET_NAME,
                episode_data['japanese_audio_path'],
                expiration=3600  # 1時間有効
            )
        
        if 'english_audio_url' in episode_data and episode_data['english_audio_url']:
            object_key = get_s3_path_from_url(episode_data['english_audio_url'], S3_BUCKET_NAME)
            if object_key:
                episode_data['english_audio_url'] = generate_presigned_url(
                    S3_BUCKET_NAME,
                    object_key,
                    expiration=3600  # 1時間有効
                )
        # 古い方式との互換性
        elif 'english_audio_path' in episode_data and episode_data['english_audio_path']:
            episode_data['english_audio_url'] = generate_presigned_url(
                S3_BUCKET_NAME,
                episode_data['english_audio_path'],
                expiration=3600  # 1時間有効
            )
        
        # 各記事の音声ファイルにも署名付きURLを追加
        if 'articles' in episode_data:
            for article in episode_data['articles']:
                # 日本語音声
                if 'japanese_audio_url' in article and article['japanese_audio_url']:
                    object_key = get_s3_path_from_url(article['japanese_audio_url'], S3_BUCKET_NAME)
                    if object_key:
                        article['japanese_audio_url'] = generate_presigned_url(
                            S3_BUCKET_NAME,
                            object_key,
                            expiration=3600  # 1時間有効
                        )
                # 古い方式との互換性
                elif 'japanese_audio_path' in article and article['japanese_audio_path']:
                    article['japanese_audio_url'] = generate_presigned_url(
                        S3_BUCKET_NAME,
                        article['japanese_audio_path'],
                        expiration=3600  # 1時間有効
                    )
                
                # 英語音声
                if 'english_audio_url' in article and article['english_audio_url']:
                    object_key = get_s3_path_from_url(article['english_audio_url'], S3_BUCKET_NAME)
                    if object_key:
                        article['english_audio_url'] = generate_presigned_url(
                            S3_BUCKET_NAME,
                            object_key,
                            expiration=3600  # 1時間有効
                        )
                # 古い方式との互換性
                elif 'english_audio_path' in article and article['english_audio_path']:
                    article['english_audio_url'] = generate_presigned_url(
                        S3_BUCKET_NAME,
                        article['english_audio_path'],
                        expiration=3600  # 1時間有効
                    )

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
    記事の音声URLを取得する（署名付きURLを生成）
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
                # 言語に応じた音声の署名付きURLを生成して返す
                if language == 'en':
                    if 'english_audio_url' in article and article['english_audio_url']:
                        object_key = get_s3_path_from_url(article['english_audio_url'], S3_BUCKET_NAME)
                        if object_key:
                            presigned_url = generate_presigned_url(
                                S3_BUCKET_NAME,
                                object_key,
                                expiration=3600  # 1時間有効
                            )
                            return create_response(200, {'audioUrl': presigned_url})
                    # 古い方式との互換性
                    elif 'english_audio_path' in article and article['english_audio_path']:
                        presigned_url = generate_presigned_url(
                            S3_BUCKET_NAME,
                            article['english_audio_path'],
                            expiration=3600  # 1時間有効
                        )
                        return create_response(200, {'audioUrl': presigned_url})
                    else:
                        return create_response(404, {'error': '英語音声ファイルが見つかりません'})
                else:
                    if 'japanese_audio_url' in article and article['japanese_audio_url']:
                        object_key = get_s3_path_from_url(article['japanese_audio_url'], S3_BUCKET_NAME)
                        if object_key:
                            presigned_url = generate_presigned_url(
                                S3_BUCKET_NAME,
                                object_key,
                                expiration=3600  # 1時間有効
                            )
                            return create_response(200, {'audioUrl': presigned_url})
                    # 古い方式との互換性
                    elif 'japanese_audio_path' in article and article['japanese_audio_path']:
                        presigned_url = generate_presigned_url(
                            S3_BUCKET_NAME,
                            article['japanese_audio_path'],
                            expiration=3600  # 1時間有効
                        )
                        return create_response(200, {'audioUrl': presigned_url})
                    else:
                        return create_response(404, {'error': '日本語音声ファイルが見つかりません'})

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
