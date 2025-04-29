import json
import os
import logging
import boto3
from botocore.exceptions import ClientError
import traceback

from src.config import (
    IS_LAMBDA, CORS_HEADERS, get_episodes_data_path,
    get_episodes_list_path, get_metadata_path,
    LOCAL_DATA_DIR, LOCAL_HOST, LOCAL_PORT, S3_BUCKET
)
from src.audio_proxy import lambda_handler as audio_proxy_handler

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# S3クライアント（Lambda環境でのみ初期化）
s3_client = boto3.client('s3') if IS_LAMBDA else None


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
                response = s3_client.get_object(
                    Bucket=S3_BUCKET, Key=episodes_path)
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
        episodes_data_path = get_episodes_data_path(episode_id)

        if IS_LAMBDA:
            # AWS環境: S3からデータ取得
            try:
                response = s3_client.get_object(
                    Bucket=S3_BUCKET, Key=episodes_data_path)
                episode = json.loads(response['Body'].read().decode('utf-8'))

                # S3バケットURLを署名付きURLまたはAPI Gateway経由のURLに変換
                # 記事の音声URL変換
                from src.config import build_audio_url
                logger.info("エピソード音声URL変換処理を開始")
                
                # 記事の音声URL変換
                for article in episode.get('articles', []):
                    # 通常の音声URL変換
                    if 'audio_url' in article and article['audio_url']:
                        original_url = article['audio_url']
                        
                        # 既に署名付きURLの場合はスキップ
                        if isinstance(original_url, str) and original_url.startswith(('https://', 'http://')) and 'X-Amz-Signature=' in original_url:
                            logger.info(f"既に署名付きURLが設定されています: {original_url}")
                            continue
                            
                        # S3 URLからキーを抽出
                        if isinstance(original_url, str) and original_url.startswith('https://') and f"{S3_BUCKET}.s3.amazonaws.com/" in original_url:
                            audio_key = original_url.split(f"{S3_BUCKET}.s3.amazonaws.com/")[-1]
                            logger.info(f"S3 URLからキー抽出: {audio_key}")
                            
                            # 署名付きURLまたはAPI Gateway経由のURLを生成
                            article['audio_url'] = build_audio_url(audio_key)
                            logger.info(f"音声URL変換結果: {article['audio_url']}")

                    # 英語音声のURL変換
                    if 'english_audio_url' in article and article['english_audio_url']:
                        original_url = article['english_audio_url']
                        
                        # 既に署名付きURLの場合はスキップ
                        if isinstance(original_url, str) and original_url.startswith(('https://', 'http://')) and 'X-Amz-Signature=' in original_url:
                            logger.info(f"既に署名付きURLが設定されています（英語）: {original_url}")
                            continue
                            
                        # S3 URLからキーを抽出
                        if isinstance(original_url, str) and original_url.startswith('https://') and f"{S3_BUCKET}.s3.amazonaws.com/" in original_url:
                            audio_key = original_url.split(f"{S3_BUCKET}.s3.amazonaws.com/")[-1]
                            logger.info(f"S3 URLからキー抽出（英語）: {audio_key}")
                            
                            # 署名付きURLまたはAPI Gateway経由のURLを生成
                            article['english_audio_url'] = build_audio_url(audio_key)
                            logger.info(f"英語音声URL変換結果: {article['english_audio_url']}")

                # イントロ音声のURL変換
                if 'intro_audio_url' in episode and episode['intro_audio_url']:
                    original_url = episode['intro_audio_url']
                    
                    # 既に署名付きURLの場合はスキップ
                    if not (isinstance(original_url, str) and original_url.startswith(('https://', 'http://')) and 'X-Amz-Signature=' in original_url):
                        # S3 URLからキーを抽出
                        if isinstance(original_url, str) and original_url.startswith('https://') and f"{S3_BUCKET}.s3.amazonaws.com/" in original_url:
                            audio_key = original_url.split(f"{S3_BUCKET}.s3.amazonaws.com/")[-1]
                            logger.info(f"S3 URLからキー抽出（イントロ）: {audio_key}")
                            
                            # 署名付きURLまたはAPI Gateway経由のURLを生成
                            episode['intro_audio_url'] = build_audio_url(audio_key)
                            logger.info(f"イントロURL変換結果: {episode['intro_audio_url']}")

                # アウトロ音声のURL変換
                if 'outro_audio_url' in episode and episode['outro_audio_url']:
                    original_url = episode['outro_audio_url']
                    
                    # 既に署名付きURLの場合はスキップ
                    if not (isinstance(original_url, str) and original_url.startswith(('https://', 'http://')) and 'X-Amz-Signature=' in original_url):
                        # S3 URLからキーを抽出
                        if isinstance(original_url, str) and original_url.startswith('https://') and f"{S3_BUCKET}.s3.amazonaws.com/" in original_url:
                            audio_key = original_url.split(f"{S3_BUCKET}.s3.amazonaws.com/")[-1]
                            logger.info(f"S3 URLからキー抽出（アウトロ）: {audio_key}")
                            
                            # 署名付きURLまたはAPI Gateway経由のURLを生成
                            episode['outro_audio_url'] = build_audio_url(audio_key)
                            logger.info(f"アウトロURL変換結果: {episode['outro_audio_url']}")
                
                logger.info("エピソード音声URL変換処理を完了")

            except ClientError as e:
                logger.error(f"S3からのエピソード取得エラー: {str(e)}")
                return build_response(404, {"error": f"Episode {episode_id} not found"})
        else:
            # ローカル環境: ファイルシステムからデータ取得
            try:
                with open(episodes_data_path, 'r', encoding='utf-8') as f:
                    episode = json.load(f)

                # S3のURLをローカル環境用に置き換える
                for article in episode.get('articles', []):
                    if 'audio_url' in article and article['audio_url'] and article['audio_url'].startswith('https://'):
                        # S3 URLからファイル名を抽出
                        filename = article['audio_url'].split('/')[-1]
                        article['audio_url'] = f"http://{LOCAL_HOST}:{LOCAL_PORT}/audio/{filename}"

                # ナレーション音声URLの置き換え
                if 'intro_audio_url' in episode and episode['intro_audio_url'] and episode['intro_audio_url'].startswith('https://'):
                    filename = episode['intro_audio_url'].split('/')[-1]
                    episode['intro_audio_url'] = f"http://{LOCAL_HOST}:{LOCAL_PORT}/audio/{filename}"

                if 'outro_audio_url' in episode and episode['outro_audio_url'] and episode['outro_audio_url'].startswith('https://'):
                    filename = episode['outro_audio_url'].split('/')[-1]
                    episode['outro_audio_url'] = f"http://{LOCAL_HOST}:{LOCAL_PORT}/audio/{filename}"

            except FileNotFoundError:
                logger.error(f"エピソードファイルが見つかりません: {episodes_data_path}")
                return build_response(404, {"error": f"Episode {episode_id} not found"})

        return build_response(200, episode)

    except Exception as e:
        logger.error(f"エピソード取得エラー: {str(e)}")
        logger.error(traceback.format_exc())
        return build_response(500, {"error": "Internal server error"})


