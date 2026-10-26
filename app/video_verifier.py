import os
import re
import json
import logging
import requests
from datetime import datetime

from PyQt6.QtCore import QThread, pyqtSignal

log = logging.getLogger("video_verifier")


def format_count(val):
    """Format numeric metrics cleanly (e.g. 1.2K, 3.4M)."""
    if val is None or val < 0:
        return "--"
    try:
        val = int(val)
    except (ValueError, TypeError):
        return "--"
    if val >= 1_000_000_000:
        return f"{val / 1_000_000_000:.1f}B"
    if val >= 1_000_000:
        return f"{val / 1_000_000:.1f}M"
    if val >= 1_000:
        return f"{val / 1_000:.1f}K"
    return f"{val:,}"


def build_video_url(platform, remote_id, saved_url=None):
    """Derive standard web URL for video if not already present."""
    if saved_url and saved_url.startswith("http"):
        return saved_url
    if not remote_id:
        return None
    clean_id = str(remote_id).strip()
    if platform in ("youtube", "youtube_short"):
        return f"https://www.youtube.com/watch?v={clean_id}"
    elif platform == "facebook":
        return f"https://www.facebook.com/reel/{clean_id}"
    elif platform == "tiktok":
        return f"https://www.tiktok.com/@video/{clean_id}"
    return None


def verify_youtube(remote_id, url=None, config=None):
    """Verify YouTube video status and fetch views, likes, and comments."""
    if not url and remote_id:
        url = f"https://www.youtube.com/watch?v={remote_id}"

    # Fallback to public extraction via yt_dlp
    try:
        import yt_dlp
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "socket_timeout": 10,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if info:
                views = info.get("view_count") or 0
                likes = info.get("like_count") or 0
                comments = info.get("comment_count") or 0
                title = info.get("title") or "YouTube Video"
                return {
                    "verified": True,
                    "status": "Verified Live",
                    "views": views,
                    "views_str": format_count(views),
                    "likes": likes,
                    "likes_str": format_count(likes),
                    "comments": comments,
                    "comments_str": format_count(comments),
                    "title": title,
                    "url": url,
                    "checked_at": datetime.now().isoformat(),
                    "error": None,
                }
    except Exception as e:
        err_msg = str(e)
        # Check if oEmbed recognizes it
        try:
            oembed_url = f"https://www.youtube.com/oembed?url={url}&format=json"
            r = requests.get(oembed_url, timeout=8)
            if r.status_code == 200:
                data = r.json()
                return {
                    "verified": True,
                    "status": "Verified Live",
                    "views": 0,
                    "views_str": "--",
                    "likes": 0,
                    "likes_str": "--",
                    "comments": 0,
                    "comments_str": "--",
                    "title": data.get("title", "YouTube Video"),
                    "url": url,
                    "checked_at": datetime.now().isoformat(),
                    "error": None,
                }
            elif r.status_code in (401, 403):
                return {
                    "verified": True,
                    "status": "Private / Restricted",
                    "views": 0,
                    "views_str": "--",
                    "likes": 0,
                    "likes_str": "--",
                    "comments": 0,
                    "comments_str": "--",
                    "title": "Private Video",
                    "url": url,
                    "checked_at": datetime.now().isoformat(),
                    "error": "Video is private or restricted",
                }
            elif r.status_code == 404:
                return {
                    "verified": False,
                    "status": "Not Found / Deleted",
                    "views": 0,
                    "views_str": "--",
                    "likes": 0,
                    "likes_str": "--",
                    "comments": 0,
                    "comments_str": "--",
                    "title": "Deleted Video",
                    "url": url,
                    "checked_at": datetime.now().isoformat(),
                    "error": "Video not found or was removed",
                }
        except Exception:
            pass

        return {
            "verified": False,
            "status": "Check Failed",
            "views": 0,
            "views_str": "--",
            "likes": 0,
            "likes_str": "--",
            "comments": 0,
            "comments_str": "--",
            "title": "",
            "url": url,
            "checked_at": datetime.now().isoformat(),
            "error": err_msg[:120],
        }


