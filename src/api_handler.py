import json
import logging
import boto3
from botocore.config import Config
from src.config import S3_BUCKET_NAME, AWS_REGION

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# S3クライアント - IAMロールを使用
s3_client = boto3.client(
    's3',
    config=Config(signature_version='s3v4')  # 署名バージョン4を指定
)

# CORS用のレスポンスヘッダー
CORS_HEADERS = {
    'Access-Control-Allow-Origin': '*',  # 本番環境では実際のドメインに制限
    # ヘッダー名を複数行に分割
    'Access-Control-Allow-Headers': (
        'Content-Type,X-Amz-Date,Authorization,'
        'X-Api-Key,X-Amz-Security-Token'
    ),
    'Access-Control-Allow-Methods': 'GET,OPTIONS'  # OPTIONSメソッドも許可
}


def create_response(status_code, body):
    """
    API Gateway Proxy統合レスポンスを生成する
    """
    return {
        'statusCode': status_code,
        'headers': CORS_HEADERS,
        'body': json.dumps(body, ensure_ascii=False)  # 日本語文字化け防止
    }


def get_s3_path_from_url(url, bucket_name):
    """
    S3のURLからオブジェクトキーを抽出する。複数のURL形式に対応。
    """
    if not url:  # URLが空やNoneの場合はNoneを返す
        return None
    try:
        # Try different S3 URL patterns
        patterns = [
            f"https://{bucket_name}.s3.amazonaws.com/",
            # リージョン指定のURL形式 (行分割)
            f"https://{bucket_name}.s3.{AWS_REGION}.amazonaws.com/",
            f"https://s3.{AWS_REGION}.amazonaws.com/{bucket_name}/"  # パス形式
        ]
        for pattern in patterns:
            if url.startswith(pattern):
                # パターンに続く部分がオブジェクトキー
                return url[len(pattern):].split('?')[0]  # クエリパラメータを除去

        # Assume path-style URL if no standard pattern matches
        if f"/{bucket_name}/" in url:
            # バケット名の後からがオブジェクトキー
            return url.split(f"/{bucket_name}/", 1)[1].split('?')[0]

        logger.warning(f"Unrecognized S3 URL format or bucket mismatch: {url}")
        return None
    except Exception as e:
        logger.error(f"Error extracting S3 path from URL '{url}': {str(e)}")
        return None


def generate_presigned_url(bucket_name, object_key, expiration=3600):
    """
    S3オブジェクトへの署名付きURLを生成する。
    オブジェクトキーがない場合はNoneを返す。
    """
    if not object_key:
        logger.warning("generate_presigned_url called with empty or None "
                       "object_key")
        return None  # オブジェクトキーが無効な場合はNoneを返す
    try:
        presigned_url = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': bucket_name,
                'Key': object_key
            },
            ExpiresIn=expiration  # 有効期限（秒）
        )
        # logger.debug(f"Generated presigned URL for {object_key}: "
        #                f"{presigned_url}")
        return presigned_url
    except Exception as e:
        # エラー発生時はログ記録し、Noneを返す
        logger.error(f"Error generating presigned URL for bucket "
                     f"'{bucket_name}', key '{object_key}': {str(e)}")
        return None


def get_episodes_list(page=1, limit=10):
    """
    エピソード一覧を取得する（ページネーション対応）。
    現状はエピソードの基本情報のみを返す。署名付きURLは含めない。
    """
    # TODO: シームレス再生対応後のエピソードリストの形式を検討。
    #       キャッシュ戦略も検討（例: ETag, Last-Modifiedヘッダー）
    try:
        # S3からエピソードリストJSONを取得
        response = s3_client.get_object(
            Bucket=S3_BUCKET_NAME,
            Key='data/episodes_list.json'  # エピソードリストのキーは固定と仮定
        )

        episodes_list_data = json.loads(
            response['Body'].read().decode('utf-8'))

        # 日付（例: 'episode_id' や 'created_at'）で降順ソート
        try:
            episodes_list_data.sort(
                key=lambda x: x.get('episode_id', '0000-00-00'), reverse=True
            )
        except Exception as sort_e:
            logger.warning(f"Could not sort episodes_list.json: {sort_e}")

        # ページネーション処理
        total_episodes = len(episodes_list_data)
        total_pages = (total_episodes + limit - 1) // limit  # ページ数計算

        # 1ベースのページ番号を0ベースのインデックスに変換
        start_idx = (page - 1) * limit
        end_idx = min(start_idx + limit, total_episodes)  # スライス終端

        # 範囲外のページが指定された場合の考慮
        if page < 1 or start_idx >= total_episodes:
            paginated_episodes_data = []  # 空リストを返す
            # ページ番号を範囲内に補正
            page = max(1, min(page, total_pages)) if total_pages > 0 else 1
        else:
            paginated_episodes_data = episodes_list_data[start_idx:end_idx]

        # レスポンスに含めるエピソード情報を整形
        processed_episodes = []
        for episode in paginated_episodes_data:
            processed_episodes.append({
                "episode_id": episode.get("episode_id"),
                "title": episode.get("title"),
                "created_at": episode.get("created_at"),
            })

        # エピソードリストがない場合のレスポンスを修正
        response_data = {
            'episodes': processed_episodes,
            'totalPages': total_pages,
            'currentPage': page,
            'totalEpisodes': total_episodes
        }
        return create_response(200, response_data)

    except s3_client.exceptions.NoSuchKey:
        logger.error("episodes_list.json not found in S3.")
        # エピソードリストがない場合は空のリストを返す
        empty_response = {
            'episodes': [], 'totalPages': 0, 'currentPage': 1, 'totalEpisodes': 0
        }
        return create_response(200, empty_response)
    except Exception as e:
        logger.error(f"Error getting episode list: {str(e)}", exc_info=True)
        error_response = {'error': 'Failed to retrieve episode list'}
        return create_response(500, error_response)


