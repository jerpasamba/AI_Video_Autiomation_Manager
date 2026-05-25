import os
import json
import time
import requests

FB_API_VERSION = "v22.0"
_CONFIG_PATH = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config.json"))

_PAGE_TOKEN_CACHE = {}


def _get_fb_config(config):
    """Return (page_id, access_token, app_id, app_secret) with env var override.

    Keeps secrets out of config.json when the user prefers environment variables.
    """
    fb_config = (config or {}).get("facebook", {})
    page_id = os.environ.get("FACEBOOK_PAGE_ID") or os.environ.get("FB_PAGE_ID") or fb_config.get("page_id", "")
    access_token = (
        os.environ.get("FACEBOOK_ACCESS_TOKEN")
        or os.environ.get("FB_PAGE_ACCESS_TOKEN")
        or fb_config.get("access_token", "")
    )
    app_id = os.environ.get("FACEBOOK_APP_ID") or fb_config.get("app_id", "")
    app_secret = os.environ.get("FACEBOOK_APP_SECRET") or fb_config.get("app_secret", "")
    return page_id, access_token, app_id, app_secret


def _is_page_token_required_error(data):
    if not isinstance(data, dict):
        return False
    err = data.get("error") or {}
    sub = err.get("error_subcode")
    msg = (err.get("message") or "").lower()
    user_msg = (err.get("error_user_msg") or "").lower()
    # Common error when a user token is used against endpoints that require a Page token.
    if sub == 2069032:
        return True
    if "page access token" in msg or "page access token" in user_msg:
        return True
    return False


def _get_page_access_token(page_id, user_access_token):
    """Derive a Page access token from a user token via /me/accounts.

    Facebook often allows reading Page metadata with a user token, but writing (publishing)
    requires a Page token. Users frequently paste the user token from Graph Explorer.
    """
    if not page_id or not user_access_token:
        return None

    cache_key = (str(page_id), user_access_token[-12:])
    if cache_key in _PAGE_TOKEN_CACHE:
        return _PAGE_TOKEN_CACHE[cache_key]

    resp = requests.get(
        f"https://graph.facebook.com/{FB_API_VERSION}/me/accounts",
        params={"access_token": user_access_token, "fields": "id,name,access_token", "limit": 200},
        timeout=30,
    )
    data = resp.json()
    if resp.status_code >= 400 or data.get("error"):
        return None

    for p in data.get("data", []):
        if str(p.get("id")) == str(page_id) and p.get("access_token"):
            _PAGE_TOKEN_CACHE[cache_key] = p["access_token"]
            return p["access_token"]
    return None


def _ensure_page_token(page_id, access_token):
    """Return a token suitable for publishing to the page."""
    if not page_id or not access_token:
        return access_token

    # Always try to derive a Page token — user tokens with pages_read_engagement
    # can read /videos but CANNOT publish (POST) to it.
    page_token = _get_page_access_token(page_id, access_token)
    if page_token:
        return page_token

    return access_token


def _validate_token(access_token, page_id=None):
    if not access_token or len(access_token) < 50:
        return False, "Token is too short or empty - likely malformed"

    # Validate the token is usable at all.
    resp = requests.get(
        f"https://graph.facebook.com/{FB_API_VERSION}/me",
        params={"access_token": access_token, "fields": "id,name"},
        timeout=15,
    )
    data = resp.json()
    if "id" not in data:
        err = data.get("error", {})
        msg = err.get("message", "Unknown error")
        code = err.get("code", 0)
        if code == 190:
            return False, "Token invalid or malformed (code 190). Regenerate it in Graph API Explorer."
        return False, msg

    # If we have a Page ID, validate the token can access that Page.
    if page_id:
        page_resp = requests.get(
            f"https://graph.facebook.com/{FB_API_VERSION}/{page_id}",
            params={"access_token": access_token, "fields": "id,name"},
            timeout=15,
        )
        page_data = page_resp.json()
        if "id" not in page_data:
            err = page_data.get("error", {})
            msg = err.get("message", "Unknown error")
            return False, f"Token can't access Page {page_id}: {msg}"
        return True, f"Valid token for Page: {page_data.get('name', '?')}"

    return True, f"Valid token for: {data.get('name', '?')}"


