-- =============================================================================
--  OLA RIDE INSIGHTS  |  SCHEMA, CLEANING & DATA MODEL
-- =============================================================================
--  Dialect : MySQL 8.0 (primary - the project brief connects MySQL to Power BI)
--  Also runs on SQLite 3.25+ (this is what the Streamlit SQL playground uses).
--
--  Dialect switches
--  ----------------
--  A handful of functions differ between engines (DAYNAME, WEEKDAY, ENGINE=).
--  Those lines come in pairs:
--        <mysql code>   -- [MySQL]       <- active by default
--        -- [SQLite] <sqlite code>        <- commented out by default
--  To run on SQLite, comment the "[MySQL]" lines and un-comment the "[SQLite]"
--  ones. `ola.sql_engine.to_dialect()` does this automatically for the tests.
--
--  Pipeline
--  --------
--  1. rides_raw       staging table - every column as text, exactly as exported
--  2. v_rides_clean   view - NULLIF('null'), TRIM, type casts   (cleaning)
--  3. ola_rides       final typed table + derived features       (preprocessing)
--  4. dim_vehicle / dim_payment   small dimensions used for JOINs
--  5. indexes + convenience views
--
--  NOTE: a NULL in this data is *structural* (e.g. no rating on a cancelled
--  ride). We never impute it - AVG()/COUNT() skip NULLs correctly on their own.
-- =============================================================================


-- -----------------------------------------------------------------------------
-- 0. Clean slate (safe to re-run)
-- -----------------------------------------------------------------------------
DROP VIEW  IF EXISTS v_successful_bookings;
DROP VIEW  IF EXISTS v_failed_bookings;
DROP TABLE IF EXISTS ola_rides;
DROP VIEW  IF EXISTS v_rides_clean;
DROP TABLE IF EXISTS dim_vehicle;
DROP TABLE IF EXISTS dim_payment;


-- -----------------------------------------------------------------------------
-- 1. Staging table (rides_raw) - one TEXT column per source column
--    Export sheet "July" (columns A:S) to CSV, then load it:
--      MySQL : LOAD DATA LOCAL INFILE 'OLA_July.csv' INTO TABLE rides_raw
--              FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
--              LINES TERMINATED BY '\n' IGNORE 1 LINES;
--      SQLite: .mode csv   /   .import --skip 1 OLA_July.csv rides_raw
--    (Create the table first so every column stays text.)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS rides_raw (
    Date                        VARCHAR(30),   -- 'YYYY-MM-DD HH:MM:SS'
    Time                        VARCHAR(10),
    Booking_ID                  VARCHAR(30),
    Booking_Status              VARCHAR(40),
    Customer_ID                 VARCHAR(30),
    Vehicle_Type                VARCHAR(30),
    Pickup_Location             VARCHAR(60),
    Drop_Location               VARCHAR(60),
    V_TAT                       VARCHAR(20),
    C_TAT                       VARCHAR(20),
    Canceled_Rides_by_Customer  VARCHAR(80),
    Canceled_Rides_by_Driver    VARCHAR(80),
    Incomplete_Rides            VARCHAR(10),
    Incomplete_Rides_Reason     VARCHAR(40),
    Booking_Value               VARCHAR(20),
    Payment_Method              VARCHAR(30),
    Ride_Distance               VARCHAR(20),
    Driver_Ratings              VARCHAR(10),
    Customer_Rating             VARCHAR(10)
);


-- -----------------------------------------------------------------------------
-- 2. Cleaning view
--    * TRIM        removes stray whitespace
--    * NULLIF      turns the literal text 'null' into a real SQL NULL
--    * CAST        gives every measure its proper numeric type
--    (CAST via DECIMAL first so '203.0' and '203' both convert without warnings)
-- -----------------------------------------------------------------------------
CREATE VIEW v_rides_clean AS
SELECT
    TRIM(Booking_ID)                                                   AS Booking_ID,
    TRIM(Customer_ID)                                                  AS Customer_ID,
    DATE(Date)                                                         AS Date,
    TRIM(Time)                                                         AS Time,
    Date                                                               AS Booking_Datetime,
    TRIM(Booking_Status)                                               AS Booking_Status,
    TRIM(Vehicle_Type)                                                 AS Vehicle_Type,
    TRIM(Pickup_Location)                                              AS Pickup_Location,
    TRIM(Drop_Location)                                                AS Drop_Location,
    CAST(NULLIF(TRIM(V_TAT), 'null') AS DECIMAL(6,1))                  AS V_TAT,
    CAST(NULLIF(TRIM(C_TAT), 'null') AS DECIMAL(6,1))                  AS C_TAT,
    NULLIF(TRIM(Canceled_Rides_by_Customer), 'null')                   AS Canceled_Rides_by_Customer,
    NULLIF(TRIM(Canceled_Rides_by_Driver), 'null')                     AS Canceled_Rides_by_Driver,
    NULLIF(TRIM(Incomplete_Rides), 'null')                             AS Incomplete_Rides,
    NULLIF(TRIM(Incomplete_Rides_Reason), 'null')                      AS Incomplete_Rides_Reason,
    CAST(CAST(TRIM(Booking_Value) AS DECIMAL(12,1)) AS SIGNED INTEGER) AS Booking_Value,
    NULLIF(TRIM(Payment_Method), 'null')                               AS Payment_Method,
    CAST(CAST(TRIM(Ride_Distance) AS DECIMAL(12,1)) AS SIGNED INTEGER) AS Ride_Distance,
    CAST(NULLIF(TRIM(Driver_Ratings), 'null') AS DECIMAL(3,1))         AS Driver_Ratings,
    CAST(NULLIF(TRIM(Customer_Rating), 'null') AS DECIMAL(3,1))        AS Customer_Rating