def get_episode(episode_id):
    """
    特定のエピソードのメタデータと再生リスト（署名付きURL付き）を取得する
    """
    try:
        # S3からエピソードデータJSONを取得
        s3_key = f'data/episodes/episode_{episode_id}.json'
        logger.info(f"Fetching episode data from S3 bucket "
                    f"'{S3_BUCKET_NAME}' with key: {s3_key}")
        response = s3_client.get_object(
            Bucket=S3_BUCKET_NAME,
            Key=s3_key
        )

        episode_data = json.loads(response['Body'].read().decode('utf-8'))
        logger.info(f"Successfully loaded episode data for {episode_id}")

        playlist = []  # 再生リスト
        processed_articles = []  # 処理済み記事リスト（署名付きURL含む）

        # --- プレイリストと記事情報の構築 ---

        # 1. エピソードイントロ音声
        intro_audio_url = episode_data.get('intro_audio_url', '')
        intro_audio_key = get_s3_path_from_url(intro_audio_url, S3_BUCKET_NAME)
        intro_presigned_url = generate_presigned_url(
            S3_BUCKET_NAME, intro_audio_key
        )
        if intro_presigned_url:
            playlist.append({
                "type": "intro",
                "audio_url": intro_presigned_url
            })
            logger.debug(f"Added intro audio to playlist for {episode_id}")
        else:
            # イントロ音声がない、またはURL生成に失敗した場合のログ
            logger.warning(
                f"Intro audio URL missing, invalid, or presigning failed "
                f"for episode {episode_id}. URL: '{intro_audio_url}', "
                f"Key: '{intro_audio_key}'")

        # 2. 記事関連音声 (イントロ、本体、トランジション)
        articles = episode_data.get('articles', [])  # 記事リスト取得、なければ空リスト
        num_articles = len(articles)
        logger.info(
            f"Processing {num_articles} articles for episode {episode_id}")

        # トランジション音声URLのリストを取得 (存在しない場合を考慮)
        transition_urls = episode_data.get('transition_audio_urls', [])

        for i, article in enumerate(articles):
            article_id = article.get(
                'id', f'unknown_article_{i+1}')  # IDがなければ仮のID
            logger.info(
                f"Processing article {i+1}/{num_articles} (ID: {article_id})")

            # 2a. 記事イントロ音声
            article_intro_url = article.get('intro_audio_url', '')
            article_intro_key = get_s3_path_from_url(
                article_intro_url, S3_BUCKET_NAME
            )
            article_intro_presigned_url = generate_presigned_url(
                S3_BUCKET_NAME, article_intro_key
            )
            if article_intro_presigned_url:
                playlist.append({
                    "type": "article_intro",
                    "article_id": article_id,
                    "audio_url": article_intro_presigned_url
                })
                logger.debug(
                    f"Added article intro audio to playlist for "
                    f"article {article_id}")
            else:
                logger.warning(
                    f"Article intro audio URL missing, invalid, or "
                    f"presigning failed for article {article_id}. URL: "
                    f"'{article_intro_url}', Key: '{article_intro_key}'")

            # 2b. 記事本体音声
            article_main_url = article.get(
                'audio_url', '')  # 'audio_url' が本体音声と仮定
            article_main_key = get_s3_path_from_url(
                article_main_url, S3_BUCKET_NAME
            )
            article_main_presigned_url = generate_presigned_url(
                S3_BUCKET_NAME, article_main_key
            )
            if article_main_presigned_url:
                playlist.append({
                    "type": "article",
                    "article_id": article_id,
                    "audio_url": article_main_presigned_url
                })
                logger.debug(
                    f"Added article main audio to playlist for "
                    f"article {article_id}")
            else:
                logger.warning(
                    f"Article main audio URL missing, invalid, or "
                    f"presigning failed for article {article_id}. URL: "
                    f"'{article_main_url}', Key: '{article_main_key}'")

            # 2c. トランジション音声 (次の記事がある場合のみ)
            if i < num_articles - 1:
                # transition_urls リストから対応するURLを取得
                if i < len(transition_urls):
                    transition_url = transition_urls[i]
                    transition_key = get_s3_path_from_url(
                        transition_url, S3_BUCKET_NAME
                    )
                    transition_presigned_url = generate_presigned_url(
                        S3_BUCKET_NAME, transition_key
                    )
                    if transition_presigned_url:
                        playlist.append({
                            "type": "transition",
                            # "from_article_id": article_id,
                            # "to_article_id": articles[i+1].get('id'),
                            "audio_url": transition_presigned_url
                        })
                        logger.debug(
                            f"Added transition audio to playlist after "
                            f"article {article_id}")
                    else:
                        # ログメッセージを短縮
                        logger.warning(
                            f"Transition audio failed for art {article_id}. "
                            f"URL: '{transition_url}', Key: '{transition_key}'")
                else:
                    # トランジションURLがリストに足りない場合
                    # ログメッセージを短縮
                    logger.warning(
                        f"Missing transition audio URL after art "
                        f"{article_id} (idx {i})")

            # 処理済み記事リストに追加（署名付きURLを含む）
            processed_articles.append({
                "id": article_id,
                "title": article.get('title'),
                "summary": article.get('summary'),
                "audio_url": article_main_presigned_url,  # 署名付きURL（本体）
                # 署名付きURL（イントロ）
                "intro_audio_url": article_intro_presigned_url,
                "duration": article.get('duration')  # duration は元のデータから取得
            })

        # 3. エピソードアウトロ音声
        outro_audio_url = episode_data.get('outro_audio_url', '')
        outro_audio_key = get_s3_path_from_url(outro_audio_url, S3_BUCKET_NAME)
        outro_presigned_url = generate_presigned_url(
            S3_BUCKET_NAME, outro_audio_key
        )
        if outro_presigned_url:
            playlist.append({
                "type": "outro",
                "audio_url": outro_presigned_url
            })
            logger.debug(f"Added outro audio to playlist for {episode_id}")
        else:
            logger.warning(
                f"Outro audio URL missing, invalid, or presigning failed "
                f"for episode {episode_id}. URL: '{outro_audio_url}', "
                f"Key: '{outro_audio_key}'")

        # --- レスポンスデータの構築 ---
        response_body = {
            "episode_id": episode_id,  # リクエストされたID
            # タイトル取得、なければデフォルト値
            "title": episode_data.get('title', f"Episode {episode_id}"),
            "created_at": episode_data.get('created_at'),  # 作成日時
            "intro_audio_url": intro_presigned_url,  # 署名付きURL（イントロ）
            "outro_audio_url": outro_presigned_url,  # 署名付きURL（アウトロ）
            "playlist": playlist,  # 完成したプレイリスト
            "articles": processed_articles  # 署名付きURLを含む記事リスト
        }

        logger.info(
            f"Successfully generated response for episode {episode_id}")
        return create_response(200, response_body)

    # --- エラーハンドリング ---
    except s3_client.exceptions.NoSuchKey:
        # 指定されたエピソードIDのJSONファイルが存在しない場合
        logger.warning(
            f"Episode data not found in S3 for episode_id: {episode_id} "
            f"(Key: {s3_key})")
        error_response = {'error': f'Episode {episode_id} not found'}
        return create_response(404, error_response)
    except json.JSONDecodeError as json_e:
        # JSONファイルのパースに失敗した場合
        logger.error(
            f"Failed to decode JSON for episode {episode_id} from key "
            f"{s3_key}: {json_e}")
        error_response = {
            'error': f'Invalid data format for episode {episode_id}'
        }
        return create_response(500, error_response)
    except Exception as e:
        # その他の予期せぬエラー
        # スタックトレースもログに出力
        logger.error(
            f"Unexpected error getting episode {episode_id}: {str(e)}",
            exc_info=True)
        error_response = {
            'error': f'Failed to retrieve episode details for {episode_id}'
        }
        return create_response(500, error_response)