def _infer_thumbnail_path(video_path, provided_thumb=None):
    if provided_thumb and os.path.exists(provided_thumb):
        return provided_thumb
    # Convention in this repo: thumbnail.jpg sits next to the generated video.
    cand = os.path.join(os.path.dirname(video_path), "thumbnail.jpg")
    if os.path.exists(cand):
        return cand
    return None


def _try_set_thumbnail(video_id, access_token, thumbnail_path):
    if not thumbnail_path or not os.path.exists(thumbnail_path):
        return False, "No thumbnail file found"
    # Facebook supports setting a video thumbnail via /{video-id}/thumbnails.
    url = f"https://graph.facebook.com/{FB_API_VERSION}/{video_id}/thumbnails"
    with open(thumbnail_path, "rb") as img:
        resp = requests.post(
            url,
            data={
                "access_token": access_token,
                "is_preferred": "true",
            },
            files={"source": img},
            timeout=60,
        )
    data = resp.json()
    if resp.status_code >= 400 or (isinstance(data, dict) and data.get("error")):
        err = data.get("error", {}).get("message", str(data))
        return False, err
    return True, "Thumbnail uploaded"


def _get_video_info(video_id, access_token):
    # Be conservative with fields: Graph API fails the whole call if any field is invalid.
    url = f"https://graph.facebook.com/{FB_API_VERSION}/{video_id}"
    fields = "id,permalink_url,published,status"
    resp = requests.get(url, params={"access_token": access_token, "fields": fields}, timeout=30)
    data = resp.json()
    if resp.status_code >= 400 or data.get("error"):
        # Fallback: permalink_url only.
        resp2 = requests.get(
            url,
            params={"access_token": access_token, "fields": "id,permalink_url"},
            timeout=30,
        )
        data2 = resp2.json()
        if resp2.status_code >= 400 or data2.get("error"):
            err = (data2.get("error") or data.get("error") or {}).get("message", str(data2))
            raise Exception(f"Facebook status check failed: {err}")
        return data2
    return data


def _try_publish_video(video_id, access_token):
    # Some flows can leave the video as an unpublished draft even though the upload finished.
    url = f"https://graph.facebook.com/{FB_API_VERSION}/{video_id}"
    resp = requests.post(url, data={"access_token": access_token, "published": "true"}, timeout=30)
    data = resp.json()
    if resp.status_code >= 400 or data.get("error"):
        err = data.get("error", {}).get("message", str(data))
        return False, err
    # API shape varies; treat HTTP 200 without error as success.
    return True, "Publish attempted"


def _token_expired_message(err_msg):
    m = (err_msg or "").lower()
    if "session has expired" in m or "error validating access token" in m:
        return True
    if "code 190" in m or "#190" in m:
        return True
    return False


def _auto_extend_and_retry(config, progress_cb, current_token):
    """Try to extend the token using app credentials and re-derive Page token.

    Returns (new_token, success). If success is False, the token is truly dead.
    """
    _, _, app_id, app_secret = _get_fb_config(config)
    if not app_id or not app_secret:
        progress_cb(5, "No app credentials to auto-extend token")
        return current_token, False

    progress_cb(5, "Token expired — attempting auto-extend...")
    new_token = _exchange_long_lived_token(app_id, app_secret, current_token)
    if not new_token:
        progress_cb(5, "Auto-extend failed — token may need manual refresh")
        return current_token, False

    fb = config.setdefault("facebook", {})
    fb["access_token"] = new_token
    with open(_CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=4)

    page_id, _, _, _ = _get_fb_config(config)
    page_token = _ensure_page_token(page_id, new_token)
    progress_cb(5, "Token auto-extended — retrying...")
    return page_token, True


