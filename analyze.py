"""
Step 2: Comments ka sentiment analysis + charts.
Usage:
    python analyze.py --input data/comments.csv --model vader
    python analyze.py --input data/comments.csv --model xlmr     # transformers chahiye
"""
import argparse
import os
import re

import matplotlib.pyplot as plt
import pandas as pd
from wordcloud import WordCloud


def clean(text):
    text = re.sub(r"http\S+|www\.\S+", " ", str(text))
    text = re.sub(r"@\w+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def vader_predict(texts):
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    sia = SentimentIntensityAnalyzer()
    labels, scores = [], []
    for t in texts:
        c = sia.polarity_scores(t)["compound"]
        scores.append(c)
        labels.append("Positive" if c >= 0.05 else "Negative" if c <= -0.05 else "Neutral")
    return labels, scores


def xlmr_predict(texts):
    from transformers import pipeline
    clf = pipeline(
        "sentiment-analysis",
        model="cardiffnlp/twitter-xlm-roberta-base-sentiment",
        truncation=True, max_length=128,
    )
    labels, scores = [], []
    for i in range(0, len(texts), 32):
        for r in clf(texts[i:i + 32]):
            labels.append(r["label"].capitalize())
            scores.append(r["score"])
    return labels, scores


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", default="data/comments.csv")
    p.add_argument("--model", choices=["vader", "xlmr"], default="vader")
    p.add_argument("--outdir", default="output")
    a = p.parse_args()

    os.makedirs(a.outdir, exist_ok=True)
    df = pd.read_csv(a.input)
    df["clean"] = df["comment"].map(clean)
    df = df[df["clean"].str.len() > 2].reset_index(drop=True)

    predict = vader_predict if a.model == "vader" else xlmr_predict
    df["sentiment"], df["score"] = predict(df["clean"].tolist())
    df.to_csv(f"{a.outdir}/results.csv", index=False, encoding="utf-8-sig")

    counts = df["sentiment"].value_counts()
    print(counts, "\n")
    print((counts / len(df) * 100).round(1).astype(str) + "%")

    colors = {"Positive": "#2e9e5b", "Neutral": "#9aa0a6", "Negative": "#d64545"}

    # 1) Distribution
    ax = counts.plot(kind="bar", color=[colors.get(k, "#555") for k in counts.index])
    ax.set_title("Sentiment Distribution"); ax.set_ylabel("Comments")
    plt.xticks(rotation=0); plt.tight_layout()
    plt.savefig(f"{a.outdir}/distribution.png", dpi=150); plt.close()

    # 2) Per-video breakdown
    pv = pd.crosstab(df["video_title"].str[:30], df["sentiment"], normalize="index") * 100
    pv.plot(kind="barh", stacked=True, color=[colors.get(c, "#555") for c in pv.columns])
    plt.title("Sentiment per Video (%)"); plt.tight_layout()
    plt.savefig(f"{a.outdir}/per_video.png", dpi=150); plt.close()

    # 3) Word clouds
    for label in ["Positive", "Negative"]:
        text = " ".join(df.loc[df["sentiment"] == label, "clean"])
        if len(text) > 20:
            wc = WordCloud(width=900, height=450, background_color="white").generate(text)
            wc.to_file(f"{a.outdir}/wordcloud_{label.lower()}.png")

    print(f"\nSaved results + charts in '{a.outdir}/'")


if __name__ == "__main__":
    main()
