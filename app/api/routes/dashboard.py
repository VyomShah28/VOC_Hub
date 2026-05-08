import uuid
import random
from collections import defaultdict
from datetime import date, timedelta
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sentence_transformers import SentenceTransformer
from sqlalchemy import and_, case, extract, func, select
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import (
    FeedbackProcessed, FeedbackRaw, Opportunity, Theme, ThemeWeeklyCount, ThemeItem
)

router = APIRouter(prefix="/api/v1/dashboard", tags=["Dashboard"])
BUG_BUCKETS         = {"bug_report", "process_complaint"}
FEATURE_BUCKETS     = {"feature_request"}
PAIN_POINT_BUCKETS  = {"bug_report", "usability_complaint", "process_complaint"}

MONTH_NAMES = ['Jan','Feb','Mar','Apr','May','Jun',
               'Jul','Aug','Sep','Oct','Nov','Dec']

embedder = SentenceTransformer('all-MiniLM-L6-v2')
class ChatQuery(BaseModel):
    question: str = Field(..., description="The natural language question from the user")


def _sentiment_label(score: float | None) -> str:
    if score is None:
        return "Neutral"
    if score > 0.1:
        return "Positive"
    if score < -0.1:
        return "Negative"
    return "Neutral"


def _alignment_status(score: float | None) -> str:
    """
    Map RAG alignment_score → human-readable roadmap status.
    These labels intentionally match what the RAG stage will write
    so the frontend gets consistent strings before and after RAG runs.
    """
    if score is None:
        return "Unreviewed"
    if score > 0.7:
        return "In Progress"
    if score > 0.3:
        return "Planned"
    return "Backlog"


@router.get("/overview")
def get_overview(db: Session = Depends(get_db)):
    """
    Returns everything the Overview page needs in one call:
      - 4 KPI cards
      - Monthly feedback + sentiment trend (last 6 months)
      - Sentiment distribution (donut)
      - Categorical breakdown table (per intent bucket)
    """

    total_feedback = (
        db.execute(select(func.count()).select_from(FeedbackRaw)).scalar() or 0
    )
    total_processed = (
        db.execute(select(func.count()).select_from(FeedbackProcessed)).scalar() or 0
    )
    positive_count = (
        db.execute(
            select(func.count())
            .select_from(FeedbackProcessed)
            .where(FeedbackProcessed.sentiment_score > 0.2)
        ).scalar() or 0
    )
    positive_sentiment_pct = round(
        (positive_count / total_processed * 100) if total_processed > 0 else 0.0, 1
    )
    active_issues = (
        db.execute(
            select(func.count())
            .select_from(Opportunity)
            .where(Opportunity.intent_bucket.in_(BUG_BUCKETS))
        ).scalar() or 0
    )
    feature_requests_count = (
        db.execute(
            select(func.count())
            .select_from(Opportunity)
            .where(Opportunity.intent_bucket.in_(FEATURE_BUCKETS))
        ).scalar() or 0
    )

    six_months_ago = date.today().replace(day=1) - timedelta(days=150)

    monthly_rows = db.execute(
        select(
            extract("year",  FeedbackRaw.date).label("year"),
            extract("month", FeedbackRaw.date).label("month"),
            func.count().label("count"),
            func.avg(FeedbackProcessed.sentiment_score).label("avg_sentiment"),
        )
        .join(FeedbackProcessed, FeedbackProcessed.feedback_id == FeedbackRaw.id, isouter=True)
        .where(FeedbackRaw.date >= six_months_ago)
        .group_by("year", "month")
        .order_by("year", "month")
    ).all()

    monthly_trend = [
        {
            "month":     MONTH_NAMES[int(r.month) - 1],
            "feedback":  r.count,
            # Sentiment scaled to 0–100 for dual-axis chart readability
            "sentiment": round(((r.avg_sentiment or 0.0) + 1.0) / 2.0 * 100, 1),
        }
        for r in monthly_rows
    ]

    dist = db.execute(
        select(
            func.count(case((FeedbackProcessed.sentiment_score >  0.2, 1))).label("positive"),
            func.count(case((FeedbackProcessed.sentiment_score < -0.2, 1))).label("negative"),
            func.count(case((
                and_(
                    FeedbackProcessed.sentiment_score >= -0.2,
                    FeedbackProcessed.sentiment_score <=  0.2,
                ),
                1,
            ))).label("neutral"),
        ).select_from(FeedbackProcessed)
    ).one()

    sentiment_distribution = {
        "positive": dist.positive or 0,
        "negative": dist.negative or 0,
        "neutral":  dist.neutral  or 0,
    }

    cat_rows = db.execute(
        select(
            Opportunity.intent_bucket,
            func.sum(Opportunity.frequency).label("count"),
            func.avg(Opportunity.avg_sentiment).label("avg_sentiment"),
        )
        .group_by(Opportunity.intent_bucket)
        .order_by(func.sum(Opportunity.frequency).desc())
    ).all()

    categorical_breakdown = [
        {
            "category":  r.intent_bucket.replace("_", " ").title(),
            "count":     int(r.count or 0),
            "sentiment": _sentiment_label(r.avg_sentiment),
            "change":    None,
        }
        for r in cat_rows
    ]

    return {
        "kpis": {
            "total_feedback":        total_feedback,
            "positive_sentiment_pct": positive_sentiment_pct,
            "active_issues":         active_issues,
            "feature_requests":      feature_requests_count,
        },
        "monthly_trend":        monthly_trend,
        "sentiment_distribution": sentiment_distribution,
        "categorical_breakdown": categorical_breakdown,
    }

