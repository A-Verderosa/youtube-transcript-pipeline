#!/usr/bin/env python3
"""
Cron helper: Query Notion "YouTube notes" DB for today's videos,
fetch YouTube metadata (title, channel, description) via oEmbed,
and output structured JSON for the Hermes agent to process.

The Hermes cron agent will then:
  - Generate a Facebook-style summary for each video
  - Write the summary to the "Résumé IA" property in Notion
"""

import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

# ── Config ──────────────────────────────────────────────────────────────────
NOTION_API_KEY = os.environ.get("NOTION_API_KEY", "")
DATA_SOURCE_ID = "1661d81e-4c39-8154-baab-000bc2d815e9"  # for queries
DATABASE_ID = "1661d81e-4c39-8177-9a60-f0bdeb50d153"      # for page updates
NOTION_VERSION = "2025-09-03"
# ────────────────────────────────────────────────────────────────────────────


def notion_query(payload: dict) -> dict:
    """POST to the Notion data_source query endpoint."""
    url = f"https://api.notion.com/v1/data_sources/{DATA_SOURCE_ID}/query"
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Authorization", f"Bearer {NOTION_API_KEY}")
    req.add_header("Notion-Version", NOTION_VERSION)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        print(f"[ERROR] Notion query: {e.code}", file=sys.stderr)
        return {"error": err_body, "results": []}


def notion_update_page(page_id: str, properties: dict) -> bool:
    """PATCH a Notion page's properties."""
    url = f"https://api.notion.com/v1/pages/{page_id}"
    body = json.dumps({"properties": properties}).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="PATCH")
    req.add_header("Authorization", f"Bearer {NOTION_API_KEY}")
    req.add_header("Notion-Version", NOTION_VERSION)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as resp:
            return True
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        print(f"[ERROR] Notion update failed for {page_id}: {e.code}", file=sys.stderr)
        return False


