
CREATE DATABASE smart_health_db;

USE smart_health_db;

-- User information
CREATE TABLE users (
    user_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(150) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(30) DEFAULT 'community_user',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Water quality records
CREATE TABLE water_quality (
    record_id INT AUTO_INCREMENT PRIMARY KEY,
    location VARCHAR(150) NOT NULL,
    ph FLOAT NOT NULL,
    turbidity FLOAT NOT NULL,
    temperature FLOAT NOT NULL,
    tds FLOAT NOT NULL,
    risk_level VARCHAR(30),
    risk_score FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Early warning alerts
CREATE TABLE alerts (
    alert_id INT AUTO_INCREMENT PRIMARY KEY,
    location VARCHAR(150) NOT NULL,
    risk_level VARCHAR(30),
    message TEXT,
    status VARCHAR(30) DEFAULT 'Active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Historical disease reports
CREATE TABLE disease_reports (
    report_id INT AUTO_INCREMENT PRIMARY KEY,
    location VARCHAR(150) NOT NULL,
    disease_name VARCHAR(100),
    case_count INT DEFAULT 0,
    report_date DATE NOT NULL
);

SHOW TABLES;
USE smart_health_db;

SELECT * FROM users;

SELECT * FROM water_quality;

SELECT * FROM alerts;
--

USE smart_health_db;

-- 1. Village information
CREATE TABLE IF NOT EXISTS villages (
    village_id INT AUTO_INCREMENT PRIMARY KEY,
    village_name VARCHAR(150) NOT NULL,
    district VARCHAR(150),
    state VARCHAR(100),
    latitude DECIMAL(10,7),
    longitude DECIMAL(10,7),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Government response actions
CREATE TABLE IF NOT EXISTS response_actions (
    action_id INT AUTO_INCREMENT PRIMARY KEY,
    village_id INT,
    location VARCHAR(150) NOT NULL,
    assigned_officer INT,
    action_description TEXT,
    status VARCHAR(50) DEFAULT 'Reported',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (village_id)
        REFERENCES villages(village_id),
    FOREIGN KEY (assigned_officer)
        REFERENCES users(user_id)
);

-- 3. Status update history
CREATE TABLE IF NOT EXISTS status_history (
    history_id INT AUTO_INCREMENT PRIMARY KEY,
    action_id INT NOT NULL,
    previous_status VARCHAR(50),
    new_status VARCHAR(50) NOT NULL,
    updated_by INT,
    remarks TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (action_id)
        REFERENCES response_actions(action_id),
    FOREIGN KEY (updated_by)
        REFERENCES users(user_id)
);
SHOW TABLES;
DESCRIBE disease_reports;
ALTER TABLE disease_reports
ADD COLUMN reported_by INT NULL,
ADD COLUMN remarks TEXT NULL,
ADD CONSTRAINT fk_disease_report_user
FOREIGN KEY (reported_by) REFERENCES users(user_id);
--
USE smart_health_db;

SELECT COUNT(*) AS total_reports,
       COALESCE(SUM(case_count), 0) AS total_cases
FROM disease_reports;

SELECT COUNT(*) AS total_villages
FROM villages;


USE smart_health_db;

SELECT * FROM villages;
USE smart_health_db;

INSERT INTO villages
(village_name, district, state, latitude, longitude)
VALUES
('Chikale', 'Belagavi', 'Karnataka', 15.6622753, 74.2645733),
('Gavase', 'Belagavi', 'Karnataka', 15.6545833, 74.2895019),
('Amagaon', 'Belagavi', 'Karnataka', 15.6455750, 74.3076122);
-- USE smart_health_db;

SELECT record_id, location, risk_level
FROM water_quality;
INSERT INTO villages
(village_name, district, state, latitude, longitude)
VALUES
('Community A', 'Belagavi', 'Karnataka', 15.8497, 74.4977);

DESCRIBE water_quality;


ALTER TABLE water_quality
ADD COLUMN rainfall_mm FLOAT NOT NULL DEFAULT 0;


SELECT
    record_id,
    location,
    ph,
    turbidity,
    rainfall_mm,
    risk_level
FROM water_quality
ORDER BY record_id DESC;

DESCRIBE response_actions;
SELECT
    history_id,
    action_id,
    previous_status,
    new_status,
    updated_by,
    remarks,
    updated_at
FROM status_history
ORDER BY history_id DESC;

SELECT user_id, name, email, role
FROM users;

UPDATE users
SET role = 'government_officer'
WHERE email = 'officer001@example.com';

UPDATE users
SET role = 'health_worker'
WHERE email = 'health001@example.com';

SELECT *
FROM water_quality
WHERE record_id = 3;


USE smart_health_db;