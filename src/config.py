import os
import logging

# ロガー設定
logger = logging.getLogger(__name__)

# 環境設定
IS_LAMBDA = os.environ.get('AWS_EXECUTION_ENV', '').startswith('AWS_Lambda_')

# ローカル開発用設定
LOCAL_HOST = '127.0.0.1'
LOCAL_PORT = 5001
LOCAL_DATA_DIR = os.path.join(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))), 'local_data')
LOCAL_AUDIO_DIR = os.path.join(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))), 'local_audio')

# AWS環境用設定
S3_BUCKET = os.environ.get(
    'S3_BUCKET_NAME', 'news-audio-files-kenchang198-dev')
# 音声ファイルは data/audio/...
S3_PREFIX = os.environ.get('S3_PREFIX', 'data/audio/')
# メタデータは data/metadata/...
S3_METADATA_PREFIX = os.environ.get('S3_METADATA_PREFIX', 'data/metadata/')
API_STAGE = os.environ.get('API_STAGE', 'dev')
# API GatewayのドメインをAPI_DOMAINとして環境変数から取得（デフォルト値は空文字列）
API_DOMAIN = os.environ.get('API_DOMAIN', '')

# 共通設定
CORS_HEADERS = {
    'Access-Control-Allow-Origin': '*',  # 開発環境では全許可、本番環境では適切に制限する
    'Access-Control-Allow-Headers': 'Content-Type',
    'Access-Control-Allow-Methods': 'OPTIONS,GET'
}

# ファイルパス設定（環境によって切り替え）


def get_episodes_data_path(episode_id=None):
    """エピソードメタデータのパスを取得

    Args:
        episode_id: エピソードID（指定がなければ全エピソード）

    Returns:
        str: ファイルパスまたはS3キー
    """
    if IS_LAMBDA:
        if episode_id:
            # S3: data/episodes/episode_<episode_id>.json
            return f"data/episodes/episode_{episode_id}.json"
        return "data/episodes/"  # ディレクトリプレフィックス
    else:
        if episode_id:
            # 既存のファイル構造に合わせて探索する
            episode_path = os.path.join(
                LOCAL_DATA_DIR, "episodes", f"episode_{episode_id}.json")
            metadata_path = os.path.join(
                LOCAL_DATA_DIR, "metadata", f"metadata_{episode_id}.json")
            standard_path = os.path.join(LOCAL_DATA_DIR, f"{episode_id}.json")

            # いずれかのファイルが存在すればそれを返す
            if os.path.exists(episode_path):
                return episode_path
            elif os.path.exists(metadata_path):
                return metadata_path
            else:
                return standard_path
        return LOCAL_DATA_DIR


def get_metadata_path(episode_id):
    """エピソードIDに基づくメタデータファイルのパスを取得

    Args:
        episode_id: エピソードID

    Returns:
        str: メタデータファイルのパスまたはS3キー
    """
    if IS_LAMBDA:
        # S3: S3_METADATA_PREFIX/metadata_<episode_id>.json
        metadata_key = f"{S3_METADATA_PREFIX}metadata_{episode_id}.json"
        return metadata_key
    else:
        # ローカル環境: LOCAL_DATA_DIR/metadata/metadata_<episode_id>.json
        metadata_dir = os.path.join(LOCAL_DATA_DIR, "metadata")
        return os.path.join(metadata_dir, f"metadata_{episode_id}.json")


def get_episodes_list_path():
    """エピソード一覧ファイルのパスを取得

    Returns:
        str: ファイルパスまたはS3キー
    """
    if IS_LAMBDA:
        # AWS環境では data ディレクトリ配下を想定
        return "data/episodes_list.json"
    else:
        # ローカル環境ではローカルのepisodes_list.jsonを使用
        return os.path.join(LOCAL_DATA_DIR, "episodes_list.json")


def build_audio_url(audio_key):
    """音声ファイルのURLを構築

    Args:
        audio_key: 音声ファイルのキーまたはパス

    Returns:
        str: 音声ファイルのURL
    """
    # デバッグ出力
    logger.debug(f"build_audio_url入力: {audio_key}")

    # audio_keyがNoneまたは空文字列の場合
    if not audio_key:
        logger.warning("build_audio_url: 空の音声キーが渡されました")
        return None

    # 既にhttps://を含む完全なURLの場合（署名付きURLなど）はそのまま返す
    if isinstance(audio_key, str) and audio_key.startswith(('https://', 'http://')):
        logger.debug(f"完全なURLが既に指定されています: {audio_key}")
        return audio_key

    if IS_LAMBDA:
        # Lambda環境では署名付きURLを生成
        try:
            # audio_proxy.pyの関数をインポート
            from src.audio_proxy import generate_presigned_url
            
            # 署名付きURLを生成（1時間有効）
            presigned_url = generate_presigned_url(audio_key, expiration=3600)
            if presigned_url:
                logger.debug(f"署名付きURL生成成功: {presigned_url}")
                return presigned_url
                
            # 署名付きURL生成に失敗した場合は従来の方法を使用
            logger.warning(f"署名付きURL生成失敗。従来のAPIパス方式にフォールバックします: {audio_key}")
            
            # 以下は従来の方法（フォールバック）
            if audio_key.startswith('/'):
                audio_path = audio_key[1:]  # 先頭の/を削除
            else:
                audio_path = audio_key

            # audio/プレフィックスがない場合は追加（ただし既に含まれている場合は追加しない）
            if not audio_path.startswith('audio/'):
                audio_path = f"audio/{audio_path}"

            # APIドメインが設定されている場合は完全なURLを返す
            if API_DOMAIN:
                # ドメインの末尾に/がある場合は削除
                domain = API_DOMAIN.rstrip('/')
                url = f"{domain}/{audio_path}"
                logger.debug(f"生成されたURL(API Domain): {url}")
                return url
            else:
                # APIドメインが設定されていない場合は相対パスを返す
                # 先頭のスラッシュを含めない
                url = f"{audio_path}"
                logger.debug(f"生成された相対パス: {url}")
                return url
                
        except ImportError as e:
            logger.warning(f"署名付きURL生成関数のインポートに失敗: {str(e)}")
            # フォールバック処理
            if audio_key.startswith('/'):
                audio_path = audio_key[1:]
            else:
                audio_path = audio_key
                
            if not audio_path.startswith('audio/'):
                audio_path = f"audio/{audio_path}"
                
            if API_DOMAIN:
                domain = API_DOMAIN.rstrip('/')
                return f"{domain}/{audio_path}"
            else:
                return f"{audio_path}"
    else:
        # ローカル開発環境ではホスト名とポートを使用
        if audio_key.startswith('/audio/'):
            filename = audio_key[7:]
        elif audio_key.startswith('audio/'):
            filename = audio_key[6:]
        else:
            filename = os.path.basename(audio_key)
            
        url = f"http://{LOCAL_HOST}:{LOCAL_PORT}/audio/{filename}"
        logger.debug(f"生成されたローカルURL: {url}")
        return url