def notion_create_child_page(parent_id: str, title: str) -> str | None:
    """Create a child page under a parent page. Returns child page ID or None."""
    url = "https://api.notion.com/v1/pages"
    payload = {
        "parent": {"page_id": parent_id, "type": "page_id"},
        "properties": {
            "title": {
                "title": [{"text": {"content": title}}]
            }
        }
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Authorization", f"Bearer {NOTION_API_KEY}")
    req.add_header("Notion-Version", NOTION_VERSION)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("id")
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        print(f"[ERROR] Notion create child page failed: {e.code} {err_body[:200]}", file=sys.stderr)
        return None


def notion_insert_body(page_id: str, markdown: str) -> bool:
    """Insert markdown content into the body of a Notion page (append to end)."""
    url = f"https://api.notion.com/v1/pages/{page_id}/markdown"
    payload = {
        "type": "insert_content",
        "insert_content": {
            "content": markdown
        }
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="PATCH")
    req.add_header("Authorization", f"Bearer {NOTION_API_KEY}")
    req.add_header("Notion-Version", NOTION_VERSION)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as resp:
            return True
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        print(f"[ERROR] Notion insert body failed for {page_id}: {e.code} {err_body[:200]}", file=sys.stderr)
        return False


def fetch_youtube_transcript(video_id: str) -> tuple[str | None, str | None]:
    """Download YouTube subtitles via yt-dlp with cookies + Node.js POT.
    Returns (transcript_text, language) or (None, error)."""
    import json
    import re
    import html
    import subprocess
    import os
    import urllib.request
    import http.cookiejar as _cj

    COOKIES_FILE = globals().get("COOKIES_FILE", os.path.expanduser(
        "/data/skills/media/youtube-session/references/cookies.txt"))
    NODE_PATH = globals().get("NODE_PATH", "/usr/local/bin/node")

    # Use a temporary copy to avoid yt-dlp overwriting the source file
    TEMP_COOKIES = f"/tmp/yt_cookies_{video_id}_{os.getpid()}.txt"
    try:
        import shutil
        shutil.copy2(COOKIES_FILE, TEMP_COOKIES)
    except Exception:
        TEMP_COOKIES = COOKIES_FILE  # fallback

    def _run_ytdlp(extra_args: list[str], timeout: int = 90) -> dict | None:
        cmd = [
            "python3", "-m", "yt_dlp",
            "--dump-json", "--skip-download",
            "--no-warnings",
        ] + extra_args + [f"https://www.youtube.com/watch?v={video_id}"]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if res.returncode != 0:
            return None
        try:
            return json.loads(res.stdout)
        except json.JSONDecodeError:
            return None

    def _cleanup():
        if TEMP_COOKIES != COOKIES_FILE and os.path.exists(TEMP_COOKIES):
            try:
                os.remove(TEMP_COOKIES)
            except Exception:
                pass

    def _extract_autocaptions(data: dict) -> tuple[str | None, str | None]:
        """From yt-dlp JSON output, extract (caption_text, language)."""
        subs_data = data.get('automatic_captions', {})
        if not subs_data:
            return (None, "No automatic captions available")

        for lang in ('en', 'fr'):
            if lang in subs_data:
                chosen_lang = lang
                break
        else:
            chosen_lang = list(subs_data.keys())[0]

        captions = subs_data[chosen_lang]
        sub_url = None
        for cap in captions:
            if cap.get('ext') == 'json3':
                sub_url = cap.get('url')
                break
        if not sub_url:
            for cap in captions:
                if cap.get('ext') in ('vtt', 'srv3'):
                    sub_url = cap.get('url')
                    break
        if not sub_url:
            return (None, "No subtitle URL found")

        req = urllib.request.Request(sub_url)
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw_data = resp.read().decode('utf-8')

        if 'json3' in sub_url:
            data_parsed = json.loads(raw_data)
            segments = []
            for event in data_parsed.get('events', []):
                for seg in event.get('segs', []):
                    text_seg = seg.get('utf8', '')
                    if text_seg and text_seg != '\n':
                        segments.append(text_seg.strip())
            return (' '.join(segments), chosen_lang)
        else:
            # VTT format
            lines = []
            for line in raw_data.split('\n'):
                if line and not line.startswith('WEBVTT') and '-->' not in line and not line.startswith('NOTE'):
                    cleaned = html.unescape(re.sub(r'<[^>]+>', '', line)).strip()
                    if cleaned:
                        lines.append(cleaned)
            return (' '.join(lines), chosen_lang)

    # ---- Strategy 1: Android client (no cookies, no POT) ----
    # Works for videos that don't require authentication
    try:
        data = _run_ytdlp([
            "--extractor-args", "youtube:player_client=android",
        ], timeout=45)
        if data:
            result = _extract_autocaptions(data)
            if result[0]:
                return result
        # Fall through if android fails
    except Exception:
        pass

    # ---- Strategy 2: Cookies + Node.js POT ----
    try:
        _jar = _cj.MozillaCookieJar(COOKIES_FILE)
        try:
            _jar.load()
            _has_login = any(c.name == 'LOGIN_INFO' for c in _jar)
        except Exception:
            _has_login = False

        if _has_login:
            data = _run_ytdlp([
                "--cookies", TEMP_COOKIES,
                "--js-runtimes", f"node:{NODE_PATH}",
            ], timeout=90)
            if data:
                result = _extract_autocaptions(data)
                if result[0]:
                    return result
        else:
            # Still try, but with a clear error if fails
            pass  # user was warned about missing LOGIN_INFO
    except subprocess.TimeoutExpired:
        _cleanup()
        pass
    except Exception:
        _cleanup()
        pass

    _cleanup()

    # Detect missing yt-dlp for a clearer error
    try:
        subprocess.run(["python3", "-m", "yt_dlp", "--version"],
                       capture_output=True, timeout=5, check=True)
    except (subprocess.SubprocessError, FileNotFoundError):
        return (None, "yt-dlp is not installed. Run: pip install yt-dlp")

    return (None, "Authentication required — YouTube returned LOGIN_REQUIRED. Try re-exporting fresh cookies.")


def extract_video_id(url: str) -> str:
    """Extract 11-char YouTube video ID."""
    patterns = [
        r'(?:v=|youtu\.be/|shorts/|embed/|live/|v/)([a-zA-Z0-9_-]{11})',
        r'^([a-zA-Z0-9_-]{11})$',
    ]
    for pat in patterns:
        m = re.search(pat, url)
        if m:
            return m.group(1)
    return ""


def fetch_oembed(video_id: str) -> dict:
    """Get video metadata via YouTube oEmbed (no auth needed)."""
    url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"error": str(e)}


