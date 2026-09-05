-- Production schema for the Supplier Quality Risk Agent.
-- Carries the Phase 1 and Phase 2 decisions; see docs/design-decisions.md.
--
-- Grain:
--   production_volume  one part, one month
--   defects            one defect event (quantity = units affected)
--   reports_8d         one 8D report
--
-- Dimensional model: defects and production_volume are facts;
-- suppliers, parts and defect_codes are conformed dimensions.

DROP TABLE IF EXISTS public.reports_8d;
DROP TABLE IF EXISTS public.defects;
DROP TABLE IF EXISTS public.production_volume;
DROP TABLE IF EXISTS public.parts;
DROP TABLE IF EXISTS public.defect_codes;
DROP TABLE IF EXISTS public.suppliers;

CREATE TABLE public.suppliers (
    supplier_id    TEXT PRIMARY KEY,
    supplier_name  TEXT NOT NULL,
    commodity      TEXT NOT NULL,
    plant_location TEXT NOT NULL
);

CREATE TABLE public.defect_codes (
    defect_code TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    severity    TEXT NOT NULL
        CHECK (severity IN ('Critical', 'Major', 'Minor'))
);

CREATE TABLE public.parts (
    part_id        TEXT PRIMARY KEY,
    part_name      TEXT NOT NULL,
    supplier_id    TEXT NOT NULL REFERENCES public.suppliers(supplier_id),
    vehicle_system TEXT NOT NULL
);

CREATE TABLE public.production_volume (
    part_id        TEXT NOT NULL REFERENCES public.parts(part_id),
    month          DATE NOT NULL,
    units_produced INTEGER NOT NULL CHECK (units_produced > 0),
    PRIMARY KEY (part_id, month)
);

CREATE TABLE public.defects (
    defect_id     SERIAL PRIMARY KEY,
    part_id       TEXT NOT NULL REFERENCES public.parts(part_id),
    defect_code   TEXT NOT NULL REFERENCES public.defect_codes(defect_code),
    detected_date DATE NOT NULL,
    quantity      INTEGER NOT NULL CHECK (quantity > 0),
    line_station  TEXT NOT NULL
);

-- 8D reports. Eight disciplines stored as separate columns rather than one
-- blob: Phase 5 chunks on discipline boundaries, and separate columns mean
-- that happens without parsing. Same insight that took App 1 from 78% to 95%
-- with article-boundary chunking, built into the schema instead of handled
-- downstream.
--
-- Phase 2: status is indexed and filterable but never applied as a hard
-- filter. A closed 8D is the wrong answer to "what is failing now" and the
-- right answer to "has this happened before".
CREATE TABLE public.reports_8d (
    report_id        TEXT PRIMARY KEY,
    supplier_id      TEXT NOT NULL REFERENCES public.suppliers(supplier_id),
    defect_code      TEXT NOT NULL REFERENCES public.defect_codes(defect_code),
    part_id          TEXT REFERENCES public.parts(part_id),
    title            TEXT NOT NULL,
    opened_date      DATE NOT NULL,
    closed_date      DATE,
    status           TEXT NOT NULL CHECK (status IN ('Open', 'Closed')),
    d1_team          TEXT NOT NULL,
    d2_problem       TEXT NOT NULL,
    d3_containment   TEXT NOT NULL,
    d4_root_cause    TEXT NOT NULL,
    d5_corrective    TEXT NOT NULL,
    d6_implemented   TEXT NOT NULL,
    d7_prevent       TEXT NOT NULL,
    d8_closure       TEXT NOT NULL,
    CHECK (
        (status = 'Open'   AND closed_date IS NULL) OR
        (status = 'Closed' AND closed_date IS NOT NULL)
    ),
    CHECK (closed_date IS NULL OR closed_date >= opened_date)
);

-- Indexes for the query catalogue's access patterns.
CREATE INDEX idx_defects_part_date    ON public.defects (part_id, detected_date);
CREATE INDEX idx_defects_code         ON public.defects (defect_code);
CREATE INDEX idx_parts_supplier       ON public.parts (supplier_id);
CREATE INDEX idx_volume_month         ON public.production_volume (month);
CREATE INDEX idx_8d_supplier_status   ON public.reports_8d (supplier_id, status);
CREATE INDEX idx_8d_opened            ON public.reports_8d (opened_date);