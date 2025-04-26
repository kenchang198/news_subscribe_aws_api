import json
import logging
from src.api_handler import handle_request

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    """AWS Lambda関数ハンドラー
    
    Args:
        event: API Gatewayイベント
        context: Lambda実行コンテキスト
        
    Returns:
        dict: API Gatewayレスポンス
    """
    logger.info(f"Received event: {json.dumps(event)}")
    
    return handle_request(event, context)