FROM rides_raw;


-- -----------------------------------------------------------------------------
-- 3. Final typed table
-- -----------------------------------------------------------------------------
CREATE TABLE ola_rides (
    Booking_ID                  VARCHAR(20)  NOT NULL PRIMARY KEY,
    Customer_ID                 VARCHAR(20)  NOT NULL,
    Date                        DATE         NOT NULL,
    Time                        VARCHAR(8)   NOT NULL,          -- 'HH:MM:SS'
    Booking_Datetime            DATETIME     NOT NULL,
    Ride_Hour                   TINYINT      NOT NULL,          -- 0-23
    Day_Name                    VARCHAR(10),
    Day_Of_Week_No              TINYINT,                        -- 1 = Monday ... 7 = Sunday
    Is_Weekend                  TINYINT,
    Time_Band                   VARCHAR(20),
    Booking_Status              VARCHAR(30)  NOT NULL,
    Is_Successful               TINYINT      NOT NULL,
    Is_Cancelled                TINYINT      NOT NULL,
    Failure_Type                VARCHAR(30),
    Failure_Reason              VARCHAR(60),
    Vehicle_Type                VARCHAR(20)  NOT NULL,
    Pickup_Location             VARCHAR(40),
    Drop_Location               VARCHAR(40),
    Is_Same_Pickup_Drop         TINYINT,
    V_TAT                       DECIMAL(6,1),
    C_TAT                       DECIMAL(6,1),
    Canceled_Rides_by_Customer  VARCHAR(60),
    Canceled_Rides_by_Driver    VARCHAR(60),
    Incomplete_Rides            VARCHAR(3),
    Incomplete_Rides_Reason     VARCHAR(30),
    Booking_Value               INT          NOT NULL,          -- INR; quoted fare if not completed
    Payment_Method              VARCHAR(20),
    Ride_Distance               INT          NOT NULL,          -- km; 0 if not completed
    Distance_Band               VARCHAR(15),
    Fare_Per_Km                 DECIMAL(8,2),
    Driver_Ratings              DECIMAL(3,1),
    Customer_Rating             DECIMAL(3,1),
    Rating_Gap                  DECIMAL(3,1)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;                         -- [MySQL]
-- [SQLite] );


-- Populate: the inner query adds the engine-specific calendar helpers once
-- (hr, dn, dow); the outer query derives everything else portably.
INSERT INTO ola_rides
SELECT
    t.Booking_ID, t.Customer_ID, t.Date, t.Time, t.Booking_Datetime,
    t.hr                                                          AS Ride_Hour,
    t.dn                                                          AS Day_Name,
    t.dow                                                         AS Day_Of_Week_No,
    CASE WHEN t.dow >= 6 THEN 1 ELSE 0 END                        AS Is_Weekend,
    CASE WHEN t.hr BETWEEN 0  AND 5  THEN 'Night (00-05)'
         WHEN t.hr BETWEEN 6  AND 11 THEN 'Morning (06-11)'
         WHEN t.hr BETWEEN 12 AND 17 THEN 'Afternoon (12-17)'
         ELSE 'Evening (18-23)' END                               AS Time_Band,
    t.Booking_Status,
    CASE WHEN t.Booking_Status = 'Success' THEN 1 ELSE 0 END      AS Is_Successful,
    CASE WHEN t.Booking_Status IN ('Canceled by Customer','Canceled by Driver')
         THEN 1 ELSE 0 END                                        AS Is_Cancelled,
    CASE t.Booking_Status
         WHEN 'Canceled by Customer' THEN 'Customer cancellation'
         WHEN 'Canceled by Driver'   THEN 'Driver cancellation'
         WHEN 'Driver Not Found'     THEN 'No driver found' END   AS Failure_Type,
    COALESCE(t.Canceled_Rides_by_Customer, t.Canceled_Rides_by_Driver,
             CASE WHEN t.Booking_Status = 'Driver Not Found' THEN 'Driver Not Found' END)
                                                                  AS Failure_Reason,
    t.Vehicle_Type, t.Pickup_Location, t.Drop_Location,
    CASE WHEN t.Pickup_Location = t.Drop_Location THEN 1 ELSE 0 END AS Is_Same_Pickup_Drop,
    t.V_TAT, t.C_TAT,
    t.Canceled_Rides_by_Customer, t.Canceled_Rides_by_Driver,
    t.Incomplete_Rides, t.Incomplete_Rides_Reason,
    t.Booking_Value, t.Payment_Method, t.Ride_Distance,
    CASE WHEN t.Booking_Status <> 'Success' OR t.Ride_Distance <= 0 THEN 'Not completed'
         WHEN t.Ride_Distance <= 5  THEN '1-5 km'
         WHEN t.Ride_Distance <= 10 THEN '6-10 km'
         WHEN t.Ride_Distance <= 20 THEN '11-20 km'
         WHEN t.Ride_Distance <= 30 THEN '21-30 km'
         WHEN t.Ride_Distance <= 40 THEN '31-40 km'
         ELSE '41-50 km' END                                      AS Distance_Band,
    CASE WHEN t.Booking_Status = 'Success' AND t.Ride_Distance > 0
         THEN ROUND(1.0 * t.Booking_Value / t.Ride_Distance, 2) END AS Fare_Per_Km,
    t.Driver_Ratings, t.Customer_Rating,
    ROUND(t.Driver_Ratings - t.Customer_Rating, 1)                AS Rating_Gap