def get_article_audio(article_id, language='ja'):
    """記事の音声ファイルURLを取得

    Args:
        article_id: 記事ID
        language: 言語（デフォルト: ja）

    Returns:
        dict: APIレスポンス
    """
    try:
        # 全エピソードファイルから記事IDに対応する音声ファイルを探す
        if IS_LAMBDA:
            # S3からエピソードリストを取得
            try:
                episodes_path = get_episodes_list_path()
                response = s3_client.get_object(
                    Bucket=S3_BUCKET, Key=episodes_path)
                episodes_data = json.loads(
                    response['Body'].read().decode('utf-8'))

                # episodes形式に統一
                if isinstance(episodes_data, list):
                    episodes = episodes_data
                else:
                    episodes = episodes_data.get('episodes', [])

                # 各エピソードを検索
                for episode in episodes:
                    episode_id = episode.get('episode_id')
                    if not episode_id:
                        continue

                    # エピソード詳細を取得
                    try:
                        episodes_data_path = get_episodes_data_path(episode_id)
                        response = s3_client.get_object(
                            Bucket=S3_BUCKET, Key=episodes_data_path)
                        episode_detail = json.loads(
                            response['Body'].read().decode('utf-8'))

                        # 記事を検索
                        for article in episode_detail.get('articles', []):
                            if article.get('id') == article_id:
                                # 言語に応じた音声ファイルURLを返す
                                from src.config import build_audio_url

                                if language == 'en' and article.get('english_audio_url'):
                                    original_url = article['english_audio_url']
                                    
                                    # 既に署名付きURLの場合はそのまま返す
                                    if isinstance(original_url, str) and original_url.startswith(('https://', 'http://')) and 'X-Amz-Signature=' in original_url:
                                        logger.info(f"既に署名付きURLが設定されています（英語）: {original_url}")
                                        return build_response(200, {"url": original_url})
                                    
                                    # S3バケットのURLを署名付きURLに変換
                                    if original_url and original_url.startswith('https://'):
                                        if f"{S3_BUCKET}.s3.amazonaws.com/" in original_url:
                                            # S3 URLからキーを抽出
                                            audio_key = original_url.split(
                                                f"{S3_BUCKET}.s3.amazonaws.com/")[-1]
                                            api_url = build_audio_url(
                                                audio_key)
                                            return build_response(200, {"url": api_url})
                                        else:
                                            # 既にAPI Gateway URL等の場合はそのまま返す
                                            return build_response(200, {"url": original_url})

                                elif article.get('audio_url'):
                                    original_url = article['audio_url']
                                    
                                    # 既に署名付きURLの場合はそのまま返す
                                    if isinstance(original_url, str) and original_url.startswith(('https://', 'http://')) and 'X-Amz-Signature=' in original_url:
                                        logger.info(f"既に署名付きURLが設定されています: {original_url}")
                                        return build_response(200, {"url": original_url})
                                    
                                    # S3バケットのURLを署名付きURLに変換
                                    if original_url and original_url.startswith('https://'):
                                        if f"{S3_BUCKET}.s3.amazonaws.com/" in original_url:
                                            # S3 URLからキーを抽出
                                            audio_key = original_url.split(
                                                f"{S3_BUCKET}.s3.amazonaws.com/")[-1]
                                            api_url = build_audio_url(
                                                audio_key)
                                            return build_response(200, {"url": api_url})
                                        else:
                                            # 既にAPI Gateway URL等の場合はそのまま返す
                                            return build_response(200, {"url": original_url})
                    except ClientError:
                        # エピソード詳細が取得できなければスキップ
                        continue

                # 音声ファイルが見つからない場合
                return build_response(404, {"error": f"Audio file for article {article_id} not found"})

            except ClientError as e:
                logger.error(f"S3からのエピソード一覧取得エラー: {str(e)}")
                return build_response(404, {"error": "Episodes list not found"})
        else:
            # ローカル環境では、S3へのアクセスなしでエミュレーション
            return build_response(200, {"url": f"http://{LOCAL_HOST}:{LOCAL_PORT}/audio/{article_id}.mp3"})

    except Exception as e:
        logger.error(f"記事音声取得エラー: {str(e)}")
        logger.error(traceback.format_exc())
        return build_response(500, {"error": "Internal server error"})