def verify_facebook(remote_id, url=None, config=None):
    """Verify Facebook Reel status and fetch views, likes, and comments."""
    if not url and remote_id:
        url = f"https://www.facebook.com/reel/{remote_id}"

    # Try Facebook Graph API if token available
    fb_cfg = (config or {}).get("facebook", {})
    token = os.environ.get("FACEBOOK_ACCESS_TOKEN") or fb_cfg.get("access_token")
    if token and remote_id and not str(remote_id).startswith("_"):
        try:
            graph_url = f"https://graph.facebook.com/v22.0/{remote_id}"
            params = {
                "fields": "id,title,description,published,views,likes.summary(true),comments.summary(true)",
                "access_token": token,
            }
            r = requests.get(graph_url, params=params, timeout=10)
            if r.status_code == 200:
                data = r.json()
                views = data.get("views") or 0
                likes = data.get("likes", {}).get("summary", {}).get("total_count", 0)
                comments = data.get("comments", {}).get("summary", {}).get("total_count", 0)
                is_pub = data.get("published", True)
                status = "Verified Live" if is_pub else "Processing"
                return {
                    "verified": True,
                    "status": status,
                    "views": views,
                    "views_str": format_count(views),
                    "likes": likes,
                    "likes_str": format_count(likes),
                    "comments": comments,
                    "comments_str": format_count(comments),
                    "title": data.get("title") or "Facebook Reel",
                    "url": url,
                    "checked_at": datetime.now().isoformat(),
                    "error": None,
                }
        except Exception as e:
            log.warning("FB Graph API check failed: %s", e)

    # Fallback to public inspection via yt_dlp
    try:
        import yt_dlp
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "socket_timeout": 10,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if info:
                views = info.get("view_count") or 0
                likes = info.get("like_count") or 0
                comments = info.get("comment_count") or 0
                title = info.get("title") or "Facebook Reel"
                return {
                    "verified": True,
                    "status": "Verified Live",
                    "views": views,
                    "views_str": format_count(views),
                    "likes": likes,
                    "likes_str": format_count(likes),
                    "comments": comments,
                    "comments_str": format_count(comments),
                    "title": title,
                    "url": url,
                    "checked_at": datetime.now().isoformat(),
                    "error": None,
                }
    except Exception:
        # Check HTTP status of reel page
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            r = requests.head(url, headers=headers, timeout=8, allow_redirects=True)
            if r.status_code == 200:
                return {
                    "verified": True,
                    "status": "Verified Live",
                    "views": 0,
                    "views_str": "--",
                    "likes": 0,
                    "likes_str": "--",
                    "comments": 0,
                    "comments_str": "--",
                    "title": "Facebook Reel",
                    "url": url,
                    "checked_at": datetime.now().isoformat(),
                    "error": None,
                }
            elif r.status_code == 404:
                return {
                    "verified": False,
                    "status": "Not Found / Deleted",
                    "views": 0,
                    "views_str": "--",
                    "likes": 0,
                    "likes_str": "--",
                    "comments": 0,
                    "comments_str": "--",
                    "title": "Deleted Reel",
                    "url": url,
                    "checked_at": datetime.now().isoformat(),
                    "error": "Reel not found on Facebook",
                }
        except Exception as e2:
            return {
                "verified": False,
                "status": "Check Failed",
                "views": 0,
                "views_str": "--",
                "likes": 0,
                "likes_str": "--",
                "comments": 0,
                "comments_str": "--",
                "title": "",
                "url": url,
                "checked_at": datetime.now().isoformat(),
                "error": str(e2)[:120],
            }

    return {
        "verified": True,
        "status": "Verified (Logged)",
        "views": 0,
        "views_str": "--",
        "likes": 0,
        "likes_str": "--",
        "comments": 0,
        "comments_str": "--",
        "title": "Facebook Reel",
        "url": url,
        "checked_at": datetime.now().isoformat(),
        "error": None,
    }