FROM (
    SELECT c.*,
           CAST(SUBSTR(c.Time, 1, 2) AS SIGNED INTEGER)           AS hr,
           DAYNAME(c.Date)                                        AS dn,    -- [MySQL]
           WEEKDAY(c.Date) + 1                                    AS dow    -- [MySQL]
-- [SQLite]    CASE strftime('%w', c.Date) WHEN '0' THEN 'Sunday' WHEN '1' THEN 'Monday' WHEN '2' THEN 'Tuesday' WHEN '3' THEN 'Wednesday' WHEN '4' THEN 'Thursday' WHEN '5' THEN 'Friday' ELSE 'Saturday' END AS dn,
-- [SQLite]    ((CAST(strftime('%w', c.Date) AS INTEGER) + 6) % 7) + 1 AS dow
    FROM v_rides_clean c
) t;


-- -----------------------------------------------------------------------------
-- 4. Dimension tables (used to demonstrate JOINs)
--    Vehicle_Class and Has_AC are analyst assumptions (documented in README).
-- -----------------------------------------------------------------------------
CREATE TABLE dim_vehicle (
    Vehicle_Type   VARCHAR(20) PRIMARY KEY,
    Vehicle_Class  VARCHAR(20) NOT NULL,
    Has_AC         TINYINT     NOT NULL,
    Icon_URL       VARCHAR(200)
);
INSERT INTO dim_vehicle (Vehicle_Type, Vehicle_Class, Has_AC, Icon_URL) VALUES
    ('Bike',        'Two-wheeler',   0, 'https://cdn-icons-png.flaticon.com/128/9983/9983173.png'),
    ('eBike',       'Two-wheeler',   0, 'https://cdn-icons-png.flaticon.com/128/6839/6839867.png'),
    ('Auto',        'Three-wheeler', 0, 'https://cdn-icons-png.flaticon.com/128/16526/16526595.png'),
    ('Mini',        'Cab',           1, 'https://cdn-icons-png.flaticon.com/128/3202/3202926.png'),
    ('Prime Sedan', 'Cab',           1, 'https://cdn-icons-png.flaticon.com/128/14183/14183770.png'),
    ('Prime Plus',  'Cab',           1, 'https://cdn-icons-png.flaticon.com/128/11409/11409716.png'),
    ('Prime SUV',   'Cab',           1, 'https://cdn-icons-png.flaticon.com/128/9983/9983204.png');

CREATE TABLE dim_payment (
    Payment_Method VARCHAR(20) PRIMARY KEY,
    Is_Digital     TINYINT     NOT NULL
);
INSERT INTO dim_payment (Payment_Method, Is_Digital) VALUES
    ('Cash', 0), ('UPI', 1), ('Credit Card', 1), ('Debit Card', 1);


-- -----------------------------------------------------------------------------
-- 5. Indexes (speed up the GROUP BY / filter columns used by the queries)
-- -----------------------------------------------------------------------------
CREATE INDEX idx_rides_status   ON ola_rides (Booking_Status);
CREATE INDEX idx_rides_vehicle  ON ola_rides (Vehicle_Type);
CREATE INDEX idx_rides_customer ON ola_rides (Customer_ID);
CREATE INDEX idx_rides_date     ON ola_rides (Date);
CREATE INDEX idx_rides_payment  ON ola_rides (Payment_Method);


-- -----------------------------------------------------------------------------
-- 6. Convenience views (also handy as Power BI sources)
-- -----------------------------------------------------------------------------
CREATE VIEW v_successful_bookings AS
SELECT * FROM ola_rides WHERE Booking_Status = 'Success';

CREATE VIEW v_failed_bookings AS
SELECT * FROM ola_rides WHERE Booking_Status <> 'Success';


-- -----------------------------------------------------------------------------
-- 7. Reconciliation (run after loading; expected values for July 2024)
--    SELECT COUNT(*) FROM ola_rides;                            -- 103024
--    SELECT Booking_Status, COUNT(*) FROM ola_rides GROUP BY 1; -- 63967 / 18434 / 10499 / 10124
--    SELECT SUM(Booking_Value) FROM v_successful_bookings;      -- 35080467
-- -----------------------------------------------------------------------------
