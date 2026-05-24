import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ANIME_SHORTS_PATH = None


def _resolve_shorts_path(config):
    global ANIME_SHORTS_PATH
    if ANIME_SHORTS_PATH:
        return ANIME_SHORTS_PATH
    rel = config.get("anime_shorts_path", "projects/anime_engine")
    ANIME_SHORTS_PATH = os.path.abspath(os.path.join(ROOT, rel))
    return ANIME_SHORTS_PATH


def _setup_youtube_imports(config):
    path = _resolve_shorts_path(config)
    if path not in sys.path:
        sys.path.insert(0, path)


def _resolve_client_secret(config):
    yt_config = config.get("youtube", {})
    path = yt_config.get("client_secret_file", "")
    if path and os.path.exists(path):
        return path
    auto_path = os.path.join(ROOT, "client_secret.json")
    if os.path.exists(auto_path):
        if yt_config:
            yt_config["client_secret_file"] = auto_path
        return auto_path
    return path


def upload_video(video_path, title, description, tags, progress_cb, config):
    _setup_youtube_imports(config)
    from src.uploader.youtube import YouTubeUploader

    client_secret = _resolve_client_secret(config)
    token_file = config.get("youtube", {}).get("token_file", "youtube_token.json")

    if not os.path.exists(client_secret):
        progress_cb(100, "YouTube client_secret not configured")
        raise FileNotFoundError(
            f"YouTube client_secret file not found: {client_secret}\n"
            "Place client_secret.json in the project folder or configure it in Settings tab."
        )

    token_path = os.path.join(ROOT, token_file)

    progress_cb(10, "Authenticating with YouTube...")
    uploader = YouTubeUploader(
        client_secret_file=client_secret,
        token_file=token_path,
    )

    try:
        uploader._get_authenticated_service()
    except Exception as e:
        progress_cb(100, f"YouTube auth failed: {e}")
        raise

    progress_cb(30, f"Uploading: {title[:50]}...")

    category_id = yt_config.get("default_category", "22")
    default_tags = yt_config.get("default_tags", [])
    all_tags = list(set(list(tags) + default_tags))

    result = uploader.upload(
        video_path=video_path,
        title=title,
        description=description,
        tags=all_tags,
        category_id=category_id,
    )

    if result:
        progress_cb(100, f"Uploaded! Video ID: {result.get('id', 'unknown')}")
    else:
        progress_cb(100, "Upload completed (no response)")
    return result


def verify_auth(config):
    _setup_youtube_imports(config)
    from src.uploader.youtube import YouTubeUploader
    from google.oauth2.credentials import Credentials

    client_secret = _resolve_client_secret(config)
    token_file = config.get("youtube", {}).get("token_file", "youtube_token.json")
    token_path = os.path.join(ROOT, token_file)

    if not os.path.exists(client_secret):
        return False, "client_secret file not found. Place client_secret.json in the project folder."

    try:
        uploader = YouTubeUploader(
            client_secret_file=client_secret,
            token_file=token_path,
        )
        uploader._get_authenticated_service()
        return True, "Authenticated"
    except Exception as e:
        return False, str(e)
