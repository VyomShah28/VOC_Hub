import json
import numpy as np
from datetime import date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import select, delete
from bertopic import BERTopic
from hdbscan import HDBSCAN
from sklearn.feature_extraction.text import CountVectorizer
from app.db.database import SessionLocal
from app.db.models import FeedbackProcessed, FeedbackRaw, Theme, ThemeItem, ThemeWeeklyCount, Opportunity
from app.core.config import settings
from app.services.scoring_service import run_scoring_pipeline
from app.services.bedrock_client import generate_text_with_bedrock

INTENT_BUCKETS = [
    "bug_report",
    "feature_request",
    "usability_complaint",
    "pricing_commercial",
    "process_complaint",
    "competitive_mention",
    "praise"
]

MIN_BUCKET_SIZE = 5


def _get_processed_feedback(db: Session) -> list[dict]:
    """
    Pull all processed feedback with embeddings and metadata from DB.
    Returns list of dicts with everything needed for clustering.
    """
    results = db.execute(
        select(
            FeedbackProcessed.feedback_id,
            FeedbackProcessed.clean_text,
            FeedbackProcessed.intents,
            FeedbackProcessed.embedding,
            FeedbackProcessed.arr,
            FeedbackProcessed.sentiment_score,
            FeedbackProcessed.urgency_keyword_score,
            FeedbackRaw.date,
            FeedbackRaw.segment
        ).join(FeedbackRaw, FeedbackProcessed.feedback_id == FeedbackRaw.id)
    ).all()

    records = []
    for row in results:
        if row.embedding is None:
            continue
        records.append({
            "feedback_id": row.feedback_id,
            "clean_text": row.clean_text,
            "intents": row.intents or [],
            "embedding": row.embedding,
            "arr": row.arr or 0.0,
            "sentiment_score": row.sentiment_score or 0.0,
            "urgency_keyword_score": row.urgency_keyword_score or 0.0,
            "date": row.date,
            "segment": row.segment
        })

    print(f"[CLUSTERING] Pulled {len(records)} processed feedback records from DB.")
    return records


def _generate_theme_name(keywords: list[str], sample_texts: list[str], intent_bucket: str) -> dict:
    """
    Ask LLM to generate a clean theme name and short description
    from BERTopic keywords + sample feedback texts.
    """
    prompt = f"""
    You are analyzing customer feedback clusters for a B2B SaaS platform.
    
    Intent bucket: {intent_bucket}
    Top keywords from this cluster: {', '.join(keywords)}
    
    Sample feedback items from this cluster:
    {chr(10).join(f'- {t}' for t in sample_texts[:3])}
    
    Generate a JSON object with:
    1. "name": A concise, human-readable theme name (max 6 words). 
       Example: "SSO Authentication Failures" or "Mobile App Performance Issues"
    2. "description": One sentence describing what customers in this cluster are experiencing.
    
    Output ONLY the JSON object, nothing else.
    """

    response_text = generate_text_with_bedrock("", prompt, is_json=True)
    result = json.loads(response_text)
    return {
        "name": result.get("name", f"{intent_bucket} cluster"),
        "description": result.get("description", "")
    }


def _write_weekly_counts(theme_id: int, items: list[dict], db: Session):
    """
    Given all feedback items in a theme, bucket them by ISO week
    and write one ThemeWeeklyCount row per week.
    week_start is always the Monday of that ISO week.
    Skips items with no date — they contribute no trend signal.
    """
    week_counts: dict[date, int] = {}

    for item in items:
        item_date = item.get("date")
        if not item_date:
            continue
        # Roll back to Monday of that week
        monday = item_date - timedelta(days=item_date.weekday())
        week_counts[monday] = week_counts.get(monday, 0) + 1

    for week_start, count in week_counts.items():
        db.add(ThemeWeeklyCount(
            theme_id=theme_id,
            week_start=week_start,
            count=count
        ))


