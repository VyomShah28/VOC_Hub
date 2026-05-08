import json
import hashlib
import pandas as pd
from fastapi import BackgroundTasks
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.services.bedrock_client import generate_text_with_bedrock

from app.db.models import FeedbackRaw
from app.core.config import settings
from app.services.ai_pipeline import run_ai_pipeline
from app.services.clustering_service import run_clustering_pipeline

BATCH_SIZE = 30


def _make_feedback_id(raw_text: str, customer_id: str) -> str:
    content = f"{customer_id}:{raw_text[:120]}"
    return "UPL-" + hashlib.md5(content.encode()).hexdigest()[:12]


def _run_full_pipeline(feedback_ids: list[str]):
    """
    Single coordinated background task.
    Runs all AI pipelines to completion first, then clustering.
    Tracks how many succeeded before handing off.
    """
    succeeded = 0
    failed = 0

    for f_id in feedback_ids:
        try:
            run_ai_pipeline(f_id)
            succeeded += 1
        except Exception as e:
            failed += 1
            print(f"[PIPELINE] AI pipeline failed for {f_id}: {e}. Continuing.")

    print(f"[PIPELINE] AI stage complete — {succeeded} succeeded, {failed} failed.")

    if succeeded == 0:
        print("[PIPELINE] No records processed successfully. Aborting clustering.")
        return

    if failed > 0:
        print(f"[PIPELINE] Warning: {failed} records will be absent from this clustering run.")

    print("[PIPELINE] Handing off to clustering...")
    run_clustering_pipeline()


def process_excel_with_llm(
    df: pd.DataFrame,
    db: Session,
    background_tasks: BackgroundTasks
) -> int:
    all_new_ids = []

    for i in range(0, len(df), BATCH_SIZE):
        batch = df.iloc[i:i + BATCH_SIZE]
        print(f"[EXCEL] Processing batch {i // BATCH_SIZE + 1} ({len(batch)} rows)...")
        try:
            new_ids = _process_batch(batch, db)
            all_new_ids.extend(new_ids)
        except Exception as e:
            print(f"[EXCEL] Batch {i // BATCH_SIZE + 1} failed: {e}")
            continue

    if all_new_ids:
        background_tasks.add_task(_run_full_pipeline, all_new_ids)
        print(f"[PIPELINE] Enqueued full pipeline for {len(all_new_ids)} new records.")
    else:
        print("[PIPELINE] No new records to process.")

    return len(all_new_ids)


def _process_batch(batch: pd.DataFrame, db: Session) -> list[str]:
    """
    Returns list of newly inserted feedback IDs.
    No longer touches BackgroundTasks — caller owns task scheduling.
    """
    csv_data = batch.to_csv(index=False)

    system_prompt = """
    You are an intelligent data extraction pipeline for a B2B SaaS platform.
    Read the following CSV data (which came from an Excel upload).
    Convert each row into a standardized JSON record.

    Rules for extraction:
    1. 'source': Guess the data source based on columns (must be one of: 'support_ticket', 'sales_data', 'marketing_lead', 'calling_entry', 'survey', or 'unknown').
    2. 'segment': Extract or guess ('SME', 'Enterprise', 'Channel Partner', or 'Unknown').
    3. 'customer_id': Extract the CRM Number, Deal ID, Email, or Phone. If none, use 'Unknown'.
    4. 'date': Extract the date in YYYY-MM-DD format. If none is present, use null.
    5. 'raw_text': Combine ALL remarks, problem descriptions, case diagnoses, and notes into a single string. DO NOT LEAVE THIS BLANK.
    6. 'metadata': Put all remaining specific fields (company name, POC name, deal amount, resolution type, etc.) inside a nested JSON object.
    7. 'arr': Look for any column representing annual contract value, deal size, deal amount, revenue, ARR, or any monetary value.
        - Normalize to a float (strip ₹, $, commas, spaces).
        - Prefer annual or total contract value if multiple exist.
        - Use 0.0 if none found.
        - Must be a TOP LEVEL field, NOT inside metadata.

    Respond ONLY with a JSON object containing a single key "records" which is an array of these extracted objects.
    """

    user_prompt = f"CSV Data:\n{csv_data}"

    try:
        response_text = generate_text_with_bedrock(system_prompt, user_prompt, is_json=True)
        extracted_data = json.loads(response_text)
        records = extracted_data.get("records", [])
        print(f"[EXCEL] LLM extracted {len(records)} records from batch.")
    except Exception as e:
        print(f"[EXCEL] LLM extraction failed: {e}")
        raise ValueError("Failed to extract data using AI.")

    new_ids = []

    for record in records:
        raw_text = record.get("raw_text", "")
        if not raw_text or len(str(raw_text).strip()) < 5:
            continue

        record_date = None
        if record.get("date"):
            try:
                record_date = pd.to_datetime(record["date"]).date()
            except Exception:
                pass

        customer_id = str(record.get("customer_id", "Unknown"))
        f_id = _make_feedback_id(raw_text, customer_id)

        if db.execute(select(FeedbackRaw).where(FeedbackRaw.id == f_id)).scalar_one_or_none():
            print(f"[EXCEL] Duplicate, skipping: {f_id}")
            continue

        meta = record.get("metadata", {})
        meta["arr"] = record.get("arr", 0.0)

        db.add(FeedbackRaw(
            id=f_id,
            source=record.get("source", "unknown"),
            segment=record.get("segment", "Unknown"),
            customer_id=customer_id,
            date=record_date,
            raw_text=str(raw_text),
            metadata_col=meta
        ))
        db.commit()
        new_ids.append(f_id)

    return new_ids