@router.get("/pain-points")
def get_pain_points(db: Session = Depends(get_db)):
    """
    Returns everything the Pain Points page needs:
      - 4 KPI cards
      - Bar chart: pain points by theme (top 6)
      - Donut: top categories
      - Multi-series trend chart: top 3 themes week-over-week (last 8 weeks)
      - Issue inventory table (top 20)
    """

    pain_opps = db.execute(
        select(Opportunity)
        .where(Opportunity.intent_bucket.in_(PAIN_POINT_BUCKETS))
    ).scalars().all()

    total_pain_points = sum(o.frequency   for o in pain_opps)
    critical_issues   = sum(1             for o in pain_opps if o.priority_label == "Critical")
    total_arr_pain    = sum(o.total_arr   for o in pain_opps)

    total_arr_all = (
        db.execute(select(func.sum(FeedbackProcessed.arr))).scalar() or 1.0
    )
    customer_impact_pct = round((total_arr_pain / total_arr_all) * 100, 1)

    top_theme_rows = db.execute(
        select(
            Theme.name,
            Opportunity.frequency,
            Opportunity.priority_label,
            Opportunity.opportunity_score,
        )
        .join(Opportunity, Opportunity.theme_id == Theme.id)
        .where(Opportunity.intent_bucket.in_(PAIN_POINT_BUCKETS))
        .where(Theme.is_outlier == False)
        .order_by(Opportunity.opportunity_score.desc())
        .limit(6)
    ).all()

    pain_by_category = [
        {
            "category": r.name,
            "count":    r.frequency,
            "priority": r.priority_label,
        }
        for r in top_theme_rows
    ]

    eight_weeks_ago = date.today() - timedelta(weeks=8)

    top_3_ids = db.execute(
        select(Opportunity.theme_id)
        .join(Theme, Theme.id == Opportunity.theme_id)
        .where(Opportunity.intent_bucket.in_(PAIN_POINT_BUCKETS))
        .where(Theme.is_outlier == False)
        .order_by(Opportunity.opportunity_score.desc())
        .limit(3)
    ).scalars().all()

    id_to_name: dict[int, str] = {}
    if top_3_ids:
        id_to_name = {
            r.id: r.name
            for r in db.execute(
                select(Theme.id, Theme.name).where(Theme.id.in_(top_3_ids))
            ).all()
        }

    trend_map: dict = defaultdict(dict)
    if top_3_ids:
        for r in db.execute(
            select(
                ThemeWeeklyCount.theme_id,
                ThemeWeeklyCount.week_start,
                ThemeWeeklyCount.count,
            )
            .where(ThemeWeeklyCount.theme_id.in_(top_3_ids))
            .where(ThemeWeeklyCount.week_start >= eight_weeks_ago)
            .order_by(ThemeWeeklyCount.week_start)
        ).all():
            label = id_to_name.get(r.theme_id, f"Theme {r.theme_id}")
            trend_map[r.week_start][label] = r.count

    pain_trend = [
        {"week": str(week), **counts}
        for week, counts in sorted(trend_map.items())
    ]

    table_rows = db.execute(
        select(
            Theme.name,
            Opportunity.intent_bucket,
            Opportunity.priority_label,
            Opportunity.frequency,
            Opportunity.total_arr,
            Opportunity.opportunity_score,
        )
        .join(Theme, Theme.id == Opportunity.theme_id)
        .where(Opportunity.intent_bucket.in_(PAIN_POINT_BUCKETS))
        .where(Theme.is_outlier == False)
        .order_by(Opportunity.opportunity_score.desc())
        .limit(20)
    ).all()

    top_pain_points = [
        {
            "issue":      r.name,
            "category":   r.intent_bucket.replace("_", " ").title(),
            "priority":   r.priority_label,
            "mentions":   r.frequency,
            "arr_at_risk": round(r.total_arr, 0),
        }
        for r in table_rows
    ]

    return {
        "kpis": {
            "total_pain_points":  total_pain_points,
            "critical_issues":    critical_issues,
            "avg_resolution_time": None,
            "customer_impact_pct": customer_impact_pct,
        },
        "pain_by_category": pain_by_category,
        "pain_trend":       pain_trend,
        "top_pain_points":  top_pain_points,
    }


