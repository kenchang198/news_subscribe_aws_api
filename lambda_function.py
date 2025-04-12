import json
import logging
from src.api_handler import handle_api_request

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def lambda_handler(event, context):
    """
    APIリクエストを処理するLambda関数
    """
    logger.info(f"APIリクエスト受信: {json.dumps(event)}")
    
    try:
        # APIリクエストの処理
        return handle_api_request(event, context)
    
    except Exception as e:
        logger.error(f"APIリクエスト処理中にエラー: {str(e)}", exc_info=True)
        
        # エラーレスポンス
        return {
            'statusCode': 500,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Content-Type': 'application/json'
            },
            'body': json.dumps({
                'error': 'Internal Server Error',
                'message': str(e)
            })
        }


# ローカル開発用のテスト
if __name__ == "__main__":
    # テストイベント
    test_event = {
        'httpMethod': 'GET',
        'path': '/api/episodes',
        'queryStringParameters': {
            'page': '1',
            'limit': '10'
        }
    }
    
    # Lambda関数を実行
    response = lambda_handler(test_event, None)
    print(json.dumps(response, indent=2, ensure_ascii=False))
