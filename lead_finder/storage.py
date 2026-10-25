"""Small local SQLite store for saved leads. No account or external database required."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Iterable

import pandas as pd

from .config import DATABASE_PATH

COLUMNS = [
    "lead_id", "business_name", "category", "decision_maker", "decision_maker_title",
    "decision_maker_confidence", "decision_maker_source", "business_phone", "phone_source",
    "email", "email_status", "website", "website_source", "linkedin", "instagram", "facebook",
    "other_social", "address", "map_url", "source_url", "latitude", "longitude", "website_checked",
    "rating", "niche_searched", "location_searched", "saved_at",
]
# Sales-team fields: kept when a lead is re-saved from a newer search.
TEAM_COLUMNS = ["status", "notes"]
STATUSES = ["New", "Contacted", "Follow up", "Interested", "Won", "Not a fit"]


def connect() -> sqlite3.Connection:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database() -> None:
    """Create the table, and add any columns missing from a database made by an older version."""
    wanted = COLUMNS[1:] + TEAM_COLUMNS
    with connect() as connection:
        connection.execute('CREATE TABLE IF NOT EXISTS leads (lead_id TEXT PRIMARY KEY)')
        existing = {row["name"] for row in connection.execute("PRAGMA table_info(leads)")}
        for column in wanted:
            if column not in existing:
                connection.execute(f'ALTER TABLE leads ADD COLUMN "{column}" TEXT DEFAULT ""')
        connection.execute("UPDATE leads SET status = 'New' WHERE status IS NULL OR status = ''")


def save_leads(leads: Iterable[dict], niche: str, location: str) -> int:
    initialize_database()
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    rows = []
    for lead in leads:
        row = {column: lead.get(column, "") for column in COLUMNS}
        row.update(niche_searched=niche, location_searched=location, saved_at=stamp)
        rows.append([str(row.get(column, "") or "") for column in COLUMNS])
    if not rows:
        return 0
    columns_sql = ", ".join(f'"{c}"' for c in COLUMNS) + ', "status"'
    placeholders = ", ".join("?" for _ in COLUMNS) + ", 'New'"
    updates = ", ".join(f'"{c}"=excluded."{c}"' for c in COLUMNS if c != "lead_id")
    with connect() as connection:
        connection.executemany(
            f"INSERT INTO leads ({columns_sql}) VALUES ({placeholders}) ON CONFLICT(lead_id) DO UPDATE SET {updates}",
            rows,
        )
    return len(rows)


def load_leads() -> pd.DataFrame:
    initialize_database()
    with connect() as connection:
        return pd.read_sql_query(
            "SELECT * FROM leads ORDER BY saved_at DESC, business_name COLLATE NOCASE", connection
        )


def update_team_fields(changes: list[tuple[str, str, str]]) -> None:
    """changes: [(lead_id, status, notes)]"""
    initialize_database()
    with connect() as connection:
        connection.executemany(
            "UPDATE leads SET status = ?, notes = ? WHERE lead_id = ?",
            [(status, notes, lead_id) for lead_id, status, notes in changes],
        )


def delete_all_leads() -> None:
    initialize_database()
    with connect() as connection:
        connection.execute("DELETE FROM leads")