@router.get("/features")
def get_features(db: Session = Depends(get_db)):
    """
    Returns everything the Features page needs:
      - 4 KPI cards
      - Monthly bar chart: feature request volume (last 6 months)
      - Top feature requests table (top 20 by opportunity score)
    """

    feature_opps = db.execute(
        select(Opportunity)
        .where(Opportunity.intent_bucket.in_(FEATURE_BUCKETS))
    ).scalars().all()

    total_requests = sum(o.frequency for o in feature_opps)
    high_priority  = sum(1 for o in feature_opps if o.priority_label == "High")
    in_development = sum(
        1 for o in feature_opps
        if o.alignment_score is not None and o.alignment_score > 0.7
    )

    six_months_ago = date.today() - timedelta(days=180)

    feature_theme_ids = [o.theme_id for o in feature_opps]

    monthly_trend_rows = []
    if feature_theme_ids:
        monthly_trend_rows = db.execute(
            select(
                extract("year",  ThemeWeeklyCount.week_start).label("year"),
                extract("month", ThemeWeeklyCount.week_start).label("month"),
                func.sum(ThemeWeeklyCount.count).label("count"),
            )
            .where(ThemeWeeklyCount.theme_id.in_(feature_theme_ids))
            .where(ThemeWeeklyCount.week_start >= six_months_ago)
            .group_by("year", "month")
            .order_by("year", "month")
        ).all()

    feature_trend = [
        {
            "month":    MONTH_NAMES[int(r.month) - 1],
            "requests": int(r.count or 0),
            "priority": 0,
            "planned":  0,
        }
        for r in monthly_trend_rows
    ]

    top_rows = db.execute(
        select(
            Theme.name,
            Theme.keywords,
            Opportunity.frequency,
            Opportunity.priority_label,
            Opportunity.alignment_score,
            Opportunity.alignment_reason,
            Opportunity.opportunity_score,
            Opportunity.total_arr,
        )
        .join(Theme, Theme.id == Opportunity.theme_id)
        .where(Opportunity.intent_bucket.in_(FEATURE_BUCKETS))
        .where(Theme.is_outlier == False)
        .order_by(Opportunity.opportunity_score.desc())
        .limit(20)
    ).all()

    top_feature_requests = [
        {
            "feature":           r.name,
            "votes":             r.frequency,
            "status":            _alignment_status(r.alignment_score),
            "category":          (
                r.keywords[0].replace("_", " ").title()
                if r.keywords else "General"
            ),
            "arr_demand":        round(r.total_arr, 0),
            "priority":          r.priority_label,
            "opportunity_score": r.opportunity_score,
            "alignment_reason":  r.alignment_reason,
        }
        for r in top_rows
    ]

    return {
        "kpis": {
            "feature_requests": total_requests,
            "high_priority":    high_priority,
            "in_development":   in_development,
            "community_votes":  total_requests,
        },
        "feature_trend":       feature_trend,
        "top_feature_requests": top_feature_requests,
    }


