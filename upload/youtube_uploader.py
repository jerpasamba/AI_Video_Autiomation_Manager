import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ANIME_SHORTS_PATH = None


def _infer_thumbnail_path(video_path, provided_thumb=None):
    if provided_thumb and os.path.exists(provided_thumb):
        return provided_thumb
    if not video_path:
        return None
    cand = os.path.join(os.path.dirname(video_path), "thumbnail.jpg")
    if os.path.exists(cand):
        return cand
    return None


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


def _get_manhwa_project_path(config):
    rel = config.get("manhwa_project_path", "projects/manhwa_engine")
    return os.path.abspath(os.path.join(ROOT, rel))


def _get_manhwa_series_title(config):
    proj = _get_manhwa_project_path(config)
    p = os.path.join(proj, "story_bible.json")
    try:
        import json
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        title = (data.get("title") or "").strip()
        return title or None
    except Exception:
        return None


def _is_manhwa_video(video_path, config):
    if not video_path:
        return False
    proj = _get_manhwa_project_path(config)
    try:
        vp = os.path.normcase(os.path.abspath(video_path))
        mp = os.path.normcase(os.path.abspath(proj))
        return vp.startswith(mp)
    except Exception:
        return False


def _get_duration_sec(video_path):
    # Uses ffprobe from anime_engine utils (already on sys.path after _setup_youtube_imports).
    from src.utils.ffmpeg import ffprobe_cmd

    r = ffprobe_cmd(
        [
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            video_path,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return float((r.stdout or "").strip() or "0")


def _pick_shorts_start(duration_sec, target_sec=60.0):
    if duration_sec <= target_sec:
        return 0.0
    # Deterministic and based only on video length: use a centered 60s window.
    return max(0.0, (duration_sec - target_sec) / 2.0)


def _render_shorts_clip(video_path, out_path, start_sec, duration_sec=60.0):
    from src.utils.ffmpeg import ffmpeg_cmd

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    ffmpeg_cmd(
        [
            "-y",
            "-ss",
            f"{start_sec:.3f}",
            "-i",
            video_path,
            "-t",
            f"{duration_sec:.3f}",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-c:a",
            "aac",
            "-movflags",
            "+faststart",
            out_path,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return out_path


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


def upload_video(video_path, title, description, tags, progress_cb, config, thumbnail_path=None):
    _setup_youtube_imports(config)
    from src.uploader.youtube import YouTubeUploader
    from app import upload_registry

    yt_config = config.get("youtube", {})

    existing = upload_registry.find_existing(video_path, platform="youtube")
    if existing and existing.get("remote_id"):
        vid = existing.get("remote_id")
        progress_cb(100, f"Already uploaded (registry). ID: {vid}")
        return {"id": vid, "url": existing.get("url"), "existing": True}

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

    vid = (result or {}).get("id")

    # Best-effort: add to manhwa series playlist.
    if vid and yt_config.get("playlists_enabled", False) and _is_manhwa_video(video_path, config):
        try:
            pl_title = (yt_config.get("manhwa_playlist_title") or "").strip() or _get_manhwa_series_title(config)
            if pl_title:
                progress_cb(80, f"Adding to playlist: {pl_title[:40]}...")
                playlist_id = uploader.find_or_create_playlist(pl_title)
                uploader.add_video_to_playlist(vid, playlist_id)
        except Exception:
            # Missing scope / API errors shouldn't fail the upload.
            pass

    # Best-effort: set YouTube thumbnail if we have thumbnail.jpg next to the video.
    try:
        thumb_path = _infer_thumbnail_path(video_path, thumbnail_path)
        if vid and thumb_path:
            progress_cb(85, "Uploading thumbnail...")
            uploader.set_thumbnail(vid, thumb_path)
    except Exception:
        pass

    try:
        url = f"https://youtu.be/{vid}" if vid else None
        upload_registry.record_upload(video_path, platform="youtube", remote_id=vid, url=url)
    except Exception:
        pass

    # Optional: auto-generate and upload a 60s YouTube Short derived from this video.
    if yt_config.get("shorts_enabled", False) and _is_manhwa_video(video_path, config):
        try:
            shorts_out = os.path.join(
                os.path.dirname(video_path),
                os.path.splitext(os.path.basename(video_path))[0] + "_short.mp4",
            )
            existing_short = upload_registry.find_existing(shorts_out, platform="youtube_short")
            if existing_short and existing_short.get("remote_id"):
                progress_cb(100, f"Short already uploaded. ID: {existing_short.get('remote_id')}")
                return result

            progress_cb(88, "Generating 60s Short...")
            dur = _get_duration_sec(video_path)
            if dur <= 62:
                progress_cb(100, "Skipped Short (video <= ~60s)")
                return result

            start = _pick_shorts_start(dur, 60.0)
            _render_shorts_clip(video_path, shorts_out, start, 60.0)

            short_title = (title or "Video")
            if "#short" not in short_title.lower():
                short_title = short_title + " #shorts"
            short_desc = (description or "").rstrip() + "\n\n#shorts\n"
            short_tags = list(set(list(tags or []) + ["shorts"]))

            progress_cb(92, "Uploading Short...")
            short_res = uploader.upload(
                video_path=shorts_out,
                title=short_title,
                description=short_desc,
                tags=short_tags,
                category_id=category_id,
            )
            short_vid = (short_res or {}).get("id")
            if short_vid:
                try:
                    thumb_path = _infer_thumbnail_path(video_path, thumbnail_path)
                    if thumb_path:
                        uploader.set_thumbnail(short_vid, thumb_path)
                except Exception:
                    pass

                if yt_config.get("playlists_enabled", False):
                    try:
                        pl_title = (yt_config.get("manhwa_playlist_title") or "").strip() or _get_manhwa_series_title(config)
                        if pl_title:
                            playlist_id = uploader.find_or_create_playlist(pl_title)
                            uploader.add_video_to_playlist(short_vid, playlist_id)
                    except Exception:
                        pass

            try:
                short_url = f"https://youtu.be/{short_vid}" if short_vid else None
                upload_registry.record_upload(shorts_out, platform="youtube_short", remote_id=short_vid, url=short_url)
            except Exception:
                pass
        except Exception:
            pass

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
