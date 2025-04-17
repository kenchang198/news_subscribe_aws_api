import json
import logging
from datetime import datetime
import os
from flask import Flask, jsonify, send_from_directory

app = Flask(__name__)

# ログ設定 (行分割)
logging.basicConfig(
    level=logging.INFO,
    # フォーマット文字列を分割
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 設定 (行分割)
# メタデータJSONファイルの保存先
LOCAL_NEWS_PATH = "/Users/ken/dev/python/news_subscribe_aws/data"
# 音声ファイルの保存先
LOCAL_AUDIO_PATH = "/Users/ken/dev/python/news_subscribe_aws/audio"
# ローカルサーバーで音声ファイルを提供するURL
PORT = int(os.environ.get('PORT', 5001))
BASE_URL = f"http://localhost:{PORT}/audio"


def get_episodes():
    """エピソード一覧を取得"""
    episodes = []
    try:
        # dataディレクトリからJSONファイルを検索
        logger.info(f"Looking for JSON files in: {LOCAL_NEWS_PATH}")
        for filename in os.listdir(LOCAL_NEWS_PATH):
            if filename.endswith('.json') and not filename.startswith('._'):
                file_path = os.path.join(LOCAL_NEWS_PATH, filename)
                logger.debug(f"Processing file: {filename}")
                try:
                    # ファイルパスを分割
                    with open(file_path, 'r', encoding='utf-8') as f:
                        episode_data = json.load(f)

                    # episode_dataが辞書であることを確認
                    if not isinstance(episode_data, dict):
                        logger.warning(
                            f"Skipping non-dict JSON file: {filename}")
                        continue  # 次のファイルへ

                    # 簡略化したエピソード情報を追加 (行分割)
                    episode_id = episode_data.get(
                        'episode_id', os.path.splitext(filename)[0]
                    )
                    title = episode_data.get(
                        'title', f"Episode {os.path.splitext(filename)[0]}"
                    )
                    created_at = episode_data.get(
                        'created_at', '')  # created_atも取得

                    episodes.append({
                        'episode_id': episode_id,
                        'title': title,
                        'created_at': created_at
                    })
                except json.JSONDecodeError as json_e:
                    logger.error(
                        f"Error decoding JSON file {filename}: {json_e}")
                except Exception as file_e:  # 個別ファイル処理中の他のエラー
                    logger.error(f"Error processing file {filename}: {file_e}")

        # created_at が存在するエピソードのみでソート
        try:
            # created_at が空文字列やNoneの場合も考慮してソート
            episodes.sort(
                key=lambda x: x.get('created_at') or '1970-01-01', reverse=True
            )
        except Exception as sort_e:
            logger.error(f"Error sorting episodes: {sort_e}")

    except FileNotFoundError:
        logger.error(f"Data directory not found: {LOCAL_NEWS_PATH}")
        episodes = []  # ディレクトリがなければ空リスト
    except Exception as e:
        logger.error(f"エピソード一覧取得エラー: {str(e)}", exc_info=True)
        episodes = []  # その他の予期せぬエラー

    logger.info(f"Found {len(episodes)} episodes.")
    return episodes


def get_episode_by_id(episode_id):
    """特定のエピソードを取得"""
    try:
        # エピソードIDに対応するJSONファイルを探す (パス構造を修正)
        # data/episodes/episode_{episode_id}.json の形式に合わせる
        json_path = os.path.join(
            LOCAL_NEWS_PATH, "episodes", f"episode_{episode_id}.json"
        )
        logger.info(f"Attempting to load episode from: {json_path}")
        if not os.path.exists(json_path):
            logger.warning(f"Episode file not found: {json_path}")
            return None

        logger.debug(f"Episode file found. Reading JSON: {json_path}")
        with open(json_path, 'r', encoding='utf-8') as f:
            episode_data = json.load(f)

        # URLをローカルパスからローカルサーバーURLに変換
        logger.debug("Converting local paths to URLs...")
        episode_data = convert_local_paths_to_urls(episode_data)

        # プレイリストを生成
        logger.debug("Creating playlist...")
        episode_data['playlist'] = create_playlist(episode_data)

        logger.info(f"Successfully processed episode: {episode_id}")
        return episode_data

    except json.JSONDecodeError as json_e:
        logger.error(f"Error decoding JSON for episode {episode_id} "
                     f"from {json_path}: {json_e}")
        return None  # エラー時はNoneを返す
    except Exception as e:
        logger.error(
            f"Error getting episode {episode_id}: {str(e)}", exc_info=True)  # 詳細ログ出力
        return None


def convert_local_paths_to_urls(episode_data):
    """ローカルファイルパスをURL形式に変換"""
    # イントロ・アウトロのURLを変換
    if 'intro_audio_url' in episode_data and episode_data['intro_audio_url']:
        url = episode_data['intro_audio_url']
        if url.startswith('/'):
            file_path = url.replace('/audio/', '')
            episode_data['intro_audio_url'] = f"{BASE_URL}/{file_path}"
        # 相対パスの場合 (行分割)
        elif not url.startswith('http'):
            episode_data['intro_audio_url'] = f"{BASE_URL}/{url}"

    if 'outro_audio_url' in episode_data and episode_data['outro_audio_url']:
        url = episode_data['outro_audio_url']
        if url.startswith('/'):
            file_path = url.replace('/audio/', '')
            episode_data['outro_audio_url'] = f"{BASE_URL}/{file_path}"
        # 相対パスの場合 (行分割)
        elif not url.startswith('http'):
            episode_data['outro_audio_url'] = f"{BASE_URL}/{url}"

    # 記事のURLを変換
    if 'articles' in episode_data:
        for article in episode_data['articles']:
            if 'audio_url' in article and article['audio_url']:
                url = article['audio_url']
                if url.startswith('/'):
                    file_path = url.replace('/audio/', '')
                    article['audio_url'] = f"{BASE_URL}/{file_path}"
                # 相対パスの場合 (行分割)
                elif not url.startswith('http'):
                    article['audio_url'] = f"{BASE_URL}/{url}"

            if 'intro_audio_url' in article and article['intro_audio_url']:
                url = article['intro_audio_url']
                if url.startswith('/'):
                    # ファイルパス取得を分割
                    file_path = url.replace('/audio/', '')
                    article['intro_audio_url'] = f"{BASE_URL}/{file_path}"
                # 相対パスの場合 (行分割)
                elif not url.startswith('http'):
                    article['intro_audio_url'] = f"{BASE_URL}/{url}"

    return episode_data


def create_playlist(episode_data):
    """シームレス再生のためのプレイリストを生成"""
    playlist = []

    # イントロを追加
    if 'intro_audio_url' in episode_data and episode_data['intro_audio_url']:
        playlist.append({
            'type': 'intro',
            'audio_url': episode_data['intro_audio_url']
        })

    # 記事とトランジションを追加
    if 'articles' in episode_data:
        num_articles = len(episode_data['articles'])
        for i, article in enumerate(episode_data['articles']):
            # 記事のイントロ
            if 'intro_audio_url' in article and article['intro_audio_url']:
                playlist.append({
                    'type': 'article_intro',
                    'article_id': article['id'],
                    'audio_url': article['intro_audio_url']
                })

            # 記事本文
            if 'audio_url' in article and article['audio_url']:
                playlist.append({
                    'type': 'article',
                    'article_id': article['id'],
                    'audio_url': article['audio_url']
                })

            # 次の記事へのトランジション（最後の記事以外）
            if i < num_articles - 1:
                transition_key = f"transition_{i+1}_{i+2}"
                transition_url_key = f"{transition_key}_audio_url"
                # キー存在確認とURL取得 (行分割)
                if (transition_url_key in episode_data and
                        episode_data[transition_url_key]):
                    playlist.append({
                        'type': 'transition',
                        'audio_url': episode_data[transition_url_key]
                    })

    # アウトロを追加
    if 'outro_audio_url' in episode_data and episode_data['outro_audio_url']:
        playlist.append({
            'type': 'outro',
            'audio_url': episode_data['outro_audio_url']
        })

    return playlist

# 音声ファイルを提供するルート


@app.route('/audio/<path:filename>')
def serve_audio(filename):
    return send_from_directory(LOCAL_AUDIO_PATH, filename)

# APIエンドポイント: エピソード一覧


@app.route('/api/episodes', methods=['GET'])
def api_episodes():
    episodes = get_episodes()
    return jsonify({
        'episodes': episodes
    })

# APIエンドポイント: 特定のエピソード


@app.route('/api/episodes/<episode_id>', methods=['GET'])
def api_episode(episode_id):
    episode = get_episode_by_id(episode_id)
    if episode:
        return jsonify(episode)
    return jsonify({'error': 'Episode not found'}), 404

# APIエンドポイント: ヘルスチェック


@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.now().isoformat()
    })

# CORSヘッダーの追加


@app.after_request
def add_cors_headers(response):
    response.headers.add("Access-Control-Allow-Origin", "*")
    # ヘッダー名を分割
    response.headers.add(
        "Access-Control-Allow-Headers", "Content-Type,Authorization"
    )
    response.headers.add("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
    return response


if __name__ == '__main__':
    print("ローカルAPIサーバーを起動します...")
    print(f"メタデータの場所: {LOCAL_NEWS_PATH}")
    print(f"音声ファイルの場所: {LOCAL_AUDIO_PATH}")
    print(f"BaseURL: {BASE_URL}")
    print("利用可能なエンドポイント:")
    print(f"- http://localhost:{PORT}/api/episodes (エピソード一覧)")
    print(f"- http://localhost:{PORT}/api/episodes/<episode_id> (特定エピソード)")
    print(f"- http://localhost:{PORT}/audio/<filename> (音声ファイル)")

    # Flaskサーバーを起動
    app.run(debug=True, port=5001)
