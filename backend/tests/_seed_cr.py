"""Directly update raw_response.confidence_reasoning for an existing scan on preview DB."""
import asyncio, os, json
from sqlalchemy import create_engine, text

DB = "postgresql://neondb_owner:npg_rA3U4MnWQDdh@ep-square-silence-ahbepao1-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require"
engine = create_engine(DB)

TARGET = "a07ffa15"  # scan prefix

with engine.begin() as conn:
    row = conn.execute(text("SELECT id, raw_response FROM scans WHERE id LIKE :p LIMIT 1"), {"p": f"{TARGET}%"}).fetchone()
    print("Before:", row.id, type(row.raw_response), str(row.raw_response)[:200] if row.raw_response else None)
    rr = row.raw_response or {}
    if isinstance(rr, str):
        rr = json.loads(rr)
    rr["confidence_reasoning"] = "Mock: clear broadside view of chest and belly, but legs are partly hidden by grass."
    conn.execute(text("UPDATE scans SET raw_response = CAST(:rr AS jsonb) WHERE id = :id"), {"rr": json.dumps(rr), "id": row.id})
    row2 = conn.execute(text("SELECT id, raw_response FROM scans WHERE id = :id"), {"id": row.id}).fetchone()
    print("After:", row2.id)
    rr2 = row2.raw_response if isinstance(row2.raw_response, dict) else json.loads(row2.raw_response)
    print("cr:", rr2.get("confidence_reasoning"))
    print("full scan id:", row.id)
