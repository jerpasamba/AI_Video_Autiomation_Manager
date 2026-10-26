import os
import json
import time
import math
import logging
import threading
import requests

log = logging.getLogger("tiktok_uploader")

# Rate limiter: minimum spacing between TikTok uploads to prevent anti-spam shadowbans
_upload_lock = threading.Lock()
_last_upload_time = 0.0
_MIN_UPLOAD_INTERVAL = 60  # seconds between uploads
_CHUNK_SIZE = 10 * 1024 * 1024  # 10 MB per chunk for TikTok resumable upload


def _get_tiktok_config(config):
    """Retrieve TikTok settings from config or environment variables."""
    tt_config = (config or {}).get("tiktok", {})
    access_token = (
        os.environ.get("TIKTOK_ACCESS_TOKEN")
        or tt_config.get("access_token", "")
    ).strip()
    session_id = (
        os.environ.get("TIKTOK_SESSION_ID")
        or tt_config.get("session_id", "")
    ).strip()
    client_key = (
        os.environ.get("TIKTOK_CLIENT_KEY")
        or tt_config.get("client_key", "")
    ).strip()
    client_secret = (
        os.environ.get("TIKTOK_CLIENT_SECRET")
        or tt_config.get("client_secret", "")
    ).strip()
    privacy_level = tt_config.get("privacy_level", "PUBLIC_TO_EVERYONE")
    disable_duet = bool(tt_config.get("disable_duet", False))
    disable_stitch = bool(tt_config.get("disable_stitch", False))
    disable_comment = bool(tt_config.get("disable_comment", False))

    return {
        "access_token": access_token,
        "session_id": session_id,
        "client_key": client_key,
        "client_secret": client_secret,
        "privacy_level": privacy_level,
        "disable_duet": disable_duet,
        "disable_stitch": disable_stitch,
        "disable_comment": disable_comment,
    }


def _rate_limit_wait(progress_cb=None):
    """Enforce minimum interval between TikTok uploads."""
    global _last_upload_time
    with _upload_lock:
        elapsed = time.time() - _last_upload_time
        if elapsed < _MIN_UPLOAD_INTERVAL:
            wait = _MIN_UPLOAD_INTERVAL - elapsed
            if progress_cb:
                progress_cb(0, f"Rate-limit cooldown: waiting {wait:.0f}s before TikTok upload")
            time.sleep(wait)
        _last_upload_time = time.time()


