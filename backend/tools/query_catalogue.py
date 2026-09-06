"""Fixed catalogue of parameterised queries.

Phase 1 chose this over text-to-SQL. The reasoning is in
docs/spike-text-to-sql.md — text-to-SQL passed the reliability threshold and
was rejected anyway, because one question passed by an unsound method and the
detection could not be shown to be airtight.

Every query here is written once and fixed. Parameters are bound by the
driver, never interpolated into the SQL string, so a hallucinated supplier ID
is a value that matches nothing rather than executable SQL.
"""

from typing import NamedTuple


class CatalogueEntry(NamedTuple):
    query_id: str
    description: str      # what the agent sees when choosing
    sql: str
    params: tuple[str, ...]


CATALOGUE: dict[str, CatalogueEntry] = {

    "supplier_ppm_over_window": CatalogueEntry(
        query_id="supplier_ppm_over_window",
        description=(
            "Defect PPM for one supplier over a date range. Returns one row "
            "with defect units, production units and PPM."
        ),
        params=("supplier_id", "start_month", "end_month"),
        sql="""
            SELECT
                s.supplier_id,
                s.supplier_name,
                SUM(v.units_produced)                       AS units_produced,
                COALESCE(SUM(d.qty), 0)                     AS defect_units,
                ROUND(COALESCE(SUM(d.qty), 0) * 1000000.0
                      / NULLIF(SUM(v.units_produced), 0), 2) AS ppm
            FROM production_volume v
            JOIN parts p     ON p.part_id = v.part_id
            JOIN suppliers s ON s.supplier_id = p.supplier_id
            LEFT JOIN (
                SELECT part_id,
                       date_trunc('month', detected_date)::date AS m,
                       SUM(quantity) AS qty
                FROM defects GROUP BY 1, 2
            ) d ON d.part_id = v.part_id AND d.m = v.month
            WHERE s.supplier_id = :supplier_id
              AND v.month >= :start_month
              AND v.month <= :end_month
            GROUP BY s.supplier_id, s.supplier_name
        """,
    ),

    "supplier_ppm_by_month": CatalogueEntry(
        query_id="supplier_ppm_by_month",
        description=(
            "Monthly PPM series for one supplier over a date range. Use this "
            "for trend questions — one row per month."
        ),
        params=("supplier_id", "start_month", "end_month"),
        sql="""
            SELECT
                v.month,
                SUM(v.units_produced)                       AS units_produced,
                COALESCE(SUM(d.qty), 0)                     AS defect_units,
                ROUND(COALESCE(SUM(d.qty), 0) * 1000000.0
                      / NULLIF(SUM(v.units_produced), 0), 2) AS ppm
            FROM production_volume v
            JOIN parts p ON p.part_id = v.part_id
            LEFT JOIN (
                SELECT part_id,
                       date_trunc('month', detected_date)::date AS m,
                       SUM(quantity) AS qty
                FROM defects GROUP BY 1, 2
            ) d ON d.part_id = v.part_id AND d.m = v.month
            WHERE p.supplier_id = :supplier_id
              AND v.month >= :start_month
              AND v.month <= :end_month
            GROUP BY v.month
            ORDER BY v.month
        """,
    ),

    "supplier_ppm_ranking": CatalogueEntry(
        query_id="supplier_ppm_ranking",
        description=(
            "All suppliers ranked by PPM over a date range, worst first. Use "
            "for 'which supplier is worst by rate' questions. Returns defect "
            "units and production units alongside PPM, so rate and raw count "
            "can be compared."
        ),
        params=("start_month", "end_month"),
        sql="""
            SELECT
                s.supplier_id,
                s.supplier_name,
                s.commodity,
                SUM(v.units_produced)                       AS units_produced,
                COALESCE(SUM(d.qty), 0)                     AS defect_units,
                ROUND(COALESCE(SUM(d.qty), 0) * 1000000.0
                      / NULLIF(SUM(v.units_produced), 0), 2) AS ppm
            FROM production_volume v
            JOIN parts p     ON p.part_id = v.part_id
            JOIN suppliers s ON s.supplier_id = p.supplier_id
            LEFT JOIN (
                SELECT part_id,
                       date_trunc('month', detected_date)::date AS m,
                       SUM(quantity) AS qty
                FROM defects GROUP BY 1, 2
            ) d ON d.part_id = v.part_id AND d.m = v.month
            WHERE v.month >= :start_month AND v.month <= :end_month
            GROUP BY s.supplier_id, s.supplier_name, s.commodity
            ORDER BY ppm DESC
        """,
    ),

    "defect_code_breakdown": CatalogueEntry(
        query_id="defect_code_breakdown",
        description=(
            "Defect codes recorded against one supplier over a date range, "
            "with each code's share of that supplier's defect units."
        ),
        params=("supplier_id", "start_date", "end_date"),
        sql="""
            SELECT
                d.defect_code,
                dc.description,
                dc.severity,
                COUNT(*)             AS events,
                SUM(d.quantity)      AS defect_units,
                ROUND(100.0 * SUM(d.quantity)
                      / SUM(SUM(d.quantity)) OVER (), 2) AS share_pct
            FROM defects d
            JOIN parts p        ON p.part_id = d.part_id
            JOIN defect_codes dc ON dc.defect_code = d.defect_code
            WHERE p.supplier_id = :supplier_id
              AND d.detected_date >= :start_date
              AND d.detected_date <= :end_date
            GROUP BY d.defect_code, dc.description, dc.severity
            ORDER BY defect_units DESC
        """,
    ),

    "part_ppm_ranking": CatalogueEntry(
        query_id="part_ppm_ranking",
        description=(
            "Parts ranked by PPM over a date range, worst first. Includes "
            "production volume so low-runner parts with inflated PPM are "
            "visible rather than hidden."
        ),
        params=("start_month", "end_month"),
        sql="""
            SELECT
                p.part_id,
                p.part_name,
                p.supplier_id,
                SUM(v.units_produced)                       AS units_produced,
                COALESCE(SUM(d.qty), 0)                     AS defect_units,
                ROUND(COALESCE(SUM(d.qty), 0) * 1000000.0
                      / NULLIF(SUM(v.units_produced), 0), 2) AS ppm
            FROM production_volume v
            JOIN parts p ON p.part_id = v.part_id
            LEFT JOIN (
                SELECT part_id,
                       date_trunc('month', detected_date)::date AS m,
                       SUM(quantity) AS qty
                FROM defects GROUP BY 1, 2
            ) d ON d.part_id = v.part_id AND d.m = v.month
            WHERE v.month >= :start_month AND v.month <= :end_month
            GROUP BY p.part_id, p.part_name, p.supplier_id
            ORDER BY ppm DESC
        """,
    ),

    "defect_code_by_supplier": CatalogueEntry(
        query_id="defect_code_by_supplier",
        description=(
            "Which suppliers record a given defect code, and each supplier's "
            "share of that code's occurrences. Use for concentration "
            "questions about a specific defect type."
        ),
        params=("defect_code", "start_date", "end_date"),
        sql="""
            SELECT
                p.supplier_id,
                s.supplier_name,
                COUNT(*)        AS events,
                SUM(d.quantity) AS defect_units,
                ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS share_pct
            FROM defects d
            JOIN parts p     ON p.part_id = d.part_id
            JOIN suppliers s ON s.supplier_id = p.supplier_id
            WHERE d.defect_code = :defect_code
              AND d.detected_date >= :start_date
              AND d.detected_date <= :end_date
            GROUP BY p.supplier_id, s.supplier_name
            ORDER BY events DESC
        """,
    ),

    "severity_breakdown": CatalogueEntry(
        query_id="severity_breakdown",
        description=(
            "Defect units by severity for one supplier over a date range. "
            "Use for 'how serious are their defects' questions."
        ),
        params=("supplier_id", "start_date", "end_date"),
        sql="""
            SELECT
                dc.severity,
                COUNT(*)        AS events,
                SUM(d.quantity) AS defect_units,
                ROUND(100.0 * SUM(d.quantity)
                      / SUM(SUM(d.quantity)) OVER (), 2) AS share_pct
            FROM defects d
            JOIN parts p         ON p.part_id = d.part_id
            JOIN defect_codes dc ON dc.defect_code = d.defect_code
            WHERE p.supplier_id = :supplier_id
              AND d.detected_date >= :start_date
              AND d.detected_date <= :end_date
            GROUP BY dc.severity
            ORDER BY defect_units DESC
        """,
    ),

    "parts_without_defects": CatalogueEntry(
        query_id="parts_without_defects",
        description=(
            "Parts with production volume but no defect events in a date "
            "range. Anchored on production_volume, so it answers absence "
            "correctly rather than returning what did occur."
        ),
        params=("start_month", "end_month"),
        sql="""
            SELECT
                p.part_id,
                p.part_name,
                p.supplier_id,
                SUM(v.units_produced) AS units_produced
            FROM production_volume v
            JOIN parts p ON p.part_id = v.part_id
            WHERE v.month >= :start_month AND v.month <= :end_month
              AND NOT EXISTS (
                  SELECT 1 FROM defects d
                  WHERE d.part_id = v.part_id
                    AND date_trunc('month', d.detected_date)::date = v.month
              )
            GROUP BY p.part_id, p.part_name, p.supplier_id
            ORDER BY units_produced DESC
        """,
    ),
}