def get_today_filter():
    """Return a created_time filter for today in UTC."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return {
        "property": "Date de création",
        "created_time": {
            "on_or_after": f"{today}T00:00:00.000Z",
            "on_or_before": f"{today}T23:59:59.999Z",
        }
    }


def main():
    import argparse
    global COOKIES_FILE, NODE_PATH
    
    parser = argparse.ArgumentParser(description="YouTube → Notion Facebook posts pipeline")
    parser.add_argument("--write-summary", nargs=3, metavar=("PAGE_ID", "SUMMARY", "TITLE"),
                        help="Write a summary back to Notion: page_id summary_text video_title")
    parser.add_argument("--write-body", nargs=5, metavar=("PAGE_ID", "TITLE", "CHANNEL", "URL", "THUMBNAIL"),
                        help="Write video metadata into page body: page_id title channel url thumbnail")
    parser.add_argument("--write-body-file", nargs=2, metavar=("PAGE_ID", "FILE"),
                        help="Write markdown from a file into page body")
    parser.add_argument("--fetch-transcript", metavar="VIDEO_ID",
                        help="Download transcript for a video ID and print it as JSON")
    parser.add_argument("--create-transcript-child", nargs=4, metavar=("PAGE_ID", "TRANSCRIPT", "LANGUAGE", "TITLE"),
                        help="Create a child page with transcript: parent_page_id transcript_text language video_title")
    parser.add_argument("--max-videos", type=int, default=5,
                        help="Max videos to process per run (default: 5)")
    parser.add_argument("--cookies", default="./cookies.txt",
                        help="Path to Netscape-format cookies file (default: ./cookies.txt)")
    parser.add_argument("--node-path", default="node",
                        help="Path to Node.js binary (default: node, uses PATH)")
    args = parser.parse_args()

    # Override global paths
    COOKIES_FILE = os.path.expanduser(args.cookies)
    NODE_PATH = args.node_path

    # ── Fetch transcript mode ──────────────────────────────────────────
    if args.fetch_transcript:
        text, lang_or_error = fetch_youtube_transcript(args.fetch_transcript)
        if text:
            print(json.dumps({"success": True, "video_id": args.fetch_transcript, "language": lang_or_error, "text": text[:50000], "length": len(text)}))
        else:
            print(json.dumps({"success": False, "video_id": args.fetch_transcript, "error": lang_or_error}))
        return

    # ── Create transcript child page ──────────────────────────────────
    if args.create_transcript_child:
        parent_id, transcript, lang, video_title = args.create_transcript_child
        child_title = f"📝 Transcription ({lang})"
        
        child_id = notion_create_child_page(parent_id, child_title)
        if not child_id:
            print(json.dumps({"success": False, "error": "Failed to create child page"}))
            return
        
        # Write transcript into child page body
        ok = notion_insert_body(child_id, transcript)
        if ok:
            print(json.dumps({
                "success": True,
                "parent_id": parent_id,
                "child_id": child_id,
                "child_title": child_title,
                "transcript_length": len(transcript),
                "language": lang,
            }))
        else:
            print(json.dumps({"success": False, "parent_id": parent_id, "error": "Failed to write transcript body"}))
        return

    # ── Write body mode (from file - recommended) ──────────────────────
    if args.write_body_file:
        page_id, file_path = args.write_body_file
        with open(file_path, "r", encoding="utf-8") as f:
            markdown_body = f.read()
        ok = notion_insert_body(page_id, markdown_body)
        if ok:
            print(json.dumps({"success": True, "page_id": page_id}))
        else:
            print(json.dumps({"success": False, "page_id": page_id}))
        # Clean up temp file
        try:
            os.remove(file_path)
        except OSError:
            pass
        return

    # ── Write body mode (direct, generates markdown internally) ────────
    if args.write_body:
        page_id, title, channel, url, thumbnail = args.write_body
        # Build proper markdown (no shell escaping issues)
        md = f"""## 🎬 {title}