# --- 以下の関数は現状維持または削除検討 ---

# def get_article_summary(article_id, language):
#      """記事の要約を取得（現在は未使用）"""
#      # このAPIエンドポイントがまだ必要か確認。
#      # get_episode で記事情報は取得済みのため、不要な可能性が高い。
#      log_msg = (f"Request for article summary (not implemented): "
#                 f"{article_id}, lang: {language}")
#      logger.info(log_msg)
#      # 必要に応じて実装 or 削除
#      msg = ("API endpoint '/articles/{id}/summary' is not implemented "
#             "or deprecated.")
#      return create_response(501, {"message": msg})

# def get_article_audio(article_id, language):
#      """記事の音声を取得（現在は未使用）"""
#      # get_episode で音声URLは取得済みのため、不要な可能性が高い。
#      log_msg = (f"Request for article audio (not implemented): "
#                 f"{article_id}, lang: {language}")
#      logger.info(log_msg)
#      # 必要に応じて実装 or 削除
#      msg = ("API endpoint '/articles/{id}/audio' is not implemented "
#             "or deprecated.")
#      return create_response(501, {"message": msg})

# --- APIリクエストハンドラ ---


def handle_api_request(event, context):
    """
    API Gatewayからのリクエストを処理し、適切なハンドラー関数を呼び出す
    """
    # デフォルト値を設定しつつ、安全に値を取得
    http_method = event.get('httpMethod', 'UNKNOWN')
    path = event.get('path', '/')
    query_params = event.get('queryStringParameters') or {}
    # API Gateway設定でパスパラメータを有効にする必要あり
    path_params = event.get('pathParameters') or {}

    logger.info(f"Handling request: {http_method} {path}")
    logger.debug(f"Query Parameters: {query_params}")
    logger.debug(f"Path Parameters: {path_params}")  # パスパラメータもログ出力

    # --- ルーティング ---

    # OPTIONSメソッドへの対応（CORSプリフライトリクエスト用）
    if http_method == 'OPTIONS':
        logger.info("Responding to OPTIONS request for CORS preflight")
        # 必要なヘッダーを含めて200 OKを返す
        return {
            'statusCode': 200,
            'headers': CORS_HEADERS,
            'body': ''  # ボディは空でよい
        }

    # GET /episodes - エピソード一覧
    if http_method == 'GET' and path == '/episodes':
        try:
            # クエリパラメータ 'page' と 'limit' を整数に変換、デフォルト値とバリデーション
            page = int(query_params.get('page', '1'))
            limit = int(query_params.get('limit', '10'))
            # 不正な値が指定された場合、デフォルト値に戻す
            page = max(1, page)
            limit = max(1, min(limit, 100))  # limitの上限を100に設定する例
            logger.info(
                f"Routing to get_episodes_list (page={page}, limit={limit})")
            return get_episodes_list(page, limit)
        except ValueError:
            logger.warning("Invalid query parameter for page or limit: "
                           f"{query_params}")
            error_msg = ('Invalid page or limit parameter. '
                         'They must be integers.')
            return create_response(400, {'error': error_msg})

    # GET /episodes/{episode_id} - 特定エピソード詳細
    # episode_id をパスパラメータから取得 (API Gateway の設定が必要)
    # パスマッチングを修正 (path_params を使用)
    if http_method == 'GET' and path.startswith('/episodes/') and 'episode_id' in path_params:
        episode_id = path_params['episode_id']
        # episode_id の簡単なバリデーション（例: 空でないか）
        if not episode_id:
            logger.warning("Invalid episode_id in path parameters: "
                           f"{path_params}")
            error_response = {'error': 'Invalid episode ID in path.'}
            return create_response(400, error_response)

        # # オプション: より厳密な形式チェック (例: YYYY-MM-DD)
        # import re
        # if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', episode_id):
        #     logger.warning(f"Invalid episode_id format: {episode_id}")
        #     error_response = {
        #         'error': 'Invalid episode ID format. Expected YYYY-MM-DD.'
        #     }
        #     return create_response(400, error_response)

        logger.info(f"Routing to get_episode (episode_id={episode_id})")
        return get_episode(episode_id)

    # --- 記事単体API（コメントアウト）---
    # if http_method == 'GET' and path.startswith('/articles/'):
    #     article_id_match = re.search(r'/articles/([^/]+)', path)
    #     if article_id_match:
    #         article_id = article_id_match.group(1)
    #         language = query_params.get('lang', 'ja')
    #
    #         if path.endswith('/summary'):
    #             log_msg = (f"Routing to get_article_summary (id={article_id}, "
    #                        f"lang={language})")
    #             logger.info(log_msg)
    #             # return get_article_summary(article_id, language)
    #             return create_response(501, {"message": "Not Implemented"})
    #         elif path.endswith('/audio'):
    #             log_msg = (f"Routing to get_article_audio (id={article_id}, "
    #                        f"lang={language})")
    #             logger.info(log_msg)
    #             # return get_article_audio(article_id, language)
    #             return create_response(501, {"message": "Not Implemented"})
    #
    # --- マッチしない場合 ---
    logger.warning(f"Unsupported route or method: {http_method} {path}")
    return create_response(404, {'error': 'Not Found'})