def _exchange_long_lived_token(app_id, app_secret, short_token):
    """Exchange a short-lived token (1-2h) for a long-lived token (60 days).

    Returns the new token string, or None on failure.
    """
    if not app_id or not app_secret or not short_token:
        return None
    url = f"https://graph.facebook.com/{FB_API_VERSION}/oauth/access_token"
    resp = requests.get(url, params={
        "grant_type": "fb_exchange_token",
        "client_id": app_id,
        "client_secret": app_secret,
        "fb_exchange_token": short_token,
    }, timeout=30)
    data = resp.json()
    if resp.status_code >= 400 or "access_token" not in data:
        return None
    return data["access_token"]


def _extend_token_if_needed(config):
    """If config has app_id/app_secret, exchange the current token for a 60-day one."""
    page_id, access_token, app_id, app_secret = _get_fb_config(config)
    if not app_id or not app_secret or not access_token:
        return access_token, False

    new_token = _exchange_long_lived_token(app_id, app_secret, access_token)
    if new_token and new_token != access_token:
        fb = config.setdefault("facebook", {})
        fb["access_token"] = new_token
        with open(_CONFIG_PATH, "w") as f:
            json.dump(config, f, indent=4)
        return new_token, True
    return access_token, False


def _reload_config_from_disk(config):
    """Reload secrets from config.json so the app always uses the latest saved token."""
    cfg_path = _CONFIG_PATH
    if os.path.exists(cfg_path):
        try:
            with open(cfg_path, encoding="utf-8") as f:
                disk = json.load(f)
            fb_disk = disk.get("facebook", {})
            fb_cfg = config.setdefault("facebook", {})
            for k in ("access_token", "app_id", "app_secret", "page_id"):
                if k in fb_disk:
                    fb_cfg[k] = fb_disk[k]
        except Exception:
            pass