📺 **Chaîne :** {channel}

🔗 **Lien :** {url}

🖼️ ![Miniature]({thumbnail})

---

*⏳ Transcription vidéo non disponible pour le moment (blocage IP cloud — les cookies YouTube doivent être réexportés depuis un navigateur pour débloquer).*
"""
        ok = notion_insert_body(page_id, md)
        if ok:
            print(f"[OK] Written body content for: {title[:60]}", file=sys.stderr)
            print(json.dumps({"success": True, "page_id": page_id, "title": title}))
        else:
            print(json.dumps({"success": False, "page_id": page_id, "title": title}))
        return

    # ── Write summary mode ──────────────────────────────────────────────
    if args.write_summary:
        page_id, summary, video_title = args.write_summary
        # Escape the summary for shell safety
        props = {
            "Résumé IA": {
                "rich_text": [{"text": {"content": summary}}]
            }
        }
        ok = notion_update_page(page_id, props)
        if ok:
            print(f"[OK] Written summary for: {video_title[:60]}", file=sys.stderr)
            print(json.dumps({"success": True, "page_id": page_id, "title": video_title}))
        else:
            print(json.dumps({"success": False, "page_id": page_id, "title": video_title}))
        return

    # ── Collect mode ────────────────────────────────────────────────────
    print("[INFO] Querying Notion for today's videos...", file=sys.stderr)
    payload = {
        "filter": get_today_filter(),
        "sorts": [{"property": "Date de création", "direction": "descending"}],
        "page_size": 50,
    }
    result = notion_query(payload)
    if "error" in result:
        print(json.dumps({"error": result["error"], "videos": []}))
        sys.exit(1)

    pages = result.get("results", [])
    print(f"[INFO] Found {len(pages)} pages created today", file=sys.stderr)

    videos = []
    for page in pages:
        pid = page["id"]
        props = page.get("properties", {})

        # Skip if already has a summary
        resume_ia = props.get("Résumé IA", {}).get("rich_text", [])
        if resume_ia and resume_ia[0].get("text", {}).get("content", "").strip():
            print(f"[SKIP] {pid[:8]}... already has Résumé IA", file=sys.stderr)
            continue

        # Get URL
        url_source = props.get("URL source", {}).get("url", "")
        if not url_source:
            print(f"[SKIP] {pid[:8]}... no URL source", file=sys.stderr)
            continue

        # Get Notion title
        notion_title = ""
        title_field = props.get("Titre", {}).get("title", [])
        if title_field:
            notion_title = title_field[0].get("text", {}).get("content", "")

        # Get channel from Notion if already set
        channel = ""
        channel_field = props.get("Canal source", {}).get("rich_text", [])
        if channel_field:
            channel = channel_field[0].get("text", {}).get("content", "")

        # Extract video ID
        video_id = extract_video_id(url_source)
        if not video_id:
            print(f"[SKIP] {pid[:8]}... could not extract video ID from {url_source}", file=sys.stderr)
            continue

        # Fetch metadata
        meta = fetch_oembed(video_id)
        youtube_title = meta.get("title", notion_title)
        youtube_channel = meta.get("author_name", channel)
        thumbnail = meta.get("thumbnail_url", "")

        print(f"[INFO] #{len(videos)+1}: {youtube_title[:60]}... ({youtube_channel})", file=sys.stderr)

        videos.append({
            "page_id": pid,
            "notion_title": notion_title,
            "youtube_title": youtube_title,
            "channel": youtube_channel,
            "url": url_source,
            "video_id": video_id,
            "thumbnail": thumbnail,
            "status": "needs_summary",
        })

    # Limit to max_videos
    videos = videos[:args.max_videos]

    output = {
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "database": "YouTube notes",
        "total_found": len(pages),
        "to_process": len(videos),
        "videos": videos,
    }

    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