@router.get("/bugs")
def get_bugs(db: Session = Depends(get_db)):
    """
    Returns everything the Bugs page needs:
      - 4 KPI cards
      - Line chart: weekly bug volume trend (last 8 weeks, top 5 themes aggregated)
      - Bar chart: bugs by severity
      - Open issues table (top 20)
    """

    bug_opps = db.execute(
        select(Opportunity)
        .where(Opportunity.intent_bucket.in_(BUG_BUCKETS))
    ).scalars().all()

    total_bugs  = sum(o.frequency for o in bug_opps)
    open_issues = len(bug_opps)   # treated as open until closed-loop tracking exists

    severity_counts: dict[str, int] = defaultdict(int)
    for o in bug_opps:
        severity_counts[o.priority_label] += 1

    bugs_by_severity = [
        {"severity": label, "count": severity_counts.get(label, 0)}
        for label in ["Critical", "High", "Medium", "Low"]
    ]

    eight_weeks_ago = date.today() - timedelta(weeks=8)

    top_bug_ids = db.execute(
        select(Opportunity.theme_id)
        .join(Theme, Theme.id == Opportunity.theme_id)
        .where(Opportunity.intent_bucket.in_(BUG_BUCKETS))
        .where(Theme.is_outlier == False)
        .order_by(Opportunity.opportunity_score.desc())
        .limit(5)
    ).scalars().all()

    resolution_trend = []
    if top_bug_ids:
        weekly_agg = db.execute(
            select(
                ThemeWeeklyCount.week_start,
                func.sum(ThemeWeeklyCount.count).label("open"),
            )
            .where(ThemeWeeklyCount.theme_id.in_(top_bug_ids))
            .where(ThemeWeeklyCount.week_start >= eight_weeks_ago)
            .group_by(ThemeWeeklyCount.week_start)
            .order_by(ThemeWeeklyCount.week_start)
        ).all()

        resolution_trend = [
            {
                "week":        str(r.week_start),
                "open":        int(r.open or 0),
                # resolved / in_progress require closed-loop status tracking
                "resolved":    0,
                "in_progress": 0,
            }
            for r in weekly_agg
        ]

    open_rows = db.execute(
        select(
            Theme.id,
            Theme.name,
            Opportunity.priority_label,
            Opportunity.frequency,
            Opportunity.total_arr,
            Opportunity.opportunity_score,
        )
        .join(Theme, Theme.id == Opportunity.theme_id)
        .where(Opportunity.intent_bucket.in_(BUG_BUCKETS))
        .where(Theme.is_outlier == False)
        .order_by(Opportunity.opportunity_score.desc())
        .limit(20)
    ).all()

    open_bugs = [
        {
            "id":          f"BUG-{str(r.id).zfill(3)}",
            "title":       r.name,
            "severity":    r.priority_label,
            "status":      "Open",
            "reports":     r.frequency,
            "arr_at_risk": round(r.total_arr, 0),
        }
        for r in open_rows
    ]

    return {
        "kpis": {
            "total_bugs":    total_bugs,
            "open_issues":   open_issues,
            # Both require closed-loop tracking (theme resolved_at timestamp)
            "resolved_this_month":  0,
            "avg_resolution_time":  None,
        },
        "bugs_by_severity":    bugs_by_severity,
        "bug_resolution_trend": resolution_trend,
        "open_bugs":           open_bugs,
    }