def _cluster_bucket(bucket_name: str, items: list[dict], db: Session):
    """
    Run BERTopic + HDBSCAN on one intent bucket.
    Inserts Theme, ThemeItem, and ThemeWeeklyCount records for all clusters
    including outliers. HDBSCAN is instantiated fresh per call to avoid
    stale fitted state across runs.
    """
    print(f"[CLUSTERING] Processing bucket: {bucket_name} ({len(items)} items)")

    documents  = [item["clean_text"] for item in items]
    embeddings = np.array([item["embedding"] for item in items])
    vectorizer = CountVectorizer(stop_words="english", min_df=1, ngram_range=(1, 2))

    n = len(items)

    # UMAP requires n_neighbors < N (number of data points).
    # Default is 15 — safe for large datasets but crashes on small buckets.
    # We also switch init to 'random' when N is very small because spectral
    # initialization needs to solve an eigenproblem that requires N > n_components.
    umap_n_neighbors = min(n - 1, 15)
    umap_init        = "random" if n < 20 else "spectral"

    from umap import UMAP
    umap_model = UMAP(
        n_neighbors=umap_n_neighbors,
        n_components=min(5, n - 1),   # n_components must also be < N
        min_dist=0.0,
        metric="cosine",
        init=umap_init,
        random_state=42,
    )

    # Instantiate fresh per run — never reuse a fitted HDBSCAN instance
    hdbscan_model = HDBSCAN(
        min_cluster_size=min(3, max(2, n // 4)),  # scale with bucket size
        min_samples=1,
        metric="euclidean",
        cluster_selection_method="eom",
        prediction_data=True,
    )

    topic_model = BERTopic(
        umap_model=umap_model,
        hdbscan_model=hdbscan_model,
        vectorizer_model=vectorizer,
        calculate_probabilities=False,
        verbose=False,
    )

    topics, _ = topic_model.fit_transform(documents, embeddings)
    topic_groups: dict[int, list[dict]] = {}
    for idx, topic_id in enumerate(topics):
        topic_groups.setdefault(topic_id, []).append(items[idx])

    print(f"[CLUSTERING] Found {len(topic_groups)} clusters (including outliers) in {bucket_name}")

    for topic_id, group_items in topic_groups.items():
        is_outlier = topic_id == -1

        if not is_outlier:
            try:
                topic_info = topic_model.get_topic(topic_id)
                keywords = [word for word, _ in topic_info[:8]] if topic_info else []
            except Exception:
                keywords = []

            sample_texts = [item["clean_text"] for item in group_items[:3]]

            try:
                naming = _generate_theme_name(keywords, sample_texts, bucket_name)
                theme_name = naming["name"]
                theme_description = naming["description"]
            except Exception as e:
                print(f"[CLUSTERING] LLM naming failed for topic {topic_id}: {e}")
                theme_name = f"{bucket_name.replace('_', ' ').title()} Theme {topic_id}"
                theme_description = ""
        else:
            keywords = []
            theme_description = "Individual feedback item not grouped into any cluster."

        dates = [item["date"] for item in group_items if item["date"]]
        first_seen = min(dates) if dates else date.today()
        last_seen = max(dates) if dates else date.today()

        if is_outlier:
            # Each outlier becomes its own single-item theme
            for single_item in group_items:
                single_date = single_item["date"] or date.today()
                words = single_item["clean_text"].split()[:8]
                outlier_name = " ".join(words) + ("..." if len(words) >= 8 else "")

                theme = Theme(
                    intent_bucket=bucket_name,
                    name=outlier_name,
                    keywords=[],
                    description=theme_description,
                    first_seen=single_date,
                    last_seen=single_date,
                    item_count=1,
                    is_outlier=True
                )
                db.add(theme)
                db.flush()

                db.add(ThemeItem(
                    theme_id=theme.id,
                    feedback_id=single_item["feedback_id"]
                ))

                # Outliers still contribute to weekly counts for trend tracking
                _write_weekly_counts(theme.id, [single_item], db)

        else:
            theme = Theme(
                intent_bucket=bucket_name,
                name=theme_name,
                keywords=keywords,
                description=theme_description,
                first_seen=first_seen,
                last_seen=last_seen,
                item_count=len(group_items),
                is_outlier=False
            )
            db.add(theme)
            db.flush()

            for item in group_items:
                db.add(ThemeItem(
                    theme_id=theme.id,
                    feedback_id=item["feedback_id"]
                ))

            # Write weekly frequency buckets for velocity computation
            _write_weekly_counts(theme.id, group_items, db)

    print(f"[CLUSTERING] Bucket {bucket_name} done — themes and weekly counts inserted.")


def run_clustering_pipeline():
    """
    Main entry point. Called after every daily Excel upload completes.

    Strategy: full re-cluster from scratch every time.
    - Wipe existing themes, theme_items, and theme_weekly_counts
    - Pull all processed feedback embeddings
    - Cluster per intent bucket separately
    - Reinsert fresh themes + weekly counts
    """
    db = SessionLocal()
    try:
        print("[CLUSTERING] Starting full re-cluster...")

        # Order matters: ThemeWeeklyCount and ThemeItem reference Theme via FK
        db.execute(delete(ThemeWeeklyCount))
        db.execute(delete(ThemeItem))
        db.execute(delete(Opportunity))
        db.execute(delete(Theme))
        db.commit()
        print("[CLUSTERING] Cleared existing themes, theme_items, and theme_weekly_counts.")

        all_records = _get_processed_feedback(db)
        if not all_records:
            print("[CLUSTERING] No processed feedback found. Aborting.")
            return

        for bucket in INTENT_BUCKETS:
            bucket_items = [
                r for r in all_records
                if bucket in r["intents"]
            ]

            if len(bucket_items) < MIN_BUCKET_SIZE:
                print(f"[CLUSTERING] Skipping {bucket} — only {len(bucket_items)} items (min {MIN_BUCKET_SIZE})")
                continue

            _cluster_bucket(bucket, bucket_items, db)
            db.commit()

        print("[CLUSTERING] Full re-cluster complete.")

        print("[CLUSTERING] Handing off to scoring pipeline...")
        run_scoring_pipeline()

    except Exception as e:
        db.rollback()
        print(f"[CLUSTERING] Fatal error: {str(e)}")
        raise
    finally:
        db.close()