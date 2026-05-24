import os
import json
import requests


def upload_reel(video_path, title, description, progress_cb, config):
    fb_config = config.get("facebook", {})
    page_id = fb_config.get("page_id", "")
    access_token = fb_config.get("access_token", "")

    if not access_token:
        progress_cb(100, "Facebook access token not configured")
        raise ValueError("Facebook access token not set in Settings tab")

    if not page_id:
        progress_cb(100, "Facebook Page ID not configured")
        raise ValueError("Facebook Page ID not set in Settings tab")

    progress_cb(10, "Preparing Facebook Reels upload...")

    url = f"https://graph.facebook.com/v19.0/{page_id}/video_reels"
    video_title = title[:100] if title else "Video"

    file_size = os.path.getsize(video_path)
    file_size_mb = file_size / (1024 * 1024)

    progress_cb(30, f"Uploading Reel ({file_size_mb:.1f} MB)...")

    try:
        with open(video_path, "rb") as video_file:
            files = {
                "video_file": (
                    os.path.basename(video_path),
                    video_file,
                    "video/mp4",
                ),
            }
            data = {
                "access_token": access_token,
                "title": video_title,
                "description": description[:200] if description else "",
            }

            response = requests.post(
                url,
                files=files,
                data=data,
                timeout=600,
            )

        result = response.json()

        if response.status_code == 200 and "id" in result:
            progress_cb(100, f"Reel uploaded! ID: {result['id']}")
            return result
        else:
            error_msg = result.get("error", {}).get("message", str(result))
            progress_cb(100, f"Upload failed: {error_msg}")
            raise Exception(f"Facebook upload failed: {error_msg}")

    except requests.exceptions.RequestException as e:
        progress_cb(100, f"Network error: {e}")
        raise


def verify_token(config):
    fb_config = config.get("facebook", {})
    access_token = fb_config.get("access_token", "")
    page_id = fb_config.get("page_id", "")

    if not access_token:
        return False, "No token configured"

    url = "https://graph.facebook.com/v19.0/me"
    params = {"access_token": access_token, "fields": "id,name"}

    try:
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()
        if "id" in data:
            if page_id and data.get("id") != page_id:
                return True, f"Token valid (user: {data.get('name','?')}), but not matching configured Page ID"
            return True, f"Authenticated as: {data.get('name', '?')}"
        else:
            return False, data.get("error", {}).get("message", "Invalid token")
    except Exception as e:
        return False, str(e)
