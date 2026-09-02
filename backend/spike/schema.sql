DROP TABLE IF EXISTS spike.defects;
DROP TABLE IF EXISTS spike.production_volume;
DROP TABLE IF EXISTS spike.parts;
DROP TABLE IF EXISTS spike.defect_codes;
DROP TABLE IF EXISTS spike.suppliers;

CREATE TABLE spike.suppliers (
    supplier_id    TEXT PRIMARY KEY,
    supplier_name  TEXT NOT NULL,
    commodity      TEXT NOT NULL,
    plant_location TEXT NOT NULL
);

CREATE TABLE spike.defect_codes (
    defect_code TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    severity    TEXT NOT NULL
);

CREATE TABLE spike.parts (
    part_id        TEXT PRIMARY KEY,
    part_name      TEXT NOT NULL,
    supplier_id    TEXT NOT NULL REFERENCES spike.suppliers(supplier_id),
    vehicle_system TEXT NOT NULL
);

CREATE TABLE spike.production_volume (
    part_id        TEXT NOT NULL REFERENCES spike.parts(part_id),
    month          DATE NOT NULL,
    units_produced INTEGER NOT NULL CHECK (units_produced > 0),
    PRIMARY KEY (part_id, month)
);

CREATE TABLE spike.defects (
    defect_id     SERIAL PRIMARY KEY,
    part_id       TEXT NOT NULL REFERENCES spike.parts(part_id),
    defect_code   TEXT NOT NULL REFERENCES spike.defect_codes(defect_code),
    detected_date DATE NOT NULL,
    quantity      INTEGER NOT NULL CHECK (quantity > 0),
    line_station  TEXT NOT NULL
);
