create database incident_report;
create user db_admin with encrypted password 'your_secure_password';
    
    CREATE TABLE incidents (
    id SERIAL PRIMARY KEY,
    incident_id VARCHAR(50) UNIQUE,
    description TEXT,
    severity VARCHAR(20),
    confidence FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    ALTER TABLE incidents ADD COLUMN ai_reasoning TEXT;
    ALTER TABLE incidents ADD COLUMN ai_severity TEXT;
    ALTER TABLE incidents ADD COLUMN prompt_version TEXT;

    ALTER TABLE incidents ADD COLUMN deadline TIMESTAMP;
    ALTER TABLE incidents ADD COLUMN  policies_applied TEXT;

    ALTER TABLE incidents ADD COLUMN address TEXT;
    ALTER TABLE incidents ADD COLUMN zip_code INTEGER;
    ALTER TABLE incidents ADD COLUMN data_source VARCHAR(50);

    ALTER TABLE incidents ADD COLUMN transformation_log TEXT;

    GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO db_admin;
    GRANT ALL PRIVILEGES ON DATABASE incident_report TO db_admin;