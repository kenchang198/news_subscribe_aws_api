import os

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
    if IS_LAMBDA:
        base_url = f"https://{S3_BUCKET}.s3.amazonaws.com"
        return f"{base_url}/{audio_key}"
    else:
        # ローカル開発環境ではホスト名とポートを使用
        filename = os.path.basename(audio_key)
        return f"http://{LOCAL_HOST}:{LOCAL_PORT}/audio/{filename}"
