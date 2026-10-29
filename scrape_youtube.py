"""
Step 1: YouTube se brand ke comments scrape karo.
Usage:
    python scrape_youtube.py --brand "Khaadi" --videos 10 --max-comments 300
"""
import argparse
import os
import time

import pandas as pd
from dotenv import load_dotenv
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

load_dotenv()


def get_youtube():
    key = os.getenv("YOUTUBE_API_KEY")
    if not key:
        raise SystemExit("YOUTUBE_API_KEY .env file me nahi mili.")
    return build("youtube", "v3", developerKey=key)


def search_videos(yt, query, n):
    """Brand se related videos dhoondo."""
    video_ids, token = [], None
    while len(video_ids) < n:
        res = yt.search().list(
            q=query, part="id,snippet", type="video",
            maxResults=min(50, n - len(video_ids)), pageToken=token,
            order="relevance",
        ).execute()
        for it in res["items"]:
            video_ids.append((it["id"]["videoId"], it["snippet"]["title"]))
        token = res.get("nextPageToken")
        if not token:
            break
    return video_ids[:n]


def get_comments(yt, video_id, title, max_comments):
    rows, token = [], None
    while len(rows) < max_comments:
        try:
            res = yt.commentThreads().list(
                part="snippet", videoId=video_id, maxResults=100,
                pageToken=token, textFormat="plainText", order="relevance",
            ).execute()
        except HttpError as e:
            print(f"  skip {video_id}: {e.reason if hasattr(e, 'reason') else e}")
            break
        for it in res["items"]:
            s = it["snippet"]["topLevelComment"]["snippet"]
            rows.append({
                "video_id": video_id,
                "video_title": title,
                "comment": s["textDisplay"],
                "likes": s["likeCount"],
                "published_at": s["publishedAt"],
            })
        token = res.get("nextPageToken")
        if not token:
            break
        time.sleep(0.2)
    return rows[:max_comments]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--brand", required=True, help="Brand ka naam, e.g. Khaadi")
    p.add_argument("--videos", type=int, default=10)
    p.add_argument("--max-comments", type=int, default=300, help="per video")
    p.add_argument("--out", default="data/comments.csv")
    a = p.parse_args()

    yt = get_youtube()
    videos = search_videos(yt, f"{a.brand} review", a.videos)
    print(f"{len(videos)} videos mile.")

    all_rows = []
    for vid, title in videos:
        print(f"Scraping: {title[:60]}")
        all_rows += get_comments(yt, vid, title, a.max_comments)

    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    df = pd.DataFrame(all_rows).drop_duplicates(subset="comment")
    df.to_csv(a.out, index=False, encoding="utf-8-sig")
    print(f"Done: {len(df)} comments -> {a.out}")


if __name__ == "__main__":
    main()
