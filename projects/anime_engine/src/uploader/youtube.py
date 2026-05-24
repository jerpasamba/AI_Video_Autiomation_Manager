import os
import pickle
import json


class YouTubeUploader:
    def __init__(self, client_secret_file=None, token_file="youtube_token.json"):
        self.client_secret_file = client_secret_file
        self.token_file = token_file
        self.service = None

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
                creds.refresh(Request())
            else:
                if not self.client_secret_file or not os.path.exists(self.client_secret_file):
                    raise FileNotFoundError(
                        "YouTube API client_secret file not found.\n"
                        "Set it up at: https://console.cloud.google.com/apis/credentials\n"
                        "Create OAuth 2.0 Client ID -> Desktop app -> Download JSON"
                    )

                flow = InstalledAppFlow.from_client_secrets_file(
                    self.client_secret_file, SCOPES
                )
                creds = flow.run_local_server(port=0)

            with open(self.token_file, "w", encoding="utf-8") as f:
                f.write(creds.to_json())

        self.service = build("youtube", "v3", credentials=creds)
        return self.service

    def upload(self, video_path, title, description="", tags=None, category_id="22"):
        from googleapiclient.http import MediaFileUpload

        if self.service is None:
            self._get_authenticated_service()

        body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": tags or ["anime", "shorts", "highlights"],
                "categoryId": category_id
            },
            "status": {
                "privacyStatus": "public",
                "selfDeclaredMadeForKids": False
            }
        }

        media = MediaFileUpload(video_path, chunksize=-1, resumable=True)

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
        request = self.service.thumbnails().set(videoId=video_id, media_body=media)
        return request.execute()

    def find_or_create_playlist(self, title, description="", privacy_status="public"):
        """Return playlistId for a playlist with exact title (create if missing)."""
        if self.service is None:
            self._get_authenticated_service()

        page_token = None
        while True:
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
                    return it.get("id")
            page_token = resp.get("nextPageToken")
            if not page_token:
                break

        body = {
            "snippet": {"title": title, "description": description or ""},
            "status": {"privacyStatus": privacy_status},
        }
        created = self.service.playlists().insert(part="snippet,status", body=body).execute()
        return created.get("id")

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
        return self.service.playlistItems().insert(part="snippet", body=body).execute()
