import os
import json
import time
import threading
import requests

FB_API_VERSION = "v22.0"
_CONFIG_PATH = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config.json"))

_PAGE_TOKEN_CACHE = {}

# Rate limiter: enforce minimum spacing between Facebook uploads
_upload_lock = threading.Lock()
_last_upload_time = 0.0
_MIN_UPLOAD_INTERVAL = 60  # seconds between Facebook uploads
_MAX_RETRIES = 5


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


def _is_rate_limit_error(data):
    """Check if the error is Facebook rate-limit (code 368)."""
    if not isinstance(data, dict):
        return False
    err = data.get("error") or {}
    code = err.get("code")
    if code == 368:
        return True
    msg = (err.get("message") or "").lower()
    if "limit how often" in msg or "going too fast" in msg:
        return True
    return False


def _rate_limit_wait(progress_cb=None):
    """Enforce minimum interval between Facebook uploads."""
    global _last_upload_time
    with _upload_lock:
        elapsed = time.time() - _last_upload_time
        if elapsed < _MIN_UPLOAD_INTERVAL:
            wait = _MIN_UPLOAD_INTERVAL - elapsed
            if progress_cb:
                progress_cb(0, f"Rate-limit cooldown: waiting {wait:.0f}s")
            time.sleep(wait)
        _last_upload_time = time.time()


def _retry_with_backoff(fn, progress_cb, max_retries=_MAX_RETRIES):
    """Execute fn with exponential backoff on rate-limit (368) errors.

    ``fn`` must return (response_data_dict, is_error_bool).
    If is_error is True, response_data_dict contains the error payload.
    """
    for attempt in range(max_retries + 1):
        data, is_error = fn()
        if not is_error:
            return data
        if not _is_rate_limit_error(data):
            err = data.get("error", {}).get("message", str(data))
            raise Exception(f"Facebook API error: {err}")
        if attempt >= max_retries:
            err = data.get("error", {}).get("message", str(data))
            raise Exception(f"Facebook rate-limit exceeded after {max_retries} retries: {err}")
        wait = min(60 * (2 ** attempt), 600)
        if progress_cb:
            progress_cb(0, f"Rate-limited (attempt {attempt+1}/{max_retries}), waiting {wait}s...")
        time.sleep(wait)
    return None


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

        # Check token has publishing permissions (best-effort, may fail for Page tokens)
        try:
            perm_resp = requests.get(
                f"https://graph.facebook.com/{FB_API_VERSION}/me/permissions",
                params={"access_token": access_token},
                timeout=15,
            )
            perm_data = perm_resp.json()
            if "data" in perm_data:
                granted = {p.get("permission"): p.get("status")
                           for p in perm_data["data"] if isinstance(p, dict)}
                missing = []
                for needed in ("pages_manage_posts", "publish_video", "pages_read_engagement"):
                    if granted.get(needed) != "granted":
                        missing.append(needed)
                if missing:
                    return False, (
                        f"Token is missing required permissions: {', '.join(missing)}. "
                        "Regenerate the token in Graph API Explorer with these permissions checked."
                    )
        except Exception:
            pass

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


def _ensure_full_reel_url(url, reel_id):
    """Facebook v22.0 returns permalink_url as a relative path (/reel/{id}/).

    Ensure we always store a full https URL so the Upload History link works.
    """
    if url and url.startswith("http"):
        return url
    return f"https://www.facebook.com/reel/{reel_id}"


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
    """Reload secrets from config.json so the app always uses the latest saved token.

    Also syncs ``os.environ`` so if ``load_dotenv()`` loaded a stale token earlier,
    the refreshed value takes precedence (``_get_fb_config`` prefers env vars).
    """
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
            env_key_map = {
                "access_token": "FACEBOOK_ACCESS_TOKEN",
                "page_id": "FACEBOOK_PAGE_ID",
                "app_id": "FACEBOOK_APP_ID",
                "app_secret": "FACEBOOK_APP_SECRET",
            }
            for cfg_key, env_key in env_key_map.items():
                if cfg_key in fb_disk and env_key in os.environ:
                    os.environ[env_key] = fb_disk[cfg_key]
        except Exception:
            pass


