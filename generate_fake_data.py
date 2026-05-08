import pandas as pd
import random
from datetime import datetime, timedelta

# Define the columns that the LLM expects to extract intelligently
columns = [
    "Date",
    "Customer ID",
    "Company Name",
    "Segment",
    "Source",
    "Annual Contract Value (ARR)",
    "Feedback / Notes",
    "Status / Resolution"
]

data = [
    # Enterprise segment - High ARR (Impacts ARR at risk heavily)
    ("2026-05-01", "CUST-ENT-01", "Acme Corp", "Enterprise", "support_ticket", 150000.0, "The new dashboard is extremely slow when loading our historical data. It takes almost 15 seconds to load the charts. This is a critical issue for our ops team.", "Open"),
    ("2026-05-02", "CUST-ENT-02", "Globex Inc", "Enterprise", "sales_data", 220000.0, "Customer decided not to renew. They mentioned CompetitorX has a built-in AI reporting tool that we lack, and their pricing was 20% cheaper for the same seat count.", "Lost"),
    ("2026-05-03", "CUST-ENT-03", "Stark Ind", "Enterprise", "survey", 500000.0, "We need role-based access control (RBAC) at a more granular level. We cannot deploy this to our 5000 employees without it. Please add this feature.", "Pending"),
    ("2026-05-04", "CUST-ENT-04", "Wayne Ent", "Enterprise", "support_ticket", 310000.0, "System crash error 500 every time we try to export the weekly CSV report. This bug is holding up our payroll.", "Escalated"),
    ("2026-05-04", "CUST-ENT-05", "Cyberdyne", "Enterprise", "calling_entry", 185000.0, "Had a QBR with the client. They love the core product, huge praise for the customer success team, but they find the onboarding process too manual and complain about usability.", "Resolved"),
    
    # SME Segment - Medium/Low ARR, High Volume
    ("2026-05-05", "CUST-SME-01", "Bob's Burgers", "SME", "support_ticket", 12000.0, "I can't figure out how to change my billing details. The UI is very confusing and the settings page is hidden.", "Closed"),
    ("2026-05-05", "CUST-SME-02", "Dunder Mifflin", "SME", "survey", 15000.0, "The pricing is getting too high for a small team like ours. We might switch to a cheaper alternative next month.", "At Risk"),
    ("2026-05-06", "CUST-SME-03", "Vance Fridge", "SME", "marketing_lead", 8000.0, "Is there an integration with QuickBooks? We really need this feature before we can sign the contract.", "Open"),
    ("2026-05-06", "CUST-SME-04", "Michael Scott Paper", "SME", "support_ticket", 9500.0, "The mobile app keeps logging me out every 5 minutes. It's super frustrating.", "In Progress"),
    ("2026-05-07", "CUST-SME-05", "Prestige Worldwide", "SME", "survey", 25000.0, "Amazing product! It saves us 10 hours a week. Just wish the colors were customizable.", "Closed"),
    
    # Channel Partner
    ("2026-05-07", "CUST-CP-01", "TechDistro", "Channel Partner", "calling_entry", 45000.0, "Our clients are complaining about the slow onboarding process. The manual approval takes 3 days, which is hurting our sales.", "Open"),
    ("2026-05-08", "CUST-CP-02", "ResellerPro", "Channel Partner", "sales_data", 60000.0, "Lost deal. CompetitorY offered a better white-label solution. They said our branding is too hard to remove.", "Lost"),
]

# Generate more synthetic rows to reach 40 rows
sources = ["support_ticket", "sales_data", "marketing_lead", "calling_entry", "survey"]
segments = ["SME", "Enterprise", "Channel Partner"]
issues = [
    "The API is rate limiting us too aggressively. We need higher limits.", # Feature
    "When I click save, nothing happens. Huge bug.", # Bug
    "Navigation is terrible, I can't find anything.", # Usability
    "The approval process takes way too long.", # Process
    "CompetitorZ is offering the same thing for half the price.", # Competitive / Pricing
    "Love the new update, great job team!", # Praise
    "Can you integrate with Salesforce?", # Feature
    "Random 502 Bad Gateway errors on the dashboard.", # Bug
    "Takes 10 clicks just to download a report. Bad UX.", # Usability
    "Billing is too confusing, we got overcharged.", # Process/Pricing
]

start_date = datetime(2026, 5, 1)

for i in range(13, 41):
    segment = random.choice(segments)
    if segment == "Enterprise":
        arr = round(random.uniform(100000, 500000), 2)
    elif segment == "SME":
        arr = round(random.uniform(5000, 30000), 2)
    else:
        arr = round(random.uniform(30000, 80000), 2)
        
    date_val = (start_date + timedelta(days=random.randint(0, 10))).strftime("%Y-%m-%d")
    source = random.choice(sources)
    issue = random.choice(issues)
    
    data.append((
        date_val,
        f"CUST-GEN-{i}",
        f"Company {i}",
        segment,
        source,
        arr,
        issue,
        random.choice(["Open", "Closed", "Pending"])
    ))

df = pd.DataFrame(data, columns=columns)
df.to_excel("fake_voc_data.xlsx", index=False)
print("Generated fake_voc_data.xlsx with", len(df), "rows.")
