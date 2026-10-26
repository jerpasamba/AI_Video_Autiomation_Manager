# AI Video Manager

A PyQt6 desktop application for automated video generation and social media upload. Orchestrates Manhwa motion comics, anime shorts, and Minecraft story pipelines with a single click.

## Features

- **Auto-Generation Loop** — Start once, it generates videos from all pipelines until you manually stop
- **Auto-Upload to Facebook, YouTube, & TikTok** — Generated videos are automatically queued and published to Facebook Reels, YouTube / YouTube Shorts, and TikTok
- **Live Video Manager & Views Checker** — Verify if uploaded videos are really live on social platforms; fetch real-time view counts (👁️), likes (❤️), and comments (💬) with one click
- **Live Monitoring** — Dashboard shows real-time success/failure counters, activity feed, and queue status
- **Parallel Workers** — Process multiple videos simultaneously (configurable up to 4 workers)
- **Pipeline Integrations** — Works with external Manhwa, Anime Shorts, Minecraft story generators, and Movie Reels

## Quick Start

1. **Install dependencies:**
   ```
   .\venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

2. **Set up credentials** (Facebook, YouTube, and/or TikTok)

3. **Launch the app:**
   ```
   .\venv\Scripts\python.exe main.py
   ```

4. **Dashboard → [ START AUTO-GENERATION ]** to begin

## Facebook Setup (Required for Facebook Reels)

1. Go to https://developers.facebook.com/tools/explorer/
2. Select your App → choose **Page Token** from the dropdown
3. Add permissions: `pages_manage_posts`, `pages_read_engagement`, `pages_show_list`
4. Click **Generate Access Token** and copy the token
5. In the app, go to **Settings** tab → paste token → **Test Connection** → **Save Settings**

## TikTok Setup (New)

You can connect TikTok via either method:
- **Option 1 (Official API Token)**:
  1. Register an app on [TikTok for Developers](https://developers.tiktok.com/).
  2. Request the **Content Posting API** (`video.upload`, `video.publish`).
  3. Paste your User Access Token in **Settings → TikTok Upload**.
- **Option 2 (Session ID Cookie)**:
  1. Log into your TikTok account at [tiktok.com](https://www.tiktok.com).
  2. Open Developer Tools (F12) → Storage/Application → Cookies → `tiktok.com`.
  3. Copy the value of the `sessionid` cookie and paste it in **Settings → TikTok Upload**.
- Click **Test TikTok Connection** to verify your account!

## YouTube Setup (Optional)

1. Go to https://console.cloud.google.com/ → Create a project
2. Enable **YouTube Data API v3**
3. Go to **Credentials** → **Create OAuth client ID** → **Desktop app**
4. Download the JSON → rename to `client_secret.json` → place in project root
5. First upload will open a browser for Google OAuth consent

## Project Structure

```
AI_Video_Manager/
├── main.py                     # Entry point
├── config.json                 # Settings + API tokens
├── app/
│   ├── main_window.py          # Main window + auto-loop logic
│   ├── queue_manager.py        # Task queue with persistence
│   ├── worker_pool.py          # Parallel worker threads
│   └── upload_registry.py      # Duplicate prevention & upload history
├── ui/
│   ├── dashboard_tab.py        # Start/Stop button + Live Monitor
│   ├── manhwa_tab.py           # Manhwa chapter management
│   ├── shorts_tab.py           # Anime + Minecraft generation
│   ├── movie_reels_tab.py      # Movie Reels generation
│   ├── queue_tab.py            # Task queue viewer
│   ├── upload_tab.py           # Multi-platform upload manager
│   ├── upload_history_tab.py   # Upload records table
│   └── settings_tab.py         # Configuration UI
├── upload/
│   ├── facebook_uploader.py    # Facebook Reels upload
│   ├── youtube_uploader.py     # YouTube upload
│   └── tiktok_uploader.py      # TikTok video upload (Official API + Session)
├── monitoring/
│   └── __init__.py             # Monitor class (counters + activity log)
└── projects/
    ├── manhwa_pipeline.py      # External manhwa project integration
    ├── anime_shorts_pipeline.py
    ├── minecraft_pipeline.py
    └── moviereels_pipeline.py
```

## How Auto-Loop Works

1. Click **[ START AUTO-GENERATION ]** on the Dashboard
2. Every 5 minutes, the app checks all pipelines and queues the next pending item
3. Workers (2 by default) pick up tasks in parallel
4. When a video finishes generating, it's automatically queued for Facebook upload
5. Live Monitor updates in real-time with success/failure counts
6. Click **[ STOP ]** to stop queuing new work (current tasks finish)
