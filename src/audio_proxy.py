import json
import os
import logging
import boto3
import base64
from botocore.exceptions import ClientError
import traceback

from src.config import (
    IS_LAMBDA, CORS_HEADERS, LOCAL_AUDIO_DIR, S3_BUCKET
)

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# S3クライアント（Lambda環境でのみ初期化）
s3_client = boto3.client('s3') if IS_LAMBDA else None


def generate_presigned_url(audio_key, expiration=3600):
    """S3オブジェクトの署名付きURLを生成する

    Args:
        audio_key: 音声ファイルのS3キー
        expiration: URL有効期限（秒）

    Returns:
        str: 署名付きURL、またはNone（エラー時）
    """
    if not IS_LAMBDA or not s3_client:
        return None

    # ファイルパスのクリーニング
    if audio_key.startswith('/audio/'):
        audio_key = audio_key[7:]
    elif audio_key.startswith('audio/'):
        audio_key = audio_key[6:]

    # 「https://」や「http://」が含まれている場合はファイル名のみ抽出
    if 'https://' in audio_key or 'http://' in audio_key:
        audio_key = audio_key.split('/')[-1]

    # 可能性のあるS3キーパターン
    s3_keys_to_try = [
        audio_key,
        f"audio/{audio_key}",
        f"data/audio/{audio_key}",
        f"narration/{audio_key}",
        f"data/narration/{audio_key}",
        # audio_keyが既にサブディレクトリを含む場合（narration/file.mp3など）
        os.path.join("data", audio_key),
        os.path.join("audio", os.path.basename(audio_key)),
        os.path.join("data/audio", os.path.basename(audio_key)),
        os.path.join("narration", os.path.basename(audio_key)),
        os.path.join("data/narration", os.path.basename(audio_key))
    ]

    # 重複するキーを削除
    s3_keys_to_try = list(set(s3_keys_to_try))

    # 各キーで署名付きURLの生成を試みる
    for s3_key in s3_keys_to_try:
        try:
            # まずオブジェクトが存在するか確認
            s3_client.head_object(Bucket=S3_BUCKET, Key=s3_key)

            # 署名付きURLを生成
            url = s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': S3_BUCKET,
                    'Key': s3_key
                },
                ExpiresIn=expiration
            )
            logger.info(f"署名付きURL生成成功: {s3_key}")
            return url
        except ClientError as e:
            # オブジェクトが存在しない場合は次のキーを試す
            logger.debug(f"S3キー {s3_key} での署名付きURL生成失敗: {str(e)}")
            continue

    logger.warning(f"すべてのS3キーパターンで署名付きURL生成に失敗: {audio_key}")
    return None


