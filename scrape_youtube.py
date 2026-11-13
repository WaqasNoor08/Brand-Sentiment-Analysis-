"""
Step 1 (updated): sirf KHAADI CLOTHING videos ke comments scrape karo.

Pehle wali script "Khaadi review" search karti thi, is liye perfume, "Khadi" herbal/stationery
aur IPO videos bhi aa jati thin. Ab:
  1. Kai clothing-specific queries search hoti hain (sale, lawn, Eid collection, haul, try-on ...)
  2. Har video ka title filter hota hai: "khaadi" + clothing word hona chahiye,
     aur perfume / hair / soap / IPO jaisi cheezein reject hoti hain
  3. Video stats (views, video likes, publish date, URL) bhi save hote hain
     -> Project 3 mein views aur days_since_post ban sakte hain
  4. Duplicate sirf (video_id, comment) par hata'te hain, taake "Nice video" har video mein rahe

Usage (Colab ya local):
    import os; os.environ["YOUTUBE_API_KEY"] = "YOUR_KEY"      # Colab mein
    python scrape_youtube.py --max-comments 500 --out data/comments_clothing.csv
    python scrape_youtube.py --dry-run                 # sirf quota ka andaaza

Quota (10,000 units/day): search.list = 100 units, videos.list = 1, commentThreads.list = 1.
Default 12 queries x 2 pages = 2,400 units for search; comments sasti hain.
Phir analyze.py chalao (VADER) taake sentiment + score columns ban jayein.
"""
import argparse
import html
import os
import re
import time
from datetime import date

import pandas as pd
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

QUERIES = [
    "Khaadi sale", "Khaadi new collection 2026", "Khaadi lawn collection", "Khaadi Eid collection",
    "Khaadi pret collection", "Khaadi winter collection", "Khaadi haul", "Khaadi try on",
    "Khaadi unboxing", "Khaadi shopping vlog", "Khaadi 3 piece suit", "Khaadi flat 50% off",
]
# title mein ye aana chahiye (brand) ...
BRAND = re.compile(r"khaadi|khaddi", re.I)
# ... aur clothing ka koi lafz
CLOTHING = re.compile(r"collection|pret|lawn|suit|dress|kurta|shalwar|kameez|3 ?pc|3 ?piece|2 ?piece|cut piece|"
                      r"sale|off|discount|haul|try.?on|unbox|eid|summer|winter|fabric|clothes|outfit|ready to wear|"
                      r"khaas|casual|signature|stitched|unstitched|trouser|dupatta|abaya|kids wear", re.I)
# in mein se kuch bhi ho to reject
BLOCK = re.compile(r"perfume|fragrance|attar|deo|body spray|shampoo|soap|hair|oil|henna|mehndi|herbal|ayurved|sketch|"
                   r"paper|saree|sari|meesho|\bipo\b|shares?\b|stock|psx|invest|go public|financials|valuation", re.I)


def get_youtube():
    key = os.getenv("YOUTUBE_API_KEY")
    if not key:
        raise SystemExit("YOUTUBE_API_KEY set nahi hai (os.environ ya .env mein daalo).")
    return build("youtube", "v3", developerKey=key)


def is_khaadi_clothing(title: str) -> bool:
    t = html.unescape(title)
    return bool(BRAND.search(t) and CLOTHING.search(t) and not BLOCK.search(t))


def search_videos(yt, queries, pages, order):
    """Har query ke 'pages' pages (50 videos each). Returns {video_id: title}."""
    found = {}
    for q in queries:
        token = None
        for _ in range(pages):
            try:
                res = yt.search().list(q=q, part="id,snippet", type="video", maxResults=50, pageToken=token,
                                       order=order, regionCode="PK").execute()
            except HttpError as e:
                print(f"  search skip '{q}': {e}")
                break
            for it in res.get("items", []):
                found[it["id"]["videoId"]] = html.unescape(it["snippet"]["title"])
            token = res.get("nextPageToken")
            if not token:
                break
        print(f"  '{q}': total candidates so far {len(found)}")
    return found


def video_stats(yt, ids):
    """views, likes, comment count, publish date (1 unit per 50 videos)."""
    out = {}
    ids = list(ids)
    for i in range(0, len(ids), 50):
        res = yt.videos().list(part="statistics,snippet", id=",".join(ids[i:i + 50])).execute()
        for it in res.get("items", []):
            st = it.get("statistics", {})
            out[it["id"]] = dict(
                views=int(st.get("viewCount", 0)), video_likes=int(st.get("likeCount", 0)),
                video_comment_count=int(st.get("commentCount", 0)),
                video_published_at=it["snippet"]["publishedAt"], channel=it["snippet"]["channelTitle"])
    return out


def get_comments(yt, video_id, title, max_comments):
    rows, token = [], None
    while len(rows) < max_comments:
        try:
            res = yt.commentThreads().list(part="snippet", videoId=video_id, maxResults=100, pageToken=token,
                                           textFormat="plainText", order="relevance").execute()
        except HttpError as e:
            print(f"  skip {video_id}: {getattr(e, 'reason', e)}")   # comments band hon to skip
            break
        for it in res["items"]:
            s = it["snippet"]["topLevelComment"]["snippet"]
            rows.append({"video_id": video_id, "video_title": title, "comment": s["textDisplay"],
                         "likes": s["likeCount"], "published_at": s["publishedAt"]})
        token = res.get("nextPageToken")
        if not token:
            break
        time.sleep(0.2)
    return rows[:max_comments]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--pages", type=int, default=2, help="search pages per query (50 videos each)")
    p.add_argument("--max-comments", type=int, default=500, help="per video")
    p.add_argument("--min-video-comments", type=int, default=5, help="is se kam comments wali video skip")
    p.add_argument("--order", default="relevance", choices=["relevance", "viewCount", "date"],
                   help="viewCount = bari videos = zyada comments")
    p.add_argument("--out", default="data/comments_clothing.csv")
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()

    search_units = len(QUERIES) * a.pages * 100
    print(f"Search quota: about {search_units} units (daily limit 10,000)")
    if a.dry_run:
        return

    yt = get_youtube()
    cand = search_videos(yt, QUERIES, a.pages, a.order)
    keep = {v: t for v, t in cand.items() if is_khaadi_clothing(t)}
    print(f"{len(cand)} candidates -> {len(keep)} Khaadi clothing videos after title filter")
    stats = video_stats(yt, keep)
    keep = {v: t for v, t in keep.items() if stats.get(v, {}).get("video_comment_count", 0) >= a.min_video_comments}
    print(f"{len(keep)} videos have at least {a.min_video_comments} comments")

    rows = []
    for i, (vid, title) in enumerate(keep.items(), 1):
        print(f"[{i}/{len(keep)}] {title[:60]}")
        rows += get_comments(yt, vid, title, a.max_comments)

    df = pd.DataFrame(rows).drop_duplicates(subset=["video_id", "comment"])
    meta = pd.DataFrame.from_dict(stats, orient="index").reset_index(names="video_id")
    df = df.merge(meta, on="video_id", how="left")
    df["video_url"] = "https://www.youtube.com/watch?v=" + df["video_id"]
    df["collection_date"] = date.today().isoformat()
    df["platform"] = "YouTube"
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    df.to_csv(a.out, index=False, encoding="utf-8-sig")
    print(f"Done: {len(df)} comments, {df['video_id'].nunique()} videos -> {a.out}")
    if len(df) < 2000:
        print("Note: 2,000 se kam. Try: --order viewCount, --pages 3, ya QUERIES mein aur clothing queries add karo.")


if __name__ == "__main__":
    main()
