"""Verify the production schema landed correctly in Neon."""

import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
engine = create_engine(os.environ["DATABASE_URL"])

print("--- tables ---")
print(pd.read_sql(
    "SELECT table_name FROM information_schema.tables "
    "WHERE table_schema = 'public' ORDER BY table_name", engine))

print("\n--- constraint counts ---")
print(pd.read_sql(
    "SELECT constraint_type, COUNT(*) AS n "
    "FROM information_schema.table_constraints "
    "WHERE table_schema = 'public' "
    "GROUP BY constraint_type ORDER BY constraint_type", engine))

# '%%' escapes the wildcard. A single '%' is read as a parameter placeholder
# by psycopg before the statement reaches Postgres.
print("\n--- indexes ---")
print(pd.read_sql(
    "SELECT indexname FROM pg_indexes "
    "WHERE schemaname = 'public' AND indexname LIKE 'idx\\_%%' "
    "ORDER BY indexname", engine))

print("\n--- named CHECK constraints ---")
print(pd.read_sql(
    "SELECT conname, pg_get_constraintdef(oid) AS definition "
    "FROM pg_constraint "
    "WHERE connamespace = 'public'::regnamespace AND contype = 'c' "
    "  AND pg_get_constraintdef(oid) NOT LIKE '%%NOT NULL%%' "
    "ORDER BY conname", engine))

print("\n--- reports_8d columns ---")
print(pd.read_sql(
    "SELECT column_name, data_type, is_nullable "
    "FROM information_schema.columns "
    "WHERE table_schema = 'public' AND table_name = 'reports_8d' "
    "ORDER BY ordinal_position", engine))