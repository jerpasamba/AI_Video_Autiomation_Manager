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

        SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

        creds = None

        if os.path.exists(self.token_file):
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

            with open(self.token_file, "w") as f:
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