def verify_tiktok(remote_id, url=None, config=None):
    """Verify TikTok video status and fetch views, likes, and comments."""
    if not url and remote_id:
        url = f"https://www.tiktok.com/@video/{remote_id}"

    # Try official API if publish_id
    tt_cfg = (config or {}).get("tiktok", {})
    token = os.environ.get("TIKTOK_ACCESS_TOKEN") or tt_cfg.get("access_token")
    if token and remote_id and not str(remote_id).startswith("session_"):
        try:
            status_url = "https://open.tiktokapis.com/v2/post/publish/status/fetch/"
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json; charset=UTF-8",
            }
            r = requests.post(status_url, headers=headers, json={"publish_id": str(remote_id)}, timeout=10)
            data = r.json()
            p_status = data.get("data", {}).get("status")
            if p_status == "SUCCESS":
                return {
                    "verified": True,
                    "status": "Verified Live",
                    "views": 0,
                    "views_str": "--",
                    "likes": 0,
                    "likes_str": "--",
                    "comments": 0,
                    "comments_str": "--",
                    "title": "TikTok Video",
                    "url": url or "https://www.tiktok.com",
                    "checked_at": datetime.now().isoformat(),
                    "error": None,
                }
            elif p_status in ("PROCESSING_UPLOAD", "PROCESSING_DOWNLOAD"):
                return {
                    "verified": True,
                    "status": "Processing",
                    "views": 0,
                    "views_str": "--",
                    "likes": 0,
                    "likes_str": "--",
                    "comments": 0,
                    "comments_str": "--",
                    "title": "TikTok Video",
                    "url": url or "https://www.tiktok.com",
                    "checked_at": datetime.now().isoformat(),
                    "error": "Still processing on TikTok",
                }
        except Exception:
            pass

    # Public check via oEmbed or yt_dlp if real url exists
    if url and "tiktok.com" in url and not url.endswith("@video/"):
        try:
            import yt_dlp
            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "skip_download": True,
                "socket_timeout": 10,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if info:
                    views = info.get("view_count") or 0
                    likes = info.get("like_count") or 0
                    comments = info.get("comment_count") or 0
                    return {
                        "verified": True,
                        "status": "Verified Live",
                        "views": views,
                        "views_str": format_count(views),
                        "likes": likes,
                        "likes_str": format_count(likes),
                        "comments": comments,
                        "comments_str": format_count(comments),
                        "title": info.get("title") or "TikTok Video",
                        "url": url,
                        "checked_at": datetime.now().isoformat(),
                        "error": None,
                    }
        except Exception:
            pass

    return {
        "verified": True,
        "status": "Uploaded (Session)",
        "views": 0,
        "views_str": "--",
        "likes": 0,
        "likes_str": "--",
        "comments": 0,
        "comments_str": "--",
        "title": "TikTok Video",
        "url": url or "https://www.tiktok.com",
        "checked_at": datetime.now().isoformat(),
        "error": None,
    }


def verify_entry(entry, config=None):
    """Verify single registry entry and return metrics dictionary."""
    platform = entry.get("platform", "unknown")
    remote_id = entry.get("remote_id", "")
    saved_url = entry.get("url", "")
    url = build_video_url(platform, remote_id, saved_url)

    if platform.startswith("youtube"):
        return verify_youtube(remote_id, url=url, config=config)
    elif platform == "facebook":
        return verify_facebook(remote_id, url=url, config=config)
    elif platform == "tiktok":
        return verify_tiktok(remote_id, url=url, config=config)
    else:
        return {
            "verified": bool(remote_id),
            "status": "Uploaded" if remote_id else "Unverified",
            "views": 0,
            "views_str": "--",
            "likes": 0,
            "likes_str": "--",
            "comments": 0,
            "comments_str": "--",
            "title": "",
            "url": url or "",
            "checked_at": datetime.now().isoformat(),
            "error": None,
        }