def upload_reel(video_path, title, description, progress_cb, config, thumbnail_path=None):
    _reload_config_from_disk(config)
    page_id, access_token, app_id, app_secret = _get_fb_config(config)

    if not access_token:
        progress_cb(100, "Facebook access token not configured")
        raise ValueError("Facebook access token not set in Settings tab")

    if not page_id:
        progress_cb(100, "Facebook Page ID not configured")
        raise ValueError("Facebook Page ID not set in Settings tab")

    # Auto-extend short-lived token to 60 days if we have app credentials.
    extended = False
    if app_id and app_secret:
        new_token = _exchange_long_lived_token(app_id, app_secret, access_token)
        if new_token and new_token != access_token:
            access_token = new_token
            extended = True
            fb = config.setdefault("facebook", {})
            fb["access_token"] = access_token
            with open(_CONFIG_PATH, "w") as f:
                json.dump(config, f, indent=4)

    # If a user token was provided, attempt to derive the Page token automatically.
    access_token = _ensure_page_token(page_id, access_token)

    valid, msg = _validate_token(access_token, page_id=page_id)
    if not valid:
        progress_cb(100, f"Token invalid: {msg}")
        raise ValueError(f"Facebook token invalid: {msg}")

    file_size = os.path.getsize(video_path)
    file_size_mb = file_size / (1024 * 1024)
    video_title = title[:100] if title else "Video"

    # Step 1: Initialize upload session
    progress_cb(10, "Initializing upload session...")
    init_url = f"https://graph.facebook.com/{FB_API_VERSION}/{page_id}/videos"
    init_resp = requests.post(init_url, data={
        "upload_phase": "start",
        "access_token": access_token,
        "video_type": "REEL",
    }, timeout=(15, 60))
    init_data = init_resp.json()

    if "video_id" not in init_data:
        err = init_data.get("error", {}).get("message", str(init_data))
        if _token_expired_message(err):
            progress_cb(5, f"Token invalid (code 190) — trying auto-extend...")
            refreshed, ok = _auto_extend_and_retry(config, progress_cb, access_token)
            if ok:
                access_token = refreshed
                init_resp = requests.post(init_url, data={
                    "upload_phase": "start",
                    "access_token": access_token,
                    "video_type": "REEL",
                }, timeout=(15, 60))
                init_data = init_resp.json()
                if "video_id" in init_data:
                    pass  # retry succeeded
                else:
                    err2 = init_data.get("error", {}).get("message", str(init_data))
                    progress_cb(100, f"Init failed after retry: {err2}")
                    raise ValueError(f"Facebook init failed after token refresh: {err2}")
            else:
                progress_cb(100, f"Token expired and auto-extend failed")
                raise ValueError(
                    "Facebook token expired. Generate a new one in Graph API Explorer "
                    "(select your App -> Page -> get Page Token) and paste it in Settings -> Facebook."
                )
        else:
            progress_cb(100, f"Init failed: {err}")
            raise Exception(f"Facebook init upload failed: {err}")

    video_id = init_data["video_id"]
    upload_session_id = init_data.get("upload_session_id", "")
    progress_cb(30, f"Upload session started (video_id: {video_id})")

    # Step 2: Upload video file to rupload.facebook.com
    progress_cb(40, f"Uploading video ({file_size_mb:.1f} MB)...")
    upload_url = f"https://rupload.facebook.com/video-upload/{FB_API_VERSION}/{video_id}"
    with open(video_path, "rb") as f:
        upload_resp = requests.post(
            upload_url,
            headers={
                "Authorization": f"OAuth {access_token}",
                "offset": "0",
                "file_size": str(file_size),
            },
            data=f,
            timeout=(30, 900),
        )
    upload_data = upload_resp.json()
    if not upload_data.get("success"):
        err = upload_data.get("error", {}).get("message", str(upload_data))
        if _token_expired_message(err):
            progress_cb(5, f"Token invalid during upload — trying auto-extend...")
            refreshed, ok = _auto_extend_and_retry(config, progress_cb, access_token)
            if ok:
                access_token = refreshed
                with open(video_path, "rb") as f:
                    upload_resp = requests.post(
                        upload_url,
                        headers={
                            "Authorization": f"OAuth {access_token}",
                            "offset": "0",
                            "file_size": str(file_size),
                        },
                        data=f,
                        timeout=(30, 900),
                    )
                upload_data = upload_resp.json()
                if upload_data.get("success"):
                    pass
                else:
                    err2 = upload_data.get("error", {}).get("message", str(upload_data))
                    progress_cb(100, f"Upload failed after retry: {err2}")
                    raise ValueError(f"Facebook upload failed after token refresh: {err2}")
            else:
                progress_cb(100, f"Token expired during upload and auto-extend failed")
                raise ValueError(
                    "Facebook token expired. Generate a new one in Graph API Explorer "
                    "and paste it in Settings -> Facebook."
                )
        else:
            progress_cb(100, f"Upload failed: {err}")
            raise Exception(f"Facebook file upload failed: {err}")
    progress_cb(70, "Video uploaded successfully")

    # Step 3: Finish upload session (Facebook may still be processing after this)
    progress_cb(80, "Publishing reel...")
    publish_url = f"https://graph.facebook.com/{FB_API_VERSION}/{page_id}/videos"
    publish_resp = requests.post(publish_url, data={
        "upload_phase": "finish",
        "video_id": video_id,
        "upload_session_id": upload_session_id,
        "access_token": access_token,
        "video_type": "REEL",
        "title": video_title,
        "description": description[:200] if description else "",
    }, timeout=(15, 120))
    publish_data = publish_resp.json()

    if publish_resp.status_code != 200 or not publish_data.get("success"):
        err = publish_data.get("error", {}).get("message", str(publish_data))
        if _token_expired_message(err):
            progress_cb(5, f"Token invalid during publish — trying auto-extend...")
            refreshed, ok = _auto_extend_and_retry(config, progress_cb, access_token)
            if ok:
                access_token = refreshed
                publish_resp = requests.post(publish_url, data={
                    "upload_phase": "finish",
                    "video_id": video_id,
                    "upload_session_id": upload_session_id,
                    "access_token": access_token,
                    "video_type": "REEL",
                    "title": video_title,
                    "description": description[:200] if description else "",
                }, timeout=(15, 120))
                publish_data = publish_resp.json()
                if publish_resp.status_code == 200 and publish_data.get("success"):
                    pass
                else:
                    err2 = publish_data.get("error", {}).get("message", str(publish_data))
                    progress_cb(100, f"Publish failed after retry: {err2}")
                    raise ValueError(f"Facebook publish failed after token refresh: {err2}")
            else:
                progress_cb(100, f"Token expired during publish and auto-extend failed")
                raise ValueError(
                    "Facebook token expired. Generate a new one in Graph API Explorer "
                    "and paste it in Settings -> Facebook."
                )
        else:
            progress_cb(100, f"Publish failed: {err}")
            raise Exception(f"Facebook publish reel failed: {err}")

    reel_id = publish_data.get("id") or publish_data.get("post_id") or "unknown"

    # Best-effort: upload thumbnail (if present). This repo generates thumbnail.jpg, but the
    # old uploader never sent it to Facebook.
    thumb_path = _infer_thumbnail_path(video_path, thumbnail_path)
    if thumb_path:
        progress_cb(85, "Uploading thumbnail...")
        ok, thumb_msg = _try_set_thumbnail(video_id, access_token, thumb_path)
        if not ok:
            # Don't fail the upload just because cover upload failed.
            progress_cb(85, f"Thumbnail upload skipped: {thumb_msg}")

    # Verify publish state; if it looks like a draft/unpublished video, attempt to publish.
    progress_cb(90, "Verifying publish status...")
    permalink_url = None
    published = None
    video_status = None

    # Facebook can take time to flip state from processing/unpublished to published.
    # Poll a bit so we don't mark the task complete while it still sits in drafts.
    for attempt in range(15):
        info = _get_video_info(video_id, access_token)
        permalink_url = info.get("permalink_url") or permalink_url
        published = info.get("published", published)
        st = info.get("status")
        if isinstance(st, dict):
            video_status = st.get("video_status") or video_status

        # If it is published already (or we can't tell), stop polling.
        if published is True or published is None:
            break

        # Attempt to publish once if it appears unpublished.
        if attempt == 0 and published is False:
            ok, pub_msg = _try_publish_video(video_id, access_token)
            progress_cb(92, f"Publish attempt: {pub_msg if ok else pub_msg}")

        time.sleep(4)

    reel_url = permalink_url or f"https://www.facebook.com/reel/{reel_id}"
    msg = publish_data.get("message", "").lower()
    if (published is False) or (isinstance(video_status, str) and video_status.lower() == "draft"):
        # This matches the user-visible symptom: it lands in drafts and lacks publishing.
        raise Exception(
            "Facebook reports the video is still unpublished (draft). "
            "This usually means the token lacks required Page permissions or Facebook still needs processing. "
            f"Check drafts in Meta Business Suite. video_id={video_id} url={reel_url}"
        )

    if "processing" in msg:
        progress_cb(100, f"Reel uploaded (processing). ID: {reel_id}")
    else:
        progress_cb(100, f"Reel uploaded. ID: {reel_id}")

    from app import upload_registry
    upload_registry.record_upload(
        video_path, platform="facebook",
        remote_id=reel_id, url=reel_url,
    )

    return {"id": reel_id, "video_id": video_id, "url": reel_url, "published": published}


