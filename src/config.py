import os
from dotenv import load_dotenv

# .env ファイルから環境変数を読み込み
load_dotenv()

# Lambda環境かどうかを判定
IS_LAMBDA = os.environ.get('AWS_LAMBDA_FUNCTION_NAME') is not None

# AWS 設定
AWS_REGION = os.environ.get('AWS_REGION', 'ap-northeast-1')
AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')

# S3 設定
S3_BUCKET_NAME = os.environ.get('S3_BUCKET_NAME')

# ロギング設定
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