class BatchVerifierWorker(QThread):
    """Background worker that verifies all uploaded videos and fetches view counts."""
    progress = pyqtSignal(int, int, str)
    item_verified = pyqtSignal(dict, dict)  # (entry, metrics)
    finished = pyqtSignal(dict)  # summary dict

    def __init__(self, entries, config, parent=None):
        super().__init__(parent)
        self.entries = entries
        self.config = config
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        total = len(self.entries)
        total_views = 0
        total_likes = 0
        total_comments = 0
        verified_count = 0

        for idx, entry in enumerate(self.entries):
            if self._is_cancelled:
                break
            vpath = entry.get("path", "")
            fname = os.path.basename(vpath) if vpath else "Video"
            plat = entry.get("platform", "").title()
            self.progress.emit(idx + 1, total, f"Checking {plat}: {fname[:30]}...")

            metrics = verify_entry(entry, self.config)

            # Persist metrics in uploads.json
            try:
                from app import upload_registry
                upload_registry.update_item_metrics(entry.get("path"), entry.get("platform"), metrics)
            except Exception as e:
                log.warning("Could not persist metrics for %s: %s", vpath, e)

            if metrics.get("verified"):
                verified_count += 1
            total_views += metrics.get("views") or 0
            total_likes += metrics.get("likes") or 0
            total_comments += metrics.get("comments") or 0

            self.item_verified.emit(entry, metrics)

        summary = {
            "total_checked": total,
            "verified_count": verified_count,
            "total_views": total_views,
            "total_views_str": format_count(total_views),
            "total_likes": total_likes,
            "total_likes_str": format_count(total_likes),
            "total_comments": total_comments,
            "total_comments_str": format_count(total_comments),
        }
        self.finished.emit(summary)