def lambda_handler(event, context):
    """S3バケットまたはローカルファイルシステムから音声ファイルを取得して返す

    Args:
        event: API Gatewayイベント
        context: Lambda実行コンテキスト

    Returns:
        dict: API Gatewayレスポンス
    """
    try:
        # パスパラメータからファイルキーを取得
        if 'pathParameters' in event and event['pathParameters']:
            file_path = event['pathParameters'].get('file_path', '')
        else:
            return {
                'statusCode': 400,
                'headers': CORS_HEADERS,
                'body': json.dumps({'error': 'Missing file path parameter'})
            }

        # イベント情報をデバッグログに出力
        logger.info(f"Audio proxy event: {json.dumps(event)}")
        logger.info(f"Requested file path: {file_path}")

        # ファイルパスのバリデーション（セキュリティ対策）
        if not file_path or '..' in file_path:
            return {
                'statusCode': 400,
                'headers': CORS_HEADERS,
                'body': json.dumps({'error': 'Invalid file path'})
            }

        # ファイルパスから不要なプレフィックスをクリーニング
        # /audio/が先頭にある場合は削除
        if file_path.startswith('/audio/'):
            file_path = file_path[7:]
        elif file_path.startswith('audio/'):
            file_path = file_path[6:]

        # URLエンコードされた文字をデコード
        if '%' in file_path:
            try:
                import urllib.parse
                file_path = urllib.parse.unquote(file_path)
                logger.info(f"Path after URL decode: {file_path}")
            except Exception as e:
                logger.warning(f"Failed to URL decode path: {str(e)}")

        # 「https://」や「http://」が含まれている場合はファイル名のみ抽出
        if 'https://' in file_path or 'http://' in file_path:
            file_path = file_path.split('/')[-1]
            logger.info(f"Extracted filename from URL: {file_path}")

        logger.info(f"Retrieving audio file (cleaned path): {file_path}")

        # ファイルの内容を取得
        file_content = None
        content_type = 'audio/mpeg'

        if IS_LAMBDA:
            # Lambda環境: S3からファイルを取得
            # 複数のパターンを試す
            s3_keys_to_try = [
                file_path,
                f"audio/{file_path}",
                f"data/audio/{file_path}",
                f"narration/{file_path}",
                f"data/narration/{file_path}",
                # file_pathが既にサブディレクトリを含む場合（narration/file.mp3など）
                os.path.join("data", file_path),
                os.path.join("audio", os.path.basename(file_path)),
                os.path.join("data/audio", os.path.basename(file_path)),
                os.path.join("narration", os.path.basename(file_path)),
                os.path.join("data/narration", os.path.basename(file_path))
            ]

            # 重複するキーを削除
            s3_keys_to_try = list(set(s3_keys_to_try))

            file_found = False
            last_error = None

            for s3_key in s3_keys_to_try:
                try:
                    logger.info(f"Trying S3 key: {s3_key}")
                    response = s3_client.get_object(
                        Bucket=S3_BUCKET,
                        Key=s3_key
                    )

                    # Content-Typeを取得
                    content_type = response.get('ContentType', 'audio/mpeg')

                    # ファイル内容を取得
                    file_content = response['Body'].read()
                    logger.info(
                        f"Successfully retrieved file from S3: {s3_key}, {len(file_content)} bytes, content-type: {content_type}")
                    file_found = True
                    break
                except ClientError as e:
                    error_code = e.response['Error']['Code']
                    error_message = e.response['Error']['Message']
                    logger.info(
                        f"S3 ClientError for key {s3_key} ({error_code}): {error_message}")
                    last_error = e

            if not file_found:
                logger.error(f"All S3 keys failed for file: {file_path}")
                if last_error:
                    error_code = last_error.response['Error']['Code']
                    return {
                        'statusCode': 404 if error_code == 'NoSuchKey' else 500,
                        'headers': CORS_HEADERS,
                        'body': json.dumps({'error': f'File not found: {file_path}'})
                    }
        else:
            # ローカル環境: ローカルファイルシステムからファイルを読み込む
            # 色々なパターンを試してみる
            paths_to_try = [
                os.path.join(LOCAL_AUDIO_DIR, file_path),
                os.path.join(LOCAL_AUDIO_DIR, os.path.basename(file_path)),
                os.path.join(os.path.dirname(LOCAL_AUDIO_DIR),
                             'local_audio', file_path),
                os.path.join(os.path.dirname(LOCAL_AUDIO_DIR), file_path),
                os.path.join(LOCAL_AUDIO_DIR, 'narration', file_path),
                os.path.join(LOCAL_AUDIO_DIR, 'narration',
                             os.path.basename(file_path))
            ]

            file_found = False
            for local_file_path in paths_to_try:
                logger.info(f"Trying to read local file: {local_file_path}")
                if os.path.exists(local_file_path) and os.path.isfile(local_file_path):
                    # ファイルの拡張子からContent-Typeを判断
                    if local_file_path.endswith('.wav'):
                        content_type = 'audio/wav'

                    # ファイルを読み込む
                    with open(local_file_path, 'rb') as file:
                        file_content = file.read()
                        logger.info(
                            f"Successfully read local file: {len(file_content)} bytes")
                        file_found = True
                        break

            if not file_found:
                logger.error(
                    f"Local file not found at any tried path for: {file_path}")
                return {
                    'statusCode': 404,
                    'headers': CORS_HEADERS,
                    'body': json.dumps({'error': f'File not found: {file_path}'})
                }

        # ファイルの内容が取得できていることを確認
        if not file_content:
            return {
                'statusCode': 404,
                'headers': CORS_HEADERS,
                'body': json.dumps({'error': 'File content is empty'})
            }

        # APIレスポンスを作成
        response_headers = {
            'Content-Type': content_type,
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Allow-Methods': 'OPTIONS,GET',
            'Cache-Control': 'public, max-age=86400'  # 1日のキャッシュを許可
        }

        return {
            'statusCode': 200,
            'headers': response_headers,
            'body': base64.b64encode(file_content).decode('utf-8'),
            'isBase64Encoded': True
        }

    except Exception as e:
        logger.error(f"Unexpected error in audio proxy: {str(e)}")
        logger.error(traceback.format_exc())
        return {
            'statusCode': 500,
            'headers': CORS_HEADERS,
            'body': json.dumps({'error': f'Server error: {str(e)}'})
        }
