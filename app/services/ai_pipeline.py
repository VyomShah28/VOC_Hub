import json
from sqlalchemy import select
from app.db.database import SessionLocal
from app.db.models import FeedbackRaw, FeedbackProcessed
from app.core.config import settings
from app.services.bedrock_client import generate_text_with_bedrock, generate_embedding_with_bedrock
def run_ai_pipeline(feedback_id: str):
    db = SessionLocal()
    try:
        print(f"[AI PIPELINE] Waking up for {feedback_id}...")

        raw_record = db.execute(
            select(FeedbackRaw).where(FeedbackRaw.id == feedback_id)
        ).scalar_one_or_none()

        if not raw_record or not raw_record.raw_text:
            print(f"[AI PIPELINE] Aborted: No text found for {feedback_id}")
            return

        if raw_record.processed:
            print(f"[AI PIPELINE] {feedback_id} already processed flag set. Skipping.")
            return
        
        existing = db.execute(
            select(FeedbackProcessed).where(FeedbackProcessed.feedback_id == feedback_id)
        ).scalar_one_or_none()
        if existing:
            print(f"[AI PIPELINE] {feedback_id} already exists in feedback_processed. Skipping.")
            return

        system_prompt = """
        You are an AI data classifier for a B2B SaaS platform.
        Analyze the customer feedback text and output ONLY a JSON object with:
        1. "clean_text": Rewrite the feedback in clear, professional sentences. Remove shorthand or typos.
        2. "intents": A list from exactly: ["bug_report", "feature_request", "usability_complaint", 
        "pricing_commercial", "process_complaint", "competitive_mention", "praise", "unclear"].
        3. "sentiment_score": Float from -1.0 (very negative) to 1.0 (very positive).
        4. "urgency_score": Float from 0.0 to 1.0.
        Judge this based on:
        - Is something broken and blocking the customer right now? (high)
        - Is there revenue, compliance, or renewal at risk? (high)
        - Is a competitor being considered as an alternative? (high)
        - Is this a nice-to-have suggestion with no immediate pain? (low)
        - Is this general feedback with no time pressure? (low)
        Base this purely on the business impact and time sensitivity implied by the text.
        """

        user_prompt = f"Raw Text: {raw_record.raw_text}"
        response_text = generate_text_with_bedrock(system_prompt, user_prompt, is_json=True)
        ai_result = json.loads(response_text)
        clean_text = ai_result.get("clean_text", raw_record.raw_text)
        intents = ai_result.get("intents", ["unclear"])

        embedding_vector = generate_embedding_with_bedrock(clean_text)

        urgency_score = round(max(0.0, min(1.0, float(ai_result.get("urgency_score", 0.0)))), 3)
        sentiment_score = round(max(-1.0, min(1.0, float(ai_result.get("sentiment_score", 0.0)))), 3)

        meta = raw_record.metadata_col or {}

        arr_value = float(meta.get("arr", 0.0))
        if arr_value == 0.0:
            print(f"[AI PIPELINE] Warning: ARR is 0.0 for {feedback_id}. Either no monetary value existed in the row or extraction missed it.")

        processed_record = FeedbackProcessed(
            feedback_id=feedback_id,
            clean_text=clean_text,
            intents=intents,
            sentiment_score=sentiment_score,
            urgency_keyword_score=urgency_score,
            arr=arr_value,
            embedding=embedding_vector
        )
        db.add(processed_record)

        raw_record.processed = True
        db.commit()

        print(f"[AI PIPELINE] Success! {feedback_id} classified as {intents}.")

    except Exception as e:
        db.rollback()
        print(f"[AI PIPELINE] Error processing {feedback_id}: {str(e)}")
    finally:
        db.close()