def repair_reel(video_id, progress_cb, config, thumbnail_path=None):
    """Best-effort repair when an upload landed in Facebook drafts.

    Tries to (1) set preferred thumbnail and (2) force published=true, then verifies state.
    """
    page_id, access_token, app_id, app_secret = _get_fb_config(config)

    if not access_token:
        raise ValueError("Facebook access token not set in Settings tab")
    if not page_id:
        raise ValueError("Facebook Page ID not set in Settings tab")

    # Auto-extend short-lived token to 60 days if we have app credentials.
    if app_id and app_secret:
        new_token = _exchange_long_lived_token(app_id, app_secret, access_token)
        if new_token and new_token != access_token:
            access_token = new_token
            fb = config.setdefault("facebook", {})
            fb["access_token"] = access_token
            with open(_CONFIG_PATH, "w") as f:
                json.dump(config, f, indent=4)

    access_token = _ensure_page_token(page_id, access_token)

    valid, msg = _validate_token(access_token, page_id=page_id)
    if not valid:
        raise ValueError(f"Facebook token invalid: {msg}")

    progress_cb(10, f"Repairing Facebook video: {video_id}")

    if thumbnail_path and os.path.exists(thumbnail_path):
        progress_cb(35, "Uploading thumbnail...")
        _try_set_thumbnail(video_id, access_token, thumbnail_path)

    progress_cb(60, "Attempting to publish...")
    _try_publish_video(video_id, access_token)

    progress_cb(80, "Verifying status...")
    info = _get_video_info(video_id, access_token)
    published = info.get("published")
    permalink_url = info.get("permalink_url")

    if published is False:
        raise Exception(
            "Facebook still reports this video as unpublished/draft after repair attempt. "
            "Double-check your token is a Page token with pages_manage_posts and that the Page allows Reels publishing."
        )

    progress_cb(100, f"Repair complete. URL: {permalink_url or ''}")
    return {"video_id": video_id, "published": published, "url": permalink_url}