def _tags_to_hashtags(tags):
    """Convert a list of tag strings to Facebook-style hashtags appended to description."""
    if not tags:
        return ""
    hashtags = []
    for tag in tags:
        t = tag.strip()
        if not t:
            continue
        if t.startswith("#"):
            hashtags.append(t)
        else:
            hashtags.append("#" + "".join(word.capitalize() for word in t.split()))
    return "\n\n" + " ".join(hashtags)


def upload_reel(video_path, title, description, progress_cb, config, thumbnail_path=None, tags=None):
    _reload_config_from_disk(config)
    page_id, access_token, app_id, app_secret = _get_fb_config(config)

    if not access_token:
        progress_cb(100, "Facebook access token not configured")
        raise ValueError("Facebook access token not set in Settings tab")

    if not page_id:
        progress_cb(100, "Facebook Page ID not configured")
        raise ValueError("Facebook Page ID not set in Settings tab")

    # Skip if already uploaded (prevents re-upload from queue re-scan).
    from app import upload_registry
    existing = upload_registry.find_existing(video_path, platform="facebook")
    if existing and existing.get("remote_id"):
        rid = existing.get("remote_id")
        progress_cb(100, f"Already uploaded (registry). ID: {rid}")
        return {"id": rid, "url": existing.get("url"), "existing": True}

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
    video_title = title.strip()[:100] if title and title.strip() else os.path.splitext(os.path.basename(video_path))[0].replace("_", " ").title()
    hashtags_str = _tags_to_hashtags(tags) if tags else ""
    full_description = (description or "").strip()
    if hashtags_str:
        full_description += hashtags_str

    # Enforce minimum interval between uploads to avoid rate-limiting
    _rate_limit_wait(progress_cb)

    # Step 1: Initialize upload session
    progress_cb(10, "Initializing upload session...")
    init_url = f"https://graph.facebook.com/{FB_API_VERSION}/{page_id}/video_reels"

    def _do_init():
        r = requests.post(init_url, data={
            "upload_phase": "start",
            "access_token": access_token,
        }, timeout=(15, 60))
        return r.json(), ("video_id" not in r.json())

    try:
        init_data = _retry_with_backoff(_do_init, progress_cb)
    except Exception as e:
        err = str(e)
        # Check for token expiry separately
        resp = requests.post(init_url, data={
            "upload_phase": "start",
            "access_token": access_token,
        }, timeout=(15, 60))
        init_data = resp.json()
        err_msg = init_data.get("error", {}).get("message", str(init_data))
        if _token_expired_message(err_msg):
            progress_cb(5, "Token invalid (code 190) — trying auto-extend...")
            refreshed, ok = _auto_extend_and_retry(config, progress_cb, access_token)
            if ok:
                access_token = refreshed
                try:
                    init_data = _retry_with_backoff(_do_init, progress_cb)
                except Exception as e2:
                    progress_cb(100, f"Init failed after retry: {e2}")
                    raise ValueError(f"Facebook init failed after token refresh: {e2}")
            else:
                progress_cb(100, "Token expired and auto-extend failed")
                raise ValueError(
                    "Facebook token expired. Generate a new one in Graph API Explorer "
                    "(select your App -> Page -> get Page Token) and paste it in Settings -> Facebook."
                )
        else:
            progress_cb(100, f"Init failed: {err_msg}")
            raise Exception(f"Facebook init upload failed: {err}")

    if "video_id" not in init_data:
        err_msg = init_data.get("error", {}).get("message", str(init_data))
        progress_cb(100, f"Init failed: {err_msg}")
        raise Exception(f"Facebook init upload failed: {err_msg}")

    video_id = init_data["video_id"]
    upload_session_id = init_data.get("upload_session_id", "")
    progress_cb(30, f"Upload session started (video_id: {video_id})")

    # Step 2: Upload video file to rupload.facebook.com
    progress_cb(40, f"Uploading video ({file_size_mb:.1f} MB)...")
    upload_url = f"https://rupload.facebook.com/video-upload/{FB_API_VERSION}/{video_id}"

    def _do_upload():
        with open(video_path, "rb") as f:
            r = requests.post(
                upload_url,
                headers={
                    "Authorization": f"OAuth {access_token}",
                    "offset": "0",
                    "file_size": str(file_size),
                },
                data=f,
                timeout=(30, 900),
            )
        data = r.json()
        return data, not data.get("success")

    upload_data, is_error = _do_upload()

    if is_error:
        if _is_rate_limit_error(upload_data):
            try:
                upload_data = _retry_with_backoff(_do_upload, progress_cb)
            except Exception as e:
                progress_cb(100, f"Upload failed after retry: {e}")
                raise
        else:
            err = upload_data.get("error", {}).get("message", str(upload_data))
            if _token_expired_message(err):
                progress_cb(5, "Token invalid during upload — trying auto-extend...")
                refreshed, ok = _auto_extend_and_retry(config, progress_cb, access_token)
                if ok:
                    access_token = refreshed
                    try:
                        upload_data = _retry_with_backoff(_do_upload, progress_cb)
                    except Exception as e:
                        progress_cb(100, f"Upload failed after retry: {e}")
                        raise
                else:
                    progress_cb(100, "Token expired during upload and auto-extend failed")
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
    publish_url = f"https://graph.facebook.com/{FB_API_VERSION}/{page_id}/video_reels"

    def _do_publish():
        r = requests.post(publish_url, data={
            "upload_phase": "finish",
            "video_id": video_id,
            "upload_session_id": upload_session_id,
            "access_token": access_token,
            "published": "true",
            "title": video_title,
            "description": full_description[:1000] if full_description else "",
        }, timeout=(15, 120))
        data = r.json()
        is_error = r.status_code != 200
        if not is_error:
            is_error = not (data.get("success") or data.get("id"))
        return data, is_error

    try:
        publish_data = _retry_with_backoff(_do_publish, progress_cb)
    except Exception as e:
        err_str = str(e)
        api_msg = err_str
        api_code = ""
        api_subcode = ""
        # Try once more without retry to get the raw response for diagnostics
        try:
            raw = requests.post(publish_url, data={
                "upload_phase": "finish",
                "video_id": video_id,
                "upload_session_id": upload_session_id,
                "access_token": access_token,
                "published": "true",
                "title": video_title,
                "description": full_description[:1000] if full_description else "",
            }, timeout=(15, 120))
            raw_data = raw.json()
            err_detail = raw_data.get("error", {})
            api_msg = err_detail.get("message", str(raw_data))
            api_code = str(err_detail.get("code", ""))
            api_subcode = str(err_detail.get("error_subcode", ""))
            progress_cb(80, f"FB API ({api_code}/{api_subcode}): {api_msg[:200]}")
        except Exception:
            pass

        if _token_expired_message(api_msg):
            progress_cb(5, "Token invalid during publish — trying auto-extend...")
            refreshed, ok = _auto_extend_and_retry(config, progress_cb, access_token)
            if ok:
                access_token = refreshed
                publish_data = _retry_with_backoff(_do_publish, progress_cb)
            else:
                raise ValueError(
                    "Facebook token expired. Generate a new one in Graph API Explorer "
                    "and paste it in Settings -> Facebook."
                )
        else:
            raise Exception(
                f"Facebook publish reel failed: {api_msg} "
                f"(code={api_code} subcode={api_subcode} "
                f"video_id={video_id} session_id={upload_session_id})"
            )

    reel_id = publish_data.get("id") or publish_data.get("post_id") or video_id
    if not reel_id:
        err_msg = publish_data.get("error", {}).get("message", str(publish_data))
        raise Exception(
            f"Facebook publish did not return a video ID. The upload completed but the "
            f"video was not published. Check your token permissions. FB says: {err_msg}"
        )

    # Capture permalink_url from publish response if available (saves polling time).
    permalink_url = publish_data.get("permalink_url") or None
    published = publish_data.get("published")
    page_name = None

    # Best-effort: upload thumbnail (if present).
    thumb_path = _infer_thumbnail_path(video_path, thumbnail_path)
    if thumb_path:
        progress_cb(85, "Uploading thumbnail...")
        ok, thumb_msg = _try_set_thumbnail(video_id, access_token, thumb_path)
        if not ok:
            progress_cb(85, f"Thumbnail upload skipped: {thumb_msg}")

    # Verify publish state; poll until we have a valid permalink or timeout.
    progress_cb(90, "Verifying publish status...")
    video_status = None
    processing_error = None

    for attempt in range(60):
        if permalink_url:
            break
        info = _get_video_info(video_id, access_token)
        permalink_url = permalink_url or info.get("permalink_url")
        published = info.get("published", published) if published is None else published
        st = info.get("status")
        if isinstance(st, dict):
            video_status = st.get("video_status") or video_status
            processing_error = st.get("processing_error") or st.get("error") or processing_error
        if not permalink_url and page_name is None:
            page_name = info.get("from", {}).get("name") if isinstance(info.get("from"), dict) else None

        if published is False and attempt >= 5:
            ok, pub_msg = _try_publish_video(video_id, access_token)
            progress_cb(92, f"Publish attempt: {pub_msg}")

        if attempt % 10 == 0:
            elapsed = attempt * 4
            progress_cb(90, f"Waiting for Facebook to process video ({elapsed}s)...")

        time.sleep(4)
    else:
        if processing_error:
            raise Exception(
                f"Facebook processing error: {processing_error}. "
                f"video_id={video_id}"
            )
        if published is False:
            raise Exception(
                "Facebook reports the video is still unpublished (draft) after 4 minutes. "
                "This usually means the token lacks required Page permissions (publish_video, "
                "pages_manage_posts) or the video format is unsupported. "
                f"Check drafts in Meta Business Suite. video_id={video_id}"
            )

    # Double-check: scan the page's actual reel list to confirm the reel is
    # really there AND actually published (not stuck as draft).
    progress_cb(95, "Confirming reel is published on the page...")
    page_found, page_published, page_url = _verify_reel_on_page(reel_id, page_id, access_token)
    if not page_found:
        raise Exception(
            f"Upload claimed success but reel ID {reel_id} was NOT found in the page's "
            f"content library. The video is invisible on Facebook. "
            f"video_id={video_id}"
        )
    if page_published is False:
        raise Exception(
            f"Reel ID {reel_id} was found on the page but is STILL a DRAFT. "
            f"Facebook did not publish it despite receiving 'published': true. "
            f"This usually means the token lacks publish_video permission. "
            f"Check Meta Business Suite drafts. video_id={video_id}"
        )
    if page_published is True:
        published = True
    permalink_url = page_url or permalink_url

    reel_url = _ensure_full_reel_url(permalink_url, reel_id)

    from app import upload_registry
    upload_registry.record_upload(
        video_path, platform="facebook",
        remote_id=reel_id, url=reel_url,
    )

    progress_cb(100, f"Reel published. ID: {reel_id}")
    return {"id": reel_id, "video_id": video_id, "url": reel_url, "published": True}


def _verify_reel_on_page(reel_id, page_id, access_token):
    """Query the page's actual reel list and confirm reel_id exists there.

    Returns (found, published, permalink_url).
    - found: bool — True if the reel ID appears in the page's reel list
    - published: bool or None — None means could not determine
    - permalink_url: str or None — the URL from the page's API if available
    """
    try:
        url = f"https://graph.facebook.com/{FB_API_VERSION}/{page_id}/video_reels"
        resp = requests.get(url, params={
            "access_token": access_token,
            "fields": "id,permalink_url,published,status",
            "limit": 50,
        }, timeout=30)
        data = resp.json()
        if resp.status_code >= 400 or data.get("error"):
            return True, None, None  # can't verify — don't block, might be permission issue
        for reel in data.get("data", []):
            if reel.get("id") == reel_id:
                pub = reel.get("published")
                perm = reel.get("permalink_url")
                return True, pub, perm
        return False, None, None
    except Exception:
        return True, None, None  # don't block on transient errors


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
