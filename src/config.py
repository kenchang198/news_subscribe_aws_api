import os

# Lambda環境かどうかを判定 (dotenvの前に判定)
IS_LAMBDA = os.environ.get('AWS_LAMBDA_FUNCTION_NAME') is not None

# ローカル環境の場合のみ dotenv をインポートして .env を読み込む
if not IS_LAMBDA:
    try:
        from dotenv import load_dotenv
        # .envファイルが存在する場合のみ読み込む
        dotenv_path = os.path.join(os.path.dirname(
            __file__), '../.env')  # .env がプロジェクトルートにあると仮定
        if os.path.exists(dotenv_path):
            load_dotenv(dotenv_path=dotenv_path)
            print("Loaded environment variables from .env")  # 確認用ログ
        else:
            # .env がなくてもエラーにはしない
            pass
    except ImportError:
        # dotenv がインストールされていない場合もエラーにしない
        pass

# AWS 設定 (環境変数から取得、なければデフォルト値)
AWS_REGION = os.environ.get('AWS_REGION', 'ap-northeast-1')
# AWS認証情報はLambda実行ロールやEC2インスタンスプロファイル等から取得される想定
# ローカル用に .env や環境変数で設定する場合のみ有効
AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')

# S3 設定
S3_BUCKET_NAME = os.environ.get('S3_BUCKET_NAME')
if not S3_BUCKET_NAME:
    # S3バケット名がない場合は警告（Lambda環境では必須）
    if IS_LAMBDA:
        print("Warning: S3_BUCKET_NAME environment variable is not set.")
    else:
        # ローカルではエラーにしない（他の方法で設定する可能性）
        pass

# ロギング設定
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