@router.post("/fake-data-matrix")
def generate_matrix_fake_data(db: Session = Depends(get_db)):
    """
    Generates 30 realistic entries tailored to Matrix Comsec's product lines.
    """
    intent_buckets = list(BUG_BUCKETS | FEATURE_BUCKETS | PAIN_POINT_BUCKETS)
    priorities = ["Critical", "High", "Medium", "Low"]
    
    # Real-world Themes for Matrix Comsec
    matrix_themes = [
        # Video Surveillance (SATATYA Range)
        {"name": "NVR RAID Configuration Error", "bucket": "Firmware Issue", "kw": ["NVR", "RAID", "Storage"]},
        {"name": "SATATYA Vision AI Face Detection", "bucket": "AI Analytics Request", "kw": ["AI", "Face Recognition", "Precision"]},
        {"name": "Low-Light Camera Noise", "bucket": "Hardware Malfunction", "kw": ["Camera", "Night Vision", "Sensor"]},
        {"name": "ANPR License Plate Accuracy", "bucket": "UI/UX Bug", "kw": ["Parking", "ANPR", "Detection"]},
        {"name": "VMS Client Latency", "bucket": "Connectivity Error", "kw": ["VMS", "Network", "Streaming"]},
        
        # Access Control & Time-Attendance (COSEC Range)
        {"name": "COSEC ARGO Face Template Sync", "bucket": "Sync Failure", "kw": ["Biometric", "Sync", "ARGO"]},
        {"name": "Visitor Management QR Pass", "bucket": "Mobile App Integration", "kw": ["Visitor", "QR Code", "Security"]},
        {"name": "Anti-Passback Logic Error", "bucket": "Security Enhancement", "kw": ["Logic", "Access", "Door"]},
        {"name": "Biometric Reader Recognition Speed", "bucket": "Slow Authentication", "kw": ["Fingerprint", "Latency", "Reader"]},
        {"name": "COSEC VYOM Cloud Integration", "bucket": "Cloud Sync", "kw": ["Cloud", "SaaS", "Management"]},
        
        # Telecom (ETERNITY & SARVAM Range)
        {"name": "IP-PBX SIP Trunk Registration", "bucket": "Connectivity Error", "kw": ["Telecom", "SIP", "Trunk"]},
        {"name": "VARTA Softphone Call Drop", "bucket": "UI/UX Bug", "kw": ["Mobile", "VoIP", "Softphone"]},
        {"name": "Gateway Voice Quality Issues", "bucket": "Hardware Malfunction", "kw": ["Gateway", "FXO", "Voice"]},
        {"name": "SARVAM UCS Multi-site Integration", "bucket": "Compatibility Issue", "kw": ["Telecom", "Unified Comm", "Server"]},
        {"name": "Emergency Conference Setup", "bucket": "Feature Request", "kw": ["Security", "Crisis", "Conference"]}
    ]

    # Expand to 30 entries by slightly varying the themes
    themes_to_create = []
    for i in range(30):
        base_theme = random.choice(matrix_themes)
        theme = Theme(
            intent_bucket=base_theme["bucket"],
            name=f"{base_theme['name']} - Case {i+1}",
            keywords=base_theme["kw"] + [f"Matrix_{i}"],
            description=f"Automated analysis of {base_theme['name']} regarding customer implementation at site {random.randint(100, 500)}.",
            first_seen=date.today() - timedelta(days=random.randint(30, 365)),
            last_seen=date.today(),
            item_count=random.randint(5, 50),
            is_outlier=random.random() < 0.1
        )
        db.add(theme)
        themes_to_create.append(theme)
    
    db.flush() 

    # Generate linked feedback and processing data
    for i, theme in enumerate(themes_to_create):
        raw_id = str(uuid.uuid4())
        
        # Realistic feedback text based on theme
        feedback_samples = [
            f"The {theme.name} is causing significant delays at our main entrance.",
            f"Need improvement on {theme.name} for our upcoming manufacturing plant deployment.",
            f"Customer reported a {theme.intent_bucket} related to {theme.name} during the night shift.",
            f"Technical support request for {theme.name} integration with third-party HRMS."
        ]
        
        raw = FeedbackRaw(
            id=raw_id,
            source=random.choice(["Partner Portal", "Technical Support", "Direct Inquiry", "Customer Email"]),
            segment=random.choice(["Manufacturing", "Hospitality", "BFSI", "Education", "Healthcare"]),
            customer_id=f"MATRIX-CUST-{random.randint(10000, 99999)}",
            date=date.today() - timedelta(days=random.randint(0, 30)),
            raw_text=random.choice(feedback_samples),
            metadata_col={"product_line": theme.name.split()[0], "region": "India-Vadodara"},
            processed=True
        )
        db.add(raw)
        db.flush()

        processed = FeedbackProcessed(
            feedback_id=raw_id,
            clean_text=f"Standardized issue: {theme.name}",
            intents=[theme.intent_bucket],
            sentiment_score=random.uniform(-0.8, 0.4), # Mostly neutral-to-negative for testing
            urgency_keyword_score=random.uniform(0.3, 0.9),
            arr=random.uniform(50000, 2000000), # Matrix deals with large enterprise contracts
            embedding=[random.uniform(-1, 1) for _ in range(384)]
        )
        db.add(processed)

        # Linking and Metrics
        db.add(ThemeItem(theme_id=theme.id, feedback_id=raw_id))
        db.add(ThemeWeeklyCount(
            theme_id=theme.id, 
            week_start=date.today() - timedelta(days=date.today().weekday()), 
            count=random.randint(1, 15)
        ))
        
        # Opportunities focused on ROI for Security hardware
        db.add(Opportunity(
            theme_id=theme.id,
            intent_bucket=theme.intent_bucket,
            frequency=theme.item_count,
            total_arr=random.uniform(500000, 5000000),
            avg_sentiment=random.uniform(-0.5, 0.5),
            avg_urgency=random.uniform(0.5, 1.0),
            avg_source_weight=1.2,
            velocity=random.uniform(-5.0, 15.0),
            alignment_score=random.uniform(0.6, 0.95),
            alignment_reason=f"High strategic value for {raw.segment} vertical.",
            opportunity_score=random.uniform(40.0, 95.0),
            priority_label=random.choice(priorities),
            updated_at=date.today()
        ))
        
    db.commit()
    return {"message": "Successfully generated 30 Matrix Comsec related entries."}