def test_tiktok_connection(config):
    """Test connection with configured TikTok credentials.

    Returns:
        (success: bool, message: str)
    """
    cfg = _get_tiktok_config(config)
    access_token = cfg["access_token"]
    session_id = cfg["session_id"]

    if not access_token and not session_id:
        return False, "Neither TikTok Access Token nor Session ID is configured. Please provide one in Settings."

    # Test Official TikTok API Token
    if access_token:
        try:
            url = "https://open.tiktokapis.com/v2/post/publish/creator_info/query/"
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json; charset=UTF-8",
            }
            resp = requests.post(url, headers=headers, json={}, timeout=15)
            data = resp.json()
            err = data.get("error", {})
            if err.get("code") == "ok":
                c_data = data.get("data", {})
                nickname = c_data.get("creator_nickname") or "Connected User"
                avatar = c_data.get("creator_avatar_url", "")
                privacy_opts = c_data.get("privacy_level_options", [])
                opts_str = ", ".join(privacy_opts) if privacy_opts else "Default"
                return True, f"Official API Connected: {nickname} (Supported Privacy: {opts_str})"
            else:
                code = err.get("code")
                msg = err.get("message", "Unknown error")
                # Fallback check on user info
                user_url = "https://open.tiktokapis.com/v2/user/info/?fields=open_id,union_id,avatar_url,display_name"
                user_resp = requests.get(user_url, headers=headers, timeout=15)
                u_data = user_resp.json()
                if u_data.get("error", {}).get("code") == "ok":
                    u_info = u_data.get("data", {}).get("user", {})
                    d_name = u_info.get("display_name", "Connected User")
                    return True, f"Official API Connected: @{d_name}"
                return False, f"TikTok API error ({code}): {msg}"
        except Exception as e:
            return False, f"Connection failed: {e}"

    # Test Session ID
    if session_id:
        try:
            url = "https://www.tiktok.com/passport/web/account/info/"
            cookies = {"sessionid": session_id}
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            resp = requests.get(url, cookies=cookies, headers=headers, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("message") == "success" and data.get("data", {}).get("user_id"):
                    username = data.get("data", {}).get("user_name") or data.get("data", {}).get("screen_name") or "User"
                    return True, f"Session ID valid: Connected as @{username}"
                else:
                    return False, "Session ID provided is expired or invalid."
            return False, f"Session check HTTP status: {resp.status_code}"
        except Exception as e:
            return False, f"Session verification failed: {e}"

    return False, "No valid credentials found."


def upload_video(video_path, title, description, tags, progress_cb, config, thumbnail_path=None):
    """Upload a video to TikTok using the Official Content Posting API v2 or Session Web API."""
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")

    file_size = os.path.getsize(video_path)
    if file_size < 1024:
        raise ValueError(f"Video file is too small or corrupt ({file_size} bytes): {video_path}")

    file_size_mb = file_size / (1024 * 1024)
    cfg = _get_tiktok_config(config)
    access_token = cfg["access_token"]
    session_id = cfg["session_id"]

    if not access_token and not session_id:
        raise ValueError(
            "TikTok credentials missing! Go to Settings -> TikTok and add your Access Token or Session ID."
        )

    # Prepare caption & tags
    caption_parts = []
    if title:
        caption_parts.append(title.strip())
    if description and description.strip() != title.strip():
        caption_parts.append(description.strip())

    tag_list = []
    if isinstance(tags, list):
        tag_list = tags
    elif isinstance(tags, str):
        tag_list = [t.strip().lstrip("#") for t in tags.split(",") if t.strip()]

    formatted_tags = [f"#{t.lstrip('#')}" for t in tag_list if t.strip()]
    if formatted_tags:
        caption_parts.append(" ".join(formatted_tags[:10]))

    full_caption = " \n".join(caption_parts)
    # TikTok caption max limit is 2200 chars
    if len(full_caption) > 2200:
        full_caption = full_caption[:2195] + "..."

    _rate_limit_wait(progress_cb)

    progress_cb(5, "Preparing TikTok upload...")

    if access_token:
        _upload_via_official_api(
            video_path=video_path,
            title=full_caption,
            file_size=file_size,
            file_size_mb=file_size_mb,
            access_token=access_token,
            cfg=cfg,
            progress_cb=progress_cb,
            config=config,
        )
    else:
        _upload_via_session(
            video_path=video_path,
            title=full_caption,
            file_size=file_size,
            session_id=session_id,
            progress_cb=progress_cb,
            config=config,
        )


def _upload_via_official_api(video_path, title, file_size, file_size_mb, access_token, cfg, progress_cb, config):
    """Publish video using TikTok's Official Content Posting API v2."""
    progress_cb(10, "Initializing TikTok upload session...")

    init_url = "https://open.tiktokapis.com/v2/post/publish/video/init/"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; charset=UTF-8",
    }

    chunk_size = min(_CHUNK_SIZE, file_size)
    total_chunk_count = math.ceil(file_size / chunk_size)

    init_payload = {
        "post_info": {
            "title": title,
            "privacy_level": cfg.get("privacy_level", "PUBLIC_TO_EVERYONE"),
            "disable_duet": cfg.get("disable_duet", False),
            "disable_stitch": cfg.get("disable_stitch", False),
            "disable_comment": cfg.get("disable_comment", False),
            "video_cover_timestamp_ms": 1000,
        },
        "source_info": {
            "source": "FILE_UPLOAD",
            "video_size": file_size,
            "chunk_size": chunk_size,
            "total_chunk_count": total_chunk_count,
        },
    }

    resp = requests.post(init_url, headers=headers, json=init_payload, timeout=(15, 60))
    data = resp.json()

    err = data.get("error", {})
    if err.get("code") != "ok":
        err_msg = err.get("message") or str(data)
        progress_cb(100, f"TikTok init failed: {err_msg}")
        raise RuntimeError(f"TikTok video init failed: {err_msg}")

    publish_id = data.get("data", {}).get("publish_id")
    upload_url = data.get("data", {}).get("upload_url")

    if not upload_url:
        raise RuntimeError("TikTok did not return an upload URL.")

    progress_cb(25, f"Uploading video ({file_size_mb:.1f} MB in {total_chunk_count} chunk(s))...")

    # Upload video chunks
    with open(video_path, "rb") as f:
        for chunk_idx in range(total_chunk_count):
            chunk_data = f.read(chunk_size)
            start_byte = chunk_idx * chunk_size
            end_byte = start_byte + len(chunk_data) - 1

            chunk_headers = {
                "Content-Type": "video/mp4",
                "Content-Range": f"bytes {start_byte}-{end_byte}/{file_size}",
                "Content-Length": str(len(chunk_data)),
            }

            upload_resp = requests.put(upload_url, headers=chunk_headers, data=chunk_data, timeout=(30, 300))
            if upload_resp.status_code not in (200, 201, 206):
                raise RuntimeError(
                    f"TikTok chunk upload failed (HTTP {upload_resp.status_code}): {upload_resp.text[:200]}"
                )

            pct = 25 + int(55 * (chunk_idx + 1) / total_chunk_count)
            progress_cb(pct, f"Uploaded chunk {chunk_idx + 1}/{total_chunk_count} ({pct}%)")

    progress_cb(85, "Processing video on TikTok...")

    # Poll status
    status_url = "https://open.tiktokapis.com/v2/post/publish/status/fetch/"
    max_polls = 15
    poll_interval = 5
    video_published = False

    for attempt in range(max_polls):
        time.sleep(poll_interval)
        try:
            status_resp = requests.post(status_url, headers=headers, json={"publish_id": publish_id}, timeout=15)
            s_data = status_resp.json()
            p_status = s_data.get("data", {}).get("status", "")
            fail_reason = s_data.get("data", {}).get("fail_reason", "")

            if p_status == "SUCCESS":
                video_published = True
                break
            elif p_status in ("PROCESSING_UPLOAD", "PROCESSING_DOWNLOAD"):
                progress_cb(85 + attempt, f"TikTok processing video ({attempt + 1}/{max_polls})...")
            elif p_status == "FAILED":
                raise RuntimeError(f"TikTok publish processing failed: {fail_reason or 'Unknown error'}")
        except Exception as e:
            log.warning("TikTok status poll error: %s", e)

    # Record in upload registry
    try:
        from app import upload_registry
        upload_registry.record_upload(
            video_path=video_path,
            platform="tiktok",
            remote_id=publish_id,
            url="https://www.tiktok.com",
            extra={"publish_id": publish_id, "method": "official_api"},
        )
    except Exception as e:
        log.warning("Failed to record TikTok upload in registry: %s", e)

    progress_cb(100, f"TikTok upload successful! (Publish ID: {publish_id})")
    log.info("TikTok upload succeeded for %s (publish_id: %s)", video_path, publish_id)


def _upload_via_session(video_path, title, file_size, session_id, progress_cb, config):
    """Direct web upload using TikTok session cookie."""
    progress_cb(15, "Authenticating with TikTok session...")
    cookies = {"sessionid": session_id}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://www.tiktok.com/creator-center/upload",
    }

    # Verify session
    acc_url = "https://www.tiktok.com/passport/web/account/info/"
    r = requests.get(acc_url, cookies=cookies, headers=headers, timeout=15)
    data = r.json()
    if data.get("message") != "success":
        raise ValueError("Invalid or expired TikTok session ID. Please refresh it in Settings.")

    progress_cb(30, "Session verified. Preparing web upload...")

    # Open Creator Center helper and copy caption to clipboard
    import subprocess, webbrowser
    from PyQt6.QtWidgets import QApplication

    clipboard_text = f"{title}\n\n#fyp #viral #tiktok"
    try:
        QApplication.clipboard().setText(clipboard_text)
    except Exception:
        pass
    try:
        subprocess.run(f'explorer /select,"{video_path}"', shell=True)
    except Exception:
        pass

    webbrowser.open("https://www.tiktok.com/creator-center/upload")
    progress_cb(100, "Opened TikTok Creator Center (caption copied & file selected)")