def get_playlist(episode_id):
    """エピソードのプレイリストを取得

    Args:
        episode_id: エピソードID

    Returns:
        dict: APIレスポンス（プレイリスト情報）
    """
    try:
        metadata = None

        # メタデータファイルの取得を試みる
        try:
            if IS_LAMBDA:
                metadata_path = get_metadata_path(episode_id)
                metadata_response = s3_client.get_object(
                    Bucket=S3_BUCKET, Key=metadata_path)
                metadata = json.loads(
                    metadata_response['Body'].read().decode('utf-8'))

                # S3バケットURLをAPI Gateway経由のURLまたは署名付きURLに変換
                if 'playlist' in metadata:
                    from src.config import build_audio_url
                    for item in metadata['playlist']:
                        if 'audio_url' in item and item['audio_url']:
                            original_url = item['audio_url']
                            
                            # デバッグ出力
                            logger.info(f"元のaudio_url: {original_url}")

                            # 処理対象URLがすでに署名付きURLの場合はスキップ
                            if isinstance(original_url, str) and (
                                (original_url.startswith('https://') and 'X-Amz-Signature=' in original_url) or
                                (original_url.startswith('http://') and 'X-Amz-Signature=' in original_url)
                            ):
                                logger.info(f"  既に署名付きURLが設定されています: {original_url}")
                                continue
                            
                            # URLパスから正しいファイルパスまたはキーを抽出
                            audio_key = None
                            
                            if original_url.startswith('/audio/'):
                                # /audio/プレフィックスがある場合
                                audio_key = original_url[7:]  # "/audio/"の後の部分
                                logger.info(f"  /audio/プレフィックス後: {audio_key}")
                                
                                # URLスキームが含まれている異常パターン: /audio/https://...
                                if audio_key.startswith(('http://', 'https://')):
                                    audio_key = audio_key.split('/')[-1]  # ファイル名のみ抽出
                                    logger.info(f"  異常パターン検出 - ファイル名抽出: {audio_key}")
                            
                            elif original_url.startswith(('https://', 'http://')):
                                # 完全なURLの場合
                                logger.info(f"  完全なURLを検出: {original_url}")
                                
                                if f"{S3_BUCKET}.s3.amazonaws.com/" in original_url:
                                    # S3 URL
                                    audio_key = original_url.split(f"{S3_BUCKET}.s3.amazonaws.com/")[-1]
                                    logger.info(f"  S3 URL処理 - キー抽出: {audio_key}")
                                else:
                                    # その他のURL
                                    audio_key = original_url.split('/')[-1]  # ファイル名のみ抽出
                                    logger.info(f"  その他のURL処理 - ファイル名抽出: {audio_key}")
                            
                            else:
                                # その他の形式（単純なファイル名など）
                                audio_key = original_url
                                logger.info(f"  シンプルなパス処理: {audio_key}")
                            
                            # 署名付きURLまたはAPI Gateway経由のURLを生成
                            item['audio_url'] = build_audio_url(audio_key)
                            
                            # 変換結果を記録
                            logger.info(f"変換後のaudio_url: {item['audio_url']}")
                            
                            # 署名付きURLの生成に失敗した場合の最終チェック
                            if item['audio_url'] and '/audio/http' in item['audio_url']:
                                # 異常な形式が残っている場合は修正
                                logger.info(f"  最終チェックで異常を検出: {item['audio_url']}")
                                parts = item['audio_url'].split('/audio/')
                                if len(parts) > 1 and parts[1].startswith(('http://', 'https://')):
                                    filename = parts[1].split('/')[-1]
                                    item['audio_url'] = build_audio_url(filename)
                                    logger.info(f"  最終修正を適用: {item['audio_url']}")

            else:
                metadata_path = get_metadata_path(episode_id)
                if os.path.exists(metadata_path):
                    with open(metadata_path, 'r', encoding='utf-8') as f:
                        metadata = json.load(f)

                    # ローカル環境でもS3 URLを変換
                    if 'playlist' in metadata:
                        for item in metadata['playlist']:
                            if 'audio_url' in item and item['audio_url']:
                                audio_url = item['audio_url']

                                # 既に/audio/が付いている場合
                                if audio_url.startswith('/audio/'):
                                    # "/audio/"の後の部分
                                    after_prefix = audio_url[7:]

                                    if after_prefix.startswith('http'):
                                        # URLスキームが含まれている場合はファイル名のみ抽出
                                        filename = after_prefix.split('/')[-1]
                                        item['audio_url'] = f"http://{LOCAL_HOST}:{LOCAL_PORT}/audio/{filename}"
                                    else:
                                        # 通常の相対パスの場合は既に適切
                                        item['audio_url'] = f"http://{LOCAL_HOST}:{LOCAL_PORT}/audio/{after_prefix}"
                                elif audio_url.startswith('https://') or audio_url.startswith('http://'):
                                    # 完全なURLの場合、ファイル名のみを抽出
                                    filename = audio_url.split('/')[-1]
                                    item['audio_url'] = f"http://{LOCAL_HOST}:{LOCAL_PORT}/audio/{filename}"
                                else:
                                    # その他の形式（単純なファイル名など）
                                    item['audio_url'] = f"http://{LOCAL_HOST}:{LOCAL_PORT}/audio/{audio_url}"

        except (ClientError, FileNotFoundError):
            # メタデータファイルが存在しない場合はエラーを返す
            logger.info(f"メタデータファイルが見つかりません: {episode_id}")
            return build_response(404, {"error": f"Metadata for episode {episode_id} not found"})
        except Exception as e:
            logger.error(f"メタデータ取得エラー: {str(e)}")
            return build_response(500, {"error": "Failed to get metadata"})

        # メタデータからプレイリストを直接取得
        if 'playlist' in metadata:
            return build_response(200, {"playlist": metadata['playlist']})
        else:
            # プレイリストがない場合は空のリストを返す
            return build_response(200, {"playlist": []})

    except Exception as e:
        logger.error(f"プレイリスト取得エラー: {str(e)}")
        logger.error(traceback.format_exc())
        return build_response(500, {"error": "Internal server error"})


