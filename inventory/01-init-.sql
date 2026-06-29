-- database/01-init.sql
-- Foundational schema for Aegis Telematics & Transport
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS telemetry_ingestion (
    event_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    vehicle_id VARCHAR(50) NOT NULL,
    driver_id VARCHAR(50) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    latitude DECIMAL(9,6),
    longitude DECIMAL(9,6),
    speed_mph INTEGER CHECK (speed_mph >= 0 AND speed_mph <= 150),
    engine_status VARCHAR(20) CHECK (engine_status IN ('ON', 'OFF', 'IDLE')),    
    eld_status VARCHAR(30) CHECK (eld_status IN ('ON_DUTY', 'OFF_DUTY', 'DRIVING', 'SLEEPER_BERTH')),
    raw_payload JSONB
);

CREATE INDEX idx_telemetry_timestamp ON telemetry_ingestion(timestamp);
CREATE INDEX idx_telemetry_vehicle ON telemetry_ingestion(vehicle_id);
CREATE INDEX idx_telemetry_driver ON telemetry_ingestion(driver_id);

COMMENT ON TABLE telemetry_ingestion IS 'Core ingestion table for continuous telematics streams';
COMMENT ON COLUMN telemetry_ingestion.raw_payload IS 'Original JSON payload for unstructured metrics and compliance audits';