def sync_channel_videos(channel_identifier, platform="youtube", max_results=50, config=None):
    """
    Automatically scrape or fetch all published videos from a channel or page.
    Supports YouTube (@handle or channel URL) and Facebook (page_id).
    Returns list of dicts: {'platform', 'remote_id', 'url', 'title', 'views', 'path'}
    """
    results = []
    if platform in ("youtube", "youtube_short"):
        chan = channel_identifier.strip()
        # Protect against numeric Facebook Page IDs mistakenly passed to YouTube
        if chan.isdigit() or (chan.startswith("@") and chan[1:].isdigit()):
            log.warning("Skipping YouTube channel sync: '%s' is a numeric ID, not a YouTube channel handle.", chan)
            return results

        if not chan.startswith("http"):
            if not chan.startswith("@"):
                chan = "@" + chan
            base_chan = f"https://www.youtube.com/{chan}"
        else:
            base_chan = chan.split("/videos")[0].split("/shorts")[0].split("/featured")[0].rstrip("/")

        targets = [f"{base_chan}/videos", f"{base_chan}/shorts"]
        seen_vids = set()

        try:
            import yt_dlp
            ydl_opts = {
                "extract_flat": True,
                "quiet": True,
                "no_warnings": True,
                "playlistend": max_results,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                for turl in targets:
                    try:
                        r = ydl.extract_info(turl, download=False)
                        entries = r.get("entries", [])
                        for e in entries:
                            vid = e.get("id")
                            if not vid or vid in seen_vids:
                                continue
                            seen_vids.add(vid)
                            vurl = f"https://youtu.be/{vid}"
                            title = e.get("title", f"YouTube Video {vid}")
                            views = e.get("view_count")
                            is_short = "/shorts" in turl
                            results.append({
                                "platform": "youtube_short" if is_short else "youtube",
                                "remote_id": vid,
                                "url": vurl,
                                "title": title,
                                "views": views or 0,
                                "path": vurl,
                            })
                    except Exception as ex_t:
                        log.debug("Target %s: %s", turl, ex_t)
        except Exception as ex:
            log.warning("YouTube channel sync error for %s: %s", chan, ex)


    elif platform == "facebook":
        page_id = channel_identifier.strip()
        from dotenv import load_dotenv
        import urllib.request
        load_dotenv()
        token = ""
        if config and isinstance(config, dict):
            token = config.get("facebook", {}).get("access_token", "")
        if not token:
            token = os.environ.get("FACEBOOK_ACCESS_TOKEN", "")

        if token and page_id:
            try:
                fb_url = f"https://graph.facebook.com/v19.0/{page_id}/video_reels?fields=id,description,created_time&access_token={token}&limit={max_results}"
                req = urllib.request.Request(fb_url)
                with urllib.request.urlopen(req, timeout=12) as resp:
                    data = json.loads(resp.read().decode())
                for item in data.get("data", []):
                    rid = item.get("id")
                    rurl = f"https://www.facebook.com/reel/{rid}"
                    desc = item.get("description", "")
                    title = desc.split("\n")[0][:80] if desc else f"Facebook Reel {rid}"
                    results.append({
                        "platform": "facebook",
                        "remote_id": rid,
                        "url": rurl,
                        "title": title,
                        "views": 0,
                        "path": rurl,
                    })
            except Exception as ex:
                log.warning("Facebook page sync error: %s", ex)

    elif platform == "tiktok":
        user_handle = channel_identifier.strip()
        if not user_handle.startswith("http"):
            clean_name = user_handle.lstrip("@")
            base_url = f"https://www.tiktok.com/@{clean_name}"
        else:
            base_url = user_handle.rstrip("/")
            clean_name = base_url.split("@")[-1].split("/")[0] if "@" in base_url else ""

        seen_vids = set()

        # 1. Check official TikTok API if access token is available in config
        tt_cfg = (config or {}).get("tiktok", {})
        token = os.environ.get("TIKTOK_ACCESS_TOKEN") or tt_cfg.get("access_token")
        if token:
            try:
                import urllib.request
                api_url = "https://open.tiktokapis.com/v2/video/list/?fields=id,title,video_description,share_url,view_count,like_count"
                payload = json.dumps({"max_count": min(max_results, 50)}).encode("utf-8")
                req = urllib.request.Request(
                    api_url,
                    data=payload,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json; charset=UTF-8",
                    },
                )
                with urllib.request.urlopen(req, timeout=12) as resp:
                    data = json.loads(resp.read().decode())
                videos_list = data.get("data", {}).get("videos", [])
                for itm in videos_list:
                    vid = str(itm.get("id"))
                    if vid and vid not in seen_vids:
                        seen_vids.add(vid)
                        vurl = itm.get("share_url") or f"https://www.tiktok.com/@{clean_name}/video/{vid}"
                        title = itm.get("title") or itm.get("video_description") or f"TikTok Video {vid}"
                        results.append({
                            "platform": "tiktok",
                            "remote_id": vid,
                            "url": vurl,
                            "title": title[:80],
                            "views": itm.get("view_count") or 0,
                            "path": vurl,
                        })
            except Exception as ex:
                log.debug("TikTok API sync error: %s", ex)

        # 2. Extract videos via yt-dlp
        if not results:
            try:
                import yt_dlp
                ydl_opts = {
                    "extract_flat": True,
                    "quiet": True,
                    "no_warnings": True,
                    "playlistend": max_results,
                }
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    r = ydl.extract_info(base_url, download=False)
                    for e in r.get("entries", []):
                        vid = str(e.get("id", ""))
                        if not vid or vid in seen_vids:
                            continue
                        seen_vids.add(vid)
                        vurl = e.get("url") or f"https://www.tiktok.com/@{clean_name}/video/{vid}"
                        title = e.get("title") or f"TikTok Video {vid}"
                        views = e.get("view_count") or 0
                        results.append({
                            "platform": "tiktok",
                            "remote_id": vid,
                            "url": vurl,
                            "title": title[:80],
                            "views": views,
                            "path": vurl,
                        })
            except Exception as ex:
                log.debug("TikTok yt-dlp sync error: %s", ex)

    return results