def get_health():
    """ヘルスチェックエンドポイント

    Returns:
        dict: APIレスポンス
    """
    return build_response(200, {"status": "OK", "service": "news-audio-api"})


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

        # /audio/以下のパスリクエストは音声プロキシに転送
        if path.startswith('/audio/'):
            # audio_proxy.pyのlambda_handlerを呼び出す
            # パスからファイルパスを抽出 (/audio/filename.mp3 -> filename.mp3)
            file_path = path[7:]  # "/audio/"の部分を削除

            # audio_proxyに必要なパラメータを設定
            proxy_event = event.copy()
            # pathParametersが存在しない場合は作成
            if 'pathParameters' not in proxy_event or not proxy_event['pathParameters']:
                proxy_event['pathParameters'] = {}

            proxy_event['pathParameters']['file_path'] = file_path

            # オーディオプロキシハンドラを呼び出し
            logger.info(f"Routing to audio proxy handler: {file_path}")
            return audio_proxy_handler(proxy_event, context)

        # パスによるルーティング
        if path == '/episodes' or path == '/api/episodes':
            return get_episodes()
        elif path.startswith('/episodes/') or path.startswith('/api/episodes/'):
            # エピソードIDのみか、playlist指定かを判定
            path_parts = path.split('/')
            # パスの末尾がplaylistの場合
            if path_parts[-1] == 'playlist':
                episode_id = path_parts[-2]
                return get_playlist(episode_id)
            # 通常のエピソード取得
            else:
                episode_id = path_parts[-1]
                return get_episode(episode_id)
        elif path.startswith('/api/articles/') and path.endswith('/audio'):
            # /api/articles/{article_id}/audio 形式から抽出
            article_id = path.split('/')[-2]
            # queryStringParametersがNoneの場合にも対応
            query_params = event.get('queryStringParameters') or {}
            language = query_params.get('language', 'ja')
            return get_article_audio(article_id, language)
        elif path == '/health':
            return get_health()
        else:
            return build_response(404, {"error": "Not found"})

    except Exception as e:
        logger.error(f"リクエスト処理エラー: {str(e)}")
        logger.error(traceback.format_exc())
        return build_response(500, {"error": "Internal server error"})
