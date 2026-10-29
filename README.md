# Brand Sentiment Analysis (YouTube Comments)

## Setup
1. Google Cloud Console -> new project -> enable **YouTube Data API v3** -> Credentials -> **API key**.
2. `cp .env.example .env` aur key paste karo.
3. `pip install -r requirements.txt`

## Run
```
python scrape_youtube.py --brand "Khaadi" --videos 10 --max-comments 300
python analyze.py --input data/comments.csv --model vader
```
Better multilingual accuracy ke liye: `pip install transformers torch` phir `--model xlmr`.

## Output
`output/results.csv`, `distribution.png`, `per_video.png`, `wordcloud_*.png`

## Note
Quota: YouTube API free tier = 10,000 units/day (search = 100 units, comments = 1 unit/page).