def extend_token_cli():
    """CLI entry point: extend the stored Facebook token to 60 days.

    Usage:  python -c "from upload.facebook_uploader import extend_token_cli; extend_token_cli()"
        or:  python upload/facebook_uploader.py
    """
    import sys
    config_path = "config.json"
    with open(config_path) as f:
        config = json.load(f)

    page_id, access_token, app_id, app_secret = _get_fb_config(config)
    if not app_id or not app_secret:
        print("ERROR: facebook.app_id and facebook.app_secret must be set in config.json")
        sys.exit(1)
    if not access_token:
        print("ERROR: facebook.access_token not set")
        sys.exit(1)

    print(f"Exchanging token for long-lived (60-day) version...")
    new_token = _exchange_long_lived_token(app_id, app_secret, access_token)
    if not new_token:
        print("FAILED: Token exchange returned no result. The current token may already be long-lived or invalid.")
        sys.exit(1)
    if new_token == access_token:
        print("Token is unchanged — it may already be a long-lived token.")
        return

    fb = config.setdefault("facebook", {})
    fb["access_token"] = new_token
    with open(config_path, "w") as f:
        json.dump(config, f, indent=4)
    print("SUCCESS: Token extended to 60 days and saved to config.json")


if __name__ == "__main__":
    extend_token_cli()


def verify_token(config):
    page_id, access_token, app_id, app_secret = _get_fb_config(config)

    if not access_token:
        return False, "No token configured"

    # Auto-extend short-lived token to 60 days if we have app credentials.
    extended = False
    if app_id and app_secret:
        new_token = _exchange_long_lived_token(app_id, app_secret, access_token)
        if new_token and new_token != access_token:
            access_token = new_token
            extended = True
            fb = config.setdefault("facebook", {})
            fb["access_token"] = access_token
            with open(_CONFIG_PATH, "w") as f:
                json.dump(config, f, indent=4)

    # Show whether the token is usable for publishing endpoints.
    page_token = _ensure_page_token(page_id, access_token)
    valid, msg = _validate_token(page_token, page_id=page_id)
    if not valid:
        return False, msg

    probe = requests.get(
        f"https://graph.facebook.com/{FB_API_VERSION}/{page_id}/videos",
        params={"access_token": page_token, "limit": 1},
        timeout=20,
    )
    pdata = probe.json()
    if probe.status_code >= 400 or pdata.get("error"):
        err = (pdata.get("error") or {}).get("message", str(pdata))
        if _is_page_token_required_error(pdata):
            return False, "This looks like a USER token. Generate a Page access token (or grant pages_show_list so the app can derive one)."
        return False, f"Token validated but cannot access /videos: {err}"

    # If we derived a different token, tell the user.
    result = f"Authenticated for publishing as Page: {msg}"
    if extended:
        result += " (auto-extended to 60 days)"
    elif page_token != access_token:
        result += " (derived Page access token from user token)"
    return True, result