@router.delete("/wipe-data")
def wipe_all_data(db: Session = Depends(get_db)):

    """
    Deletes ALL rows from all tables.
    Useful for resetting local/dev database.
    """

    try:
        # Delete child tables first (important because of FK constraints)
        db.query(ThemeItem).delete()
        db.query(ThemeWeeklyCount).delete()
        db.query(Opportunity).delete()
        db.query(FeedbackProcessed).delete()
        db.query(FeedbackRaw).delete()
        db.query(Theme).delete()

        db.commit()

        return {
            "message": "All table data wiped successfully."
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to wipe database: {str(e)}"
        )
    
@router.post("/chat")
async def ask_your_data(query: ChatQuery, db: Session = Depends(get_db)):
    """
    Hybrid RAG Chatbot: 
    1. Vector searches specific feedback.
    2. Joins those matches to Theme/Opportunity for aggregate stats (frequency, ARR).
    3. Pulls global top issues for broad questions.
    """
    try:
        global embedder
        print(f"💬 [CHATBOT] User asks: '{query.question}'")
        question_embedding = embedder.encode(query.question).tolist()
        search_query = text("""
            SELECT fp.feedback_id, fp.clean_text, fp.intents, fp.arr, fr.source, fr.segment
            FROM feedback_processed fp
            JOIN feedback_raw fr ON fp.feedback_id = fr.id
            ORDER BY fp.embedding <=> :q_emb
            LIMIT 10
        """)
        
        raw_results = db.execute(search_query, {"q_emb": str(question_embedding)}).fetchall()
        
        if not raw_results:
            return {"answer": "I don't have any data matching that query yet."}
        feedback_ids = [r.feedback_id for r in raw_results]

        theme_results = db.execute(
            select(
                Theme.name, 
                Theme.intent_bucket, 
                Opportunity.frequency, 
                Opportunity.total_arr, 
                Opportunity.priority_label,
                Opportunity.velocity
            )
            .join(ThemeItem, ThemeItem.theme_id == Theme.id)
            .join(Opportunity, Opportunity.theme_id == Theme.id)
            .where(ThemeItem.feedback_id.in_(feedback_ids))
            .distinct()
        ).all()

        global_results = db.execute(
            select(Theme.name, Opportunity.intent_bucket, Opportunity.frequency, Opportunity.priority_label)
            .join(Theme, Theme.id == Opportunity.theme_id)
            .order_by(Opportunity.opportunity_score.desc())
            .limit(5)
        ).all()

        context_block = "=== RELEVANT AGGREGATED THEMES (Use this for frequency, ARR, or priority questions) ===\n"
        for r in theme_results:
            context_block += f"- Theme: {r.name} | Category: {r.intent_bucket} | Frequency: {r.frequency} | ARR at Risk: ${r.total_arr} | Priority: {r.priority_label}\n"

        context_block += "\n=== RELEVANT SPECIFIC FEEDBACK (Use this for specific customer quotes/examples) ===\n"
        for i, row in enumerate(raw_results):
            context_block += f"[{i+1}] Segment: {row.segment} | Source: {row.source} | ARR: ${row.arr}\n"
            context_block += f"    Feedback: {row.clean_text}\n"

        context_block += "\n=== GLOBAL SYSTEM TOP 5 ISSUES (Use ONLY if user asks for general 'top', 'highest', or 'most frequent' issues overall) ===\n"
        for r in global_results:
            context_block += f"- {r.name} ({r.intent_bucket}) - {r.frequency} mentions, Priority: {r.priority_label}\n"

        system_prompt = """
        You are an AI Product Analyst for a B2B SaaS company. 
        You are answering a question from leadership based on customer feedback.
        
        RULES:
        1. Base your answer STRICTLY on the Context provided below. Do not make up information.
        2. If the user asks about the "frequency", "priority", or "total impact" of a specific issue, use the 'RELEVANT AGGREGATED THEMES' data.
        3. If the user asks for examples or specific details, use the 'RELEVANT SPECIFIC FEEDBACK' data.
        4. If the user asks broad questions like "What are the most frequent bugs?", use the 'GLOBAL SYSTEM TOP 5 ISSUES'.
        5. If the context does not contain the answer, say "I don't have enough data to answer that."
        6. Cite the segments and ARR impact where relevant to show business value.
        """
        
        client = Groq(api_key=settings.GROQ_API_KEY)

        response = client.chat.completions.create(
            model="llama-3.1-8b-instant", # Or llama-3.3-70b-versatile for smarter routing
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Context Database Records:\n{context_block}\n\nUser Question: {query.question}"}
            ]
        )
        
        final_answer = response.choices[0].message.content

        return {
            "question": query.question,
            "answer": final_answer,
            "sources_used": len(raw_results),
            "themes_referenced": len(theme_results)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))