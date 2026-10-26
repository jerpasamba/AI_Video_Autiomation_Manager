import os
import pickle
import json

PLAYLIST_CACHE_FILE = "playlist_cache.json"

_QUOTA_COST = {
    "videos.insert": 1600,
    "thumbnails.set": 50,
    "playlists.list": 1,
    "playlists.insert": 50,
    "playlistItems.insert": 50,
}

_quota_used = 0

def get_quota_used():
    return _quota_used

def _load_playlist_cache():
    if os.path.exists(PLAYLIST_CACHE_FILE):
        try:
            with open(PLAYLIST_CACHE_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def _save_playlist_cache(cache):
    with open(PLAYLIST_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2)

class YouTubeUploader:
    def __init__(self, client_secret_file=None, token_file="youtube_token.json", progress_cb=None):
        self.client_secret_file = client_secret_file
        self.token_file = token_file
        self.service = None
        self._progress_cb = progress_cb
        self._playlist_cache = _load_playlist_cache()

    def _progress(self, msg):
        cb = self._progress_cb
        if cb:
            try:
                cb(msg)
            except Exception:
                pass

    def _get_authenticated_service(self):
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build

        # youtube.upload is enough for uploads; youtube.force-ssl is needed for
        # playlist operations (create/find playlists, add playlist items).
        SCOPES = [
            "https://www.googleapis.com/auth/youtube.upload",
            "https://www.googleapis.com/auth/youtube.force-ssl",
        ]

        creds = None

        if os.path.exists(self.token_file):
            # If the stored token lacks required scopes, force a re-auth.
            try:
                with open(self.token_file, encoding="utf-8") as f:
                    tok = json.load(f)
                tok_scopes = set(tok.get("scopes") or [])
                if not set(SCOPES).issubset(tok_scopes):
                    creds = None
                else:
                    creds = Credentials.from_authorized_user_file(self.token_file, SCOPES)
            except Exception:
                creds = Credentials.from_authorized_user_file(self.token_file, SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                self._progress("Refreshing YouTube token...")
                try:
                    creds.refresh(Request())
                except Exception as e:
                    self._progress(f"Token refresh failed ({e}), opening browser to re-authenticate...")
                    creds = None

            if not creds or not creds.valid:
                if not self.client_secret_file or not os.path.exists(self.client_secret_file):
                    raise FileNotFoundError(
                        "YouTube API client_secret file not found.\n"
                        "Set it up at: https://console.cloud.google.com/apis/credentials\n"
                        "Create OAuth 2.0 Client ID -> Desktop app -> Download JSON"
                    )

                flow = InstalledAppFlow.from_client_secrets_file(self.client_secret_file, SCOPES)

                # In a GUI app (pythonw), auth can look "stuck". Always use the loopback
                # server flow (NOT the deprecated OOB redirect), and add a timeout when supported.
                self._progress("YouTube auth: opening browser...")
                try:
                    creds = flow.run_local_server(port=0, open_browser=True, timeout_seconds=300)
                except TypeError:
                    # Older google-auth-oauthlib doesn't support timeout_seconds.
                    creds = flow.run_local_server(port=0, open_browser=True)
                except TimeoutError:
                    raise TimeoutError(
                        "YouTube authentication timed out. Complete auth in the browser and retry."
                    )
                except Exception as e:
                    msg = str(e)
                    if "access blocked" in msg.lower() or "redirect_uri_mismatch" in msg.lower() or "invalid_request" in msg.lower():
                        raise RuntimeError(
                            "YouTube OAuth failed (access blocked / invalid_request).\n\n"
                            "Fix in Google Cloud Console:\n"
                            "1. APIs & Services > OAuth consent screen:\n"
                            "   - Set User Type = External, add your email as a Test user\n"
                            "2. APIs & Services > Credentials:\n"
                            "   - Create OAuth 2.0 Client ID > Desktop application\n"
                            "   - Download JSON and save as client_secret.json in the project root\n"
                            "3. APIs & Services > Library:\n"
                            "   - Enable 'YouTube Data API v3'\n\n"
                            "Then delete youtube_token.json and retry."
                        )
                    raise

            with open(self.token_file, "w", encoding="utf-8") as f:
                f.write(creds.to_json())

        self.service = build("youtube", "v3", credentials=creds, cache_discovery=False)
        return self.service

    def _track_quota(self, cost):
        global _quota_used
        _quota_used += cost

    def upload(self, video_path, title, description="", tags=None, category_id="22"):
        from googleapiclient.http import MediaFileUpload

        if self.service is None:
            self._get_authenticated_service()

        # YouTube title limit is 100 chars, tags total 500 chars
        safe_title = title.strip()[:100]
        safe_tags = (tags or ["anime", "shorts", "highlights"])[:30]
        body = {
            "snippet": {
                "title": safe_title,
                "description": description,
                "tags": safe_tags,
                "categoryId": category_id
            },
            "status": {
                "privacyStatus": "public",
                "selfDeclaredMadeForKids": False
            }
        }

        media = MediaFileUpload(video_path, chunksize=-1, resumable=True)

        self._track_quota(_QUOTA_COST["videos.insert"])
        request = self.service.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media
        )

        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                print(f"Upload progress: {int(status.progress() * 100)}%")

        return response

    def set_thumbnail(self, video_id, thumbnail_path):
        """Best-effort thumbnail upload. Returns API response or None."""
        from googleapiclient.http import MediaFileUpload

        if self.service is None:
            self._get_authenticated_service()

        if not video_id or not thumbnail_path or not os.path.exists(thumbnail_path):
            return None

        media = MediaFileUpload(thumbnail_path)
        self._track_quota(_QUOTA_COST["thumbnails.set"])
        request = self.service.thumbnails().set(videoId=video_id, media_body=media)
        return request.execute()

    def find_or_create_playlist(self, title, description="", privacy_status="public"):
        """Return playlistId for a playlist with exact title (create if missing)."""
        if self.service is None:
            self._get_authenticated_service()

        cached = self._playlist_cache.get(title)
        if cached:
            return cached

        page_token = None
        while True:
            self._track_quota(_QUOTA_COST["playlists.list"])
            req = self.service.playlists().list(
                part="snippet",
                mine=True,
                maxResults=50,
                pageToken=page_token,
            )
            resp = req.execute()
            for it in resp.get("items", []) or []:
                sn = it.get("snippet") or {}
                if sn.get("title") == title:
                    pid = it.get("id")
                    self._playlist_cache[title] = pid
                    _save_playlist_cache(self._playlist_cache)
                    return pid
            page_token = resp.get("nextPageToken")
            if not page_token:
                break

        body = {
            "snippet": {"title": title, "description": description or ""},
            "status": {"privacyStatus": privacy_status},
        }
        self._track_quota(_QUOTA_COST["playlists.insert"])
        created = self.service.playlists().insert(part="snippet,status", body=body).execute()
        pid = created.get("id")
        self._playlist_cache[title] = pid
        _save_playlist_cache(self._playlist_cache)
        return pid

    def add_video_to_playlist(self, video_id, playlist_id):
        if self.service is None:
            self._get_authenticated_service()
        if not video_id or not playlist_id:
            return None

        body = {
            "snippet": {
                "playlistId": playlist_id,
                "resourceId": {"kind": "youtube#video", "videoId": video_id},
            }
        }
        self._track_quota(_QUOTA_COST["playlistItems.insert"])
        return self.service.playlistItems().insert(part="snippet", body=body).execute()
