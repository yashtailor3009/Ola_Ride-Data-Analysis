-- =============================================================================
--  OLA RIDE INSIGHTS  |  ANALYSIS QUERIES
-- =============================================================================
--  Run AFTER ola_schema_and_cleaning.sql.  Tables used:
--     ola_rides    one row per booking (103,024 rows, July 2024)
--     dim_vehicle  Vehicle_Type -> Vehicle_Class, Has_AC, Icon_URL
--     dim_payment  Payment_Method -> Is_Digital
--
--  Portable SQL: every query runs unchanged on MySQL 8.0 and SQLite 3.25+
--  (no engine-specific functions; "100.0 *" forces decimal division).
--
--  Each query is preceded by tags read by the Streamlit app:
--     @id     short code        @group  menu section
--     @title  plain-English question
--     @note   what the result means for the business (the "so what")
--
--  Definitions used throughout
--     Completed / successful ride : Booking_Status = 'Success'
--     Revenue                      : SUM(Booking_Value) over completed rides only
--     Quoted fare lost             : SUM(Booking_Value) over failed bookings
--     Failed booking               : Canceled by Customer | Canceled by Driver | Driver Not Found
-- =============================================================================


-- #############################################################################
--  PART A - THE 10 REQUIRED QUESTIONS
-- #############################################################################

-- @id: Q01
-- @group: A. Required questions
-- @title: Retrieve all successful bookings
-- @note: 63,967 of 103,024 bookings (62.1%) were completed. The view v_successful_bookings returns the same rows.
SELECT *
FROM ola_rides
WHERE Booking_Status = 'Success';

-- @id: Q02
-- @group: A. Required questions
-- @title: Average ride distance for each vehicle type (all bookings)
-- @note: Matches the AVERAGEIF in the workbook's Sheet1. Cancelled bookings carry 0 km, which drags every average down - see Q02b for the like-for-like figure.
SELECT Vehicle_Type,
       ROUND(AVG(Ride_Distance), 2) AS Avg_Distance_All_Bookings_Km,
       COUNT(*)                     AS Bookings
FROM ola_rides
GROUP BY Vehicle_Type
ORDER BY Avg_Distance_All_Bookings_Km DESC;

-- @id: Q02b
-- @group: A. Required questions
-- @title: Average ride distance per vehicle type (completed rides only)
-- @note: The business-correct view. Every vehicle averages ~25 km except Auto at ~10 km: Auto is a short-hop product, the only vehicle that behaves differently.
SELECT Vehicle_Type,
       ROUND(AVG(Ride_Distance), 2) AS Avg_Distance_Completed_Km,
       COUNT(*)                     AS Completed_Rides
FROM ola_rides
WHERE Booking_Status = 'Success'
GROUP BY Vehicle_Type
ORDER BY Avg_Distance_Completed_Km DESC;

-- @id: Q03
-- @group: A. Required questions
-- @title: Total number of rides cancelled by customers
-- @note: 10,499 bookings (10.2% of all demand) were cancelled by the customer.
SELECT COUNT(*) AS Cancelled_By_Customer
FROM ola_rides
WHERE Booking_Status = 'Canceled by Customer';

-- @id: Q04
-- @group: A. Required questions
-- @title: Top 5 customers by number of rides booked
-- @note: Only one customer has 5 bookings; 26 customers tie on 4. Ties are broken by completed booking value, then Customer_ID, so the result is deterministic.
SELECT Customer_ID,
       COUNT(*) AS Total_Rides,
       SUM(CASE WHEN Booking_Status = 'Success' THEN Booking_Value ELSE 0 END) AS Completed_Booking_Value
FROM ola_rides
GROUP BY Customer_ID
ORDER BY Total_Rides DESC, Completed_Booking_Value DESC, Customer_ID
LIMIT 5;

-- @id: Q05
-- @group: A. Required questions
-- @title: Rides cancelled by drivers for personal and car-related issues
-- @note: 6,542 cancellations - the single largest driver cancellation reason (35.5% of driver cancellations).
SELECT COUNT(*) AS Driver_Cancelled_Personal_Car_Issue
FROM ola_rides
WHERE Canceled_Rides_by_Driver = 'Personal & Car related issue';

-- @id: Q06
-- @group: A. Required questions
-- @title: Maximum and minimum driver ratings for Prime Sedan bookings
-- @note: Ratings span the full 3.0-5.0 range. MAX/MIN ignore the NULL ratings of cancelled rides automatically.
SELECT MAX(Driver_Ratings) AS Max_Driver_Rating,
       MIN(Driver_Ratings) AS Min_Driver_Rating
FROM ola_rides
WHERE Vehicle_Type = 'Prime Sedan';

-- @id: Q07
-- @group: A. Required questions
-- @title: All rides where payment was made using UPI
-- @note: 25,881 completed rides (40.5% of completed rides) were paid by UPI.
SELECT *
FROM ola_rides
WHERE Payment_Method = 'UPI';

-- @id: Q08
-- @group: A. Required questions
-- @title: Average customer rating per vehicle type
-- @note: All vehicle types sit within 0.02 points of 4.00 - the differences are statistically insignificant (ANOVA p = 0.29).
SELECT Vehicle_Type,
       ROUND(AVG(Customer_Rating), 2) AS Avg_Customer_Rating,
       COUNT(Customer_Rating)         AS Rated_Rides
FROM ola_rides
GROUP BY Vehicle_Type
ORDER BY Avg_Customer_Rating DESC;

-- @id: Q09
-- @group: A. Required questions
-- @title: Total booking value of rides completed successfully
-- @note: INR 35.08 M realised revenue. Q09b removes the 3,926 rides flagged incomplete, which gives the stricter 'fully completed' figure.
SELECT SUM(Booking_Value) AS Total_Booking_Value_Successful
FROM ola_rides
WHERE Booking_Status = 'Success';

-- @id: Q09b
-- @group: A. Required questions
-- @title: Booking value of fully completed rides (successful AND not incomplete)
-- @note: INR 32.83 M. The INR 2.25 M gap is revenue booked on rides that ended early - it is exposed to refunds/disputes.
SELECT SUM(Booking_Value) AS Total_Booking_Value_Fully_Completed
FROM ola_rides
WHERE Booking_Status = 'Success' AND Incomplete_Rides = 'No';

-- @id: Q10
-- @group: A. Required questions
-- @title: All incomplete rides along with the reason
-- @note: 3,926 rides were marked incomplete, all of them inside 'Success' bookings.
SELECT Booking_ID, Customer_ID, Date, Vehicle_Type, Pickup_Location, Drop_Location,
       Ride_Distance, Booking_Value, Payment_Method, Incomplete_Rides_Reason
FROM ola_rides
WHERE Incomplete_Rides = 'Yes'
ORDER BY Date, Booking_ID;

-- @id: Q10b
-- @group: A. Required questions
-- @title: Incomplete rides - reason summary
-- @note: Customer demand (40.8%) and vehicle breakdown (40.5%) account for four in five incomplete rides; breakdown is equally likely on every vehicle type (chi-square p = 0.64).
SELECT Incomplete_Rides_Reason,
       COUNT(*)                                          AS Rides,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS Share_Pct,
       SUM(Booking_Value)                                AS Booking_Value_At_Risk
FROM ola_rides
WHERE Incomplete_Rides = 'Yes'
GROUP BY Incomplete_Rides_Reason
ORDER BY Rides DESC;


-- #############################################################################
--  PART B - OVERALL PERFORMANCE & DEMAND
-- #############################################################################

-- @id: B01
-- @group: B. Overall & demand
-- @title: Headline KPI summary
-- @note: Only 62.1% of demand converts into a completed ride; INR 21.45 M of quoted fare (38% of potential) is lost to failed bookings.
SELECT COUNT(*)                                                                AS Total_Bookings,
       SUM(Is_Successful)                                                      AS Completed_Rides,
       ROUND(100.0 * SUM(Is_Successful) / COUNT(*), 2)                         AS Success_Rate_Pct,
       SUM(CASE WHEN Is_Successful = 1 THEN Booking_Value ELSE 0 END)          AS Completed_Revenue,
       SUM(CASE WHEN Is_Successful = 0 THEN Booking_Value ELSE 0 END)          AS Quoted_Fare_Lost,
       ROUND(AVG(CASE WHEN Is_Successful = 1 THEN Booking_Value END), 2)       AS Avg_Fare_Completed,
       ROUND(AVG(CASE WHEN Is_Successful = 1 THEN Ride_Distance END), 2)       AS Avg_Distance_Completed_Km,
       ROUND(AVG(Driver_Ratings), 2)                                           AS Avg_Driver_Rating,
       ROUND(AVG(Customer_Rating), 2)                                          AS Avg_Customer_Rating,
       COUNT(DISTINCT Customer_ID)                                             AS Unique_Customers
FROM ola_rides;

-- @id: B02
-- @group: B. Overall & demand
-- @title: Booking status breakdown
-- @note: Driver-side failures (driver cancelled + no driver found) are 27.7% of all bookings - nearly three times the 10.2% cancelled by customers.
SELECT Booking_Status,
       COUNT(*)                                          AS Bookings,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS Share_Pct
FROM ola_rides
GROUP BY Booking_Status
ORDER BY Bookings DESC;

-- @id: B03
-- @group: B. Overall & demand
-- @title: Daily ride volume with 7-day moving average
-- @note: Volume is remarkably stable (about 3,320 bookings/day, coefficient of variation 2.1%). There is no growth or decay trend inside the month.
WITH daily AS (
    SELECT Date,
           COUNT(*)           AS Bookings,
           SUM(Is_Successful) AS Completed,
           SUM(CASE WHEN Is_Successful = 1 THEN Booking_Value ELSE 0 END) AS Revenue
    FROM ola_rides
    GROUP BY Date
)
SELECT Date, Bookings, Completed, Revenue,
       ROUND(AVG(Bookings) OVER (ORDER BY Date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW), 1) AS Bookings_7d_Avg
FROM daily
ORDER BY Date;

-- @id: B04
-- @group: B. Overall & demand
-- @title: Hourly demand and success rate (peak-hour check)
-- @note: All 24 hours sit within +/-3% of the average (uniformity test p = 0.74). There is no rush-hour peak in this data, so time-of-day driver reallocation cannot be justified from it.
SELECT Ride_Hour,
       COUNT(*)                                        AS Bookings,
       ROUND(100.0 * SUM(Is_Successful) / COUNT(*), 2) AS Success_Rate_Pct,
       RANK() OVER (ORDER BY COUNT(*) DESC)            AS Demand_Rank
FROM ola_rides
GROUP BY Ride_Hour
ORDER BY Ride_Hour;

-- @id: B05
-- @group: B. Overall & demand
-- @title: Weekday demand normalised per calendar day
-- @note: Mon-Wed look ~25% busier in raw totals only because July 2024 contained five of each (31 days = 4 weeks + 3 days). Per-day demand is flat - a calendar artefact, not real weekday seasonality.
SELECT Day_Of_Week_No, Day_Name,
       COUNT(*)                                    AS Total_Bookings,
       COUNT(DISTINCT Date)                        AS Calendar_Days,
       ROUND(1.0 * COUNT(*) / COUNT(DISTINCT Date), 1) AS Avg_Bookings_Per_Day,
       ROUND(100.0 * SUM(Is_Successful) / COUNT(*), 2) AS Success_Rate_Pct
FROM ola_rides
GROUP BY Day_Of_Week_No, Day_Name
ORDER BY Day_Of_Week_No;

-- @id: B06
-- @group: B. Overall & demand
-- @title: Performance by time band (equal 6-hour windows)
-- @note: Four equal windows give the same picture as the hourly view: no band is meaningfully busier, faster to complete or more expensive.
SELECT Time_Band,
       COUNT(*)                                        AS Bookings,
       ROUND(100.0 * SUM(Is_Successful) / COUNT(*), 2) AS Success_Rate_Pct,
       ROUND(AVG(CASE WHEN Is_Successful = 1 THEN Booking_Value END), 1) AS Avg_Fare_Completed,
       ROUND(AVG(V_TAT), 1)                            AS Avg_V_TAT
FROM ola_rides
GROUP BY Time_Band
ORDER BY MIN(Ride_Hour);

-- @id: B07
-- @group: B. Overall & demand
-- @title: Top 10 pickup locations by demand
-- @note: 50 pickup areas with near-identical demand and success rates (59.8%-64.0%). Only 1 of 50 deviates beyond chance, so there is no genuine failure 'hotspot'.
SELECT Pickup_Location,
       COUNT(*)                                        AS Bookings,
       ROUND(100.0 * SUM(Is_Successful) / COUNT(*), 2) AS Success_Rate_Pct,
       RANK() OVER (ORDER BY COUNT(*) DESC)            AS Demand_Rank
FROM ola_rides
GROUP BY Pickup_Location
ORDER BY Bookings DESC
LIMIT 10;

-- @id: B08
-- @group: B. Overall & demand
-- @title: Top 10 routes (pickup to drop)
-- @note: With 2,450 possible routes and ~42 bookings each, no corridor dominates: demand is spread thin across the whole network.
SELECT Pickup_Location, Drop_Location,
       COUNT(*)                                        AS Bookings,
       ROUND(100.0 * SUM(Is_Successful) / COUNT(*), 2) AS Success_Rate_Pct
FROM ola_rides
WHERE Pickup_Location <> Drop_Location
GROUP BY Pickup_Location, Drop_Location
ORDER BY Bookings DESC, Pickup_Location, Drop_Location
LIMIT 10;


-- #############################################################################
--  PART C - VEHICLE TYPE
-- #############################################################################

-- @id: C01
-- @group: C. Vehicle type
-- @title: Vehicle scorecard (volume, success, revenue, fare, distance, ratings)
-- @note: Prime Sedan leads on revenue and success rate, but the spread between vehicles (61.4%-63.0%) is within random variation (chi-square p = 0.35).
SELECT Vehicle_Type,
       COUNT(*)                                                           AS Bookings,
       ROUND(100.0 * SUM(Is_Successful) / COUNT(*), 2)                    AS Success_Rate_Pct,
       SUM(CASE WHEN Is_Successful = 1 THEN Booking_Value ELSE 0 END)     AS Revenue,
       ROUND(AVG(CASE WHEN Is_Successful = 1 THEN Booking_Value END), 1)  AS Avg_Fare,
       ROUND(AVG(CASE WHEN Is_Successful = 1 THEN Ride_Distance END), 1)  AS Avg_Distance_Km,
       ROUND(AVG(Customer_Rating), 2)                                     AS Avg_Customer_Rating,
       ROUND(AVG(Driver_Ratings), 2)                                      AS Avg_Driver_Rating,
       RANK() OVER (ORDER BY SUM(CASE WHEN Is_Successful = 1 THEN Booking_Value ELSE 0 END) DESC) AS Revenue_Rank
FROM ola_rides
GROUP BY Vehicle_Type
ORDER BY Revenue_Rank;

-- @id: C02
-- @group: C. Vehicle type
-- @title: Top 5 vehicle types by total ride distance (completed rides)
-- @note: Distance is driven by volume of completed rides, not by vehicle choice - the five leaders are separated by <5%, and Auto ranks last because its trips are 2.5x shorter.
SELECT Vehicle_Type,
       SUM(Ride_Distance)             AS Total_Distance_Km,
       COUNT(*)                       AS Completed_Rides,
       ROUND(AVG(Ride_Distance), 1)   AS Avg_Distance_Km
FROM ola_rides
WHERE Is_Successful = 1
GROUP BY Vehicle_Type
ORDER BY Total_Distance_Km DESC
LIMIT 5;

-- @id: C03
-- @group: C. Vehicle type
-- @title: Vehicle class summary (JOIN with dim_vehicle)
-- @note: Joins the vehicle dimension to roll seven vehicle types up into three classes. Cabs generate ~57% of revenue simply because they are 4 of the 7 types; success rate and distance are identical across classes except Three-wheeler distance (10 km).
SELECT d.Vehicle_Class,
       COUNT(*)                                                       AS Bookings,
       ROUND(100.0 * SUM(r.Is_Successful) / COUNT(*), 2)              AS Success_Rate_Pct,
       SUM(CASE WHEN r.Is_Successful = 1 THEN r.Booking_Value ELSE 0 END) AS Revenue,
       ROUND(AVG(CASE WHEN r.Is_Successful = 1 THEN r.Ride_Distance END), 1) AS Avg_Distance_Km
FROM ola_rides r
JOIN dim_vehicle d ON d.Vehicle_Type = r.Vehicle_Type
GROUP BY d.Vehicle_Class
ORDER BY Revenue DESC;

-- @id: C04
-- @group: C. Vehicle type
-- @title: Turn-around times (V_TAT, C_TAT) by vehicle type
-- @note: Turn-around times are identical across vehicles (V_TAT ~171, C_TAT ~85, units undocumented) and do not correlate with ratings or fares.
SELECT Vehicle_Type,
       ROUND(AVG(V_TAT), 1) AS Avg_V_TAT,
       ROUND(AVG(C_TAT), 1) AS Avg_C_TAT,
       COUNT(*)             AS Completed_Rides
FROM ola_rides
WHERE Is_Successful = 1
GROUP BY Vehicle_Type
ORDER BY Avg_V_TAT;


-- #############################################################################
--  PART D - REVENUE, PRICING & PAYMENTS
-- #############################################################################

-- @id: D01
-- @group: D. Revenue & pricing
-- @title: Revenue by payment method
-- @note: Cash still carries 55% of revenue (INR 19.3 M of cash to collect and reconcile); UPI is 40%; cards together are just 4.7%.
SELECT Payment_Method,
       COUNT(*)                                                          AS Rides,
       SUM(Booking_Value)                                                AS Revenue,
       ROUND(100.0 * SUM(Booking_Value) / SUM(SUM(Booking_Value)) OVER (), 2) AS Revenue_Share_Pct,
       ROUND(AVG(Booking_Value), 1)                                      AS Avg_Fare
FROM ola_rides
WHERE Is_Successful = 1
GROUP BY Payment_Method
ORDER BY Revenue DESC;

-- @id: D02
-- @group: D. Revenue & pricing
-- @title: Digital vs cash split (JOIN with dim_payment)
-- @note: About 45% of completed revenue is already digital. Average fare is the same for cash and digital riders, so a digital-first incentive does not need to target a particular ticket size.
SELECT CASE WHEN p.Is_Digital = 1 THEN 'Digital (UPI + cards)' ELSE 'Cash' END AS Payment_Type,
       COUNT(*)                                                        AS Rides,
       SUM(r.Booking_Value)                                            AS Revenue,
       ROUND(100.0 * SUM(r.Booking_Value) / SUM(SUM(r.Booking_Value)) OVER (), 2) AS Revenue_Share_Pct
FROM ola_rides r
JOIN dim_payment p ON p.Payment_Method = r.Payment_Method
WHERE r.Is_Successful = 1
GROUP BY p.Is_Digital
ORDER BY Revenue DESC;

-- @id: D03
-- @group: D. Revenue & pricing
-- @title: Top 5 customers by total booking value (completed rides)
-- @note: The five biggest customers together account for just 0.09% of revenue. There are no 'whale' accounts: growth must come from volume and retention, not key-account management.
SELECT Customer_ID,
       COUNT(*)           AS Completed_Rides,
       SUM(Booking_Value) AS Total_Booking_Value,
       ROUND(100.0 * SUM(Booking_Value) / (SELECT SUM(Booking_Value) FROM ola_rides WHERE Is_Successful = 1), 4) AS Share_Of_Revenue_Pct
FROM ola_rides
WHERE Is_Successful = 1
GROUP BY Customer_ID
ORDER BY Total_Booking_Value DESC, Customer_ID
LIMIT 5;

-- @id: D04
-- @group: D. Revenue & pricing
-- @title: Daily revenue with running total
-- @note: Daily revenue stays in a narrow INR 1.07-1.19 M band; the cumulative line is almost perfectly straight - steady but stagnant.
WITH daily AS (
    SELECT Date, SUM(Booking_Value) AS Revenue
    FROM ola_rides
    WHERE Is_Successful = 1
    GROUP BY Date
)
SELECT Date, Revenue,
       SUM(Revenue) OVER (ORDER BY Date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS Cumulative_Revenue
FROM daily
ORDER BY Date;

-- @id: D05
-- @group: D. Revenue & pricing
-- @title: Revenue leakage - quoted fare lost by failure type
-- @note: INR 21.45 M of quoted fare never converted: INR 10.18 M to driver cancellations, 5.77 M to customer cancellations and 5.50 M to 'driver not found'. Recovering just 10% would add ~6% to revenue.
SELECT Failure_Type,
       COUNT(*)           AS Failed_Bookings,
       SUM(Booking_Value) AS Quoted_Fare_Lost,
       ROUND(100.0 * SUM(Booking_Value) / SUM(SUM(Booking_Value)) OVER (), 2) AS Share_Of_Loss_Pct
FROM ola_rides
WHERE Is_Successful = 0
GROUP BY Failure_Type
ORDER BY Quoted_Fare_Lost DESC;

-- @id: D06
-- @group: D. Revenue & pricing
-- @title: Ride distance distribution per day
-- @note: Average completed-ride distance holds between 22.5 and 23.6 km on every single day of the month.
SELECT Date,
       COUNT(*)                     AS Completed_Rides,
       SUM(Ride_Distance)           AS Total_Distance_Km,
       ROUND(AVG(Ride_Distance), 2) AS Avg_Distance_Km,
       MIN(Ride_Distance)           AS Min_Distance_Km,
       MAX(Ride_Distance)           AS Max_Distance_Km
FROM ola_rides
WHERE Is_Successful = 1
GROUP BY Date
ORDER BY Date;

-- @id: D07
-- @group: D. Revenue & pricing
-- @title: Does fare grow with distance? (average fare by distance band)
-- @note: Pricing red flag: average fare is ~INR 550 in EVERY distance band - a 3 km ride costs as much as a 45 km ride (correlation 0.002). Fares are not distance-based in this data.
SELECT Distance_Band,
       COUNT(*)                     AS Completed_Rides,
       ROUND(AVG(Booking_Value), 1) AS Avg_Fare,
       ROUND(1.0 * SUM(Booking_Value) / SUM(Ride_Distance), 2) AS Fare_Per_Km_Weighted
FROM ola_rides
WHERE Is_Successful = 1
GROUP BY Distance_Band
ORDER BY MIN(Ride_Distance);

-- @id: D08
-- @group: D. Revenue & pricing
-- @title: Fare per km by vehicle type (pricing pattern)
-- @note: Auto's fare per km is 2.5x that of every other vehicle - not because Auto is dearer, but because the fare is the same ~INR 550 over a 10 km trip instead of 25 km.
SELECT Vehicle_Type,
       ROUND(AVG(Booking_Value), 1)                            AS Avg_Fare,
       ROUND(AVG(Ride_Distance), 1)                            AS Avg_Distance_Km,
       ROUND(1.0 * SUM(Booking_Value) / SUM(Ride_Distance), 2) AS Fare_Per_Km_Weighted,
       ROUND(AVG(Fare_Per_Km), 2)                              AS Avg_Of_Fare_Per_Km
FROM ola_rides
WHERE Is_Successful = 1
GROUP BY Vehicle_Type
ORDER BY Fare_Per_Km_Weighted DESC;

-- @id: D09
-- @group: D. Revenue & pricing
-- @title: Surge-pricing check - fare per km by hour of day
-- @note: The dataset has no surge multiplier. As a proxy, fare per km by hour stays in a narrow INR 22.9-25.9 band and success rate by hour is flat, so there is no visible price response to demand and surge effectiveness cannot be demonstrated.
SELECT Ride_Hour,
       COUNT(*)                                                AS Completed_Rides,
       ROUND(1.0 * SUM(Booking_Value) / SUM(Ride_Distance), 2) AS Fare_Per_Km_Weighted,
       ROUND(AVG(Booking_Value), 1)                            AS Avg_Fare
FROM ola_rides
WHERE Is_Successful = 1
GROUP BY Ride_Hour
ORDER BY Ride_Hour;

-- @id: D10
-- @group: D. Revenue & pricing
-- @title: Fare tiers and their share of revenue
-- @note: Pricing is heavy-tailed: the 6.8% of rides at INR 1,500 or more generate 28% of revenue.
SELECT CASE WHEN Booking_Value < 250  THEN '1. Under 250'
            WHEN Booking_Value < 500  THEN '2. 250-499'
            WHEN Booking_Value < 1000 THEN '3. 500-999'
            WHEN Booking_Value < 1500 THEN '4. 1,000-1,499'
            ELSE '5. 1,500 and above' END                             AS Fare_Tier,
       COUNT(*)                                                       AS Completed_Rides,
       SUM(Booking_Value)                                             AS Revenue,
       ROUND(100.0 * SUM(Booking_Value) / SUM(SUM(Booking_Value)) OVER (), 2) AS Revenue_Share_Pct
FROM ola_rides
WHERE Is_Successful = 1
GROUP BY CASE WHEN Booking_Value < 250  THEN '1. Under 250'
              WHEN Booking_Value < 500  THEN '2. 250-499'
              WHEN Booking_Value < 1000 THEN '3. 500-999'
              WHEN Booking_Value < 1500 THEN '4. 1,000-1,499'
              ELSE '5. 1,500 and above' END
ORDER BY Fare_Tier;


-- #############################################################################
--  PART E - CANCELLATIONS & FAILURES
-- #############################################################################

-- @id: E01
-- @group: E. Cancellations
-- @title: Customer cancellation reasons
-- @note: 55.7% of customer cancellations are triggered by the driver (not moving towards pickup 30.2% + asked to cancel 25.4%). Only 'change of plans' and 'wrong address' (29.4%) are genuinely customer-owned.
SELECT Canceled_Rides_by_Customer AS Reason,
       COUNT(*)                                          AS Cancellations,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS Share_Pct
FROM ola_rides
WHERE Booking_Status = 'Canceled by Customer'
GROUP BY Canceled_Rides_by_Customer
ORDER BY Cancellations DESC;

-- @id: E02
-- @group: E. Cancellations
-- @title: Driver cancellation reasons
-- @note: 64.5% of driver cancellations cite the customer side (customer related 29.4%, sick 19.8%, over capacity 15.3%); 35.5% are the driver's own readiness (personal & car issues).
SELECT Canceled_Rides_by_Driver AS Reason,
       COUNT(*)                                          AS Cancellations,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS Share_Pct
FROM ola_rides
WHERE Booking_Status = 'Canceled by Driver'
GROUP BY Canceled_Rides_by_Driver
ORDER BY Cancellations DESC;

-- @id: E03
-- @group: E. Cancellations
-- @title: Root-cause attribution of every failed booking
-- @note: ~88% of the 39,057 failed bookings trace back to the supply side (driver cancelled, no driver found, or customer cancelled because of the driver). Only ~12% are truly customer-owned.
WITH failed AS (
    SELECT CASE
             WHEN Booking_Status = 'Canceled by Driver' THEN '1. Driver cancelled'
             WHEN Booking_Status = 'Driver Not Found'   THEN '2. No driver found'
             WHEN Canceled_Rides_by_Customer IN ('Driver is not moving towards pickup location',
                                                 'Driver asked to cancel')
                  THEN '3. Customer cancelled - driver-triggered'
             ELSE '4. Customer cancelled - own reason'
           END AS Root_Cause,
           Booking_Value
    FROM ola_rides
    WHERE Is_Successful = 0
)
SELECT Root_Cause,
       COUNT(*)                                          AS Failed_Bookings,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS Share_Pct,
       SUM(Booking_Value)                                AS Quoted_Fare_Lost
FROM failed
GROUP BY Root_Cause
ORDER BY Root_Cause;

-- @id: E04
-- @group: E. Cancellations
-- @title: Failure mix by vehicle type (percent of each vehicle's bookings)
-- @note: Every vehicle shows the same ~38% failure rate split in the same proportions - the problem is platform-wide, not tied to any vehicle.
SELECT Vehicle_Type,
       COUNT(*) AS Bookings,
       ROUND(100.0 * SUM(CASE WHEN Booking_Status = 'Success'              THEN 1 ELSE 0 END) / COUNT(*), 2) AS Success_Pct,
       ROUND(100.0 * SUM(CASE WHEN Booking_Status = 'Canceled by Driver'   THEN 1 ELSE 0 END) / COUNT(*), 2) AS Driver_Cancel_Pct,
       ROUND(100.0 * SUM(CASE WHEN Booking_Status = 'Canceled by Customer' THEN 1 ELSE 0 END) / COUNT(*), 2) AS Customer_Cancel_Pct,
       ROUND(100.0 * SUM(CASE WHEN Booking_Status = 'Driver Not Found'     THEN 1 ELSE 0 END) / COUNT(*), 2) AS No_Driver_Pct
FROM ola_rides
GROUP BY Vehicle_Type
ORDER BY Success_Pct DESC;

-- @id: E05
-- @group: E. Cancellations
-- @title: Incomplete rides by vehicle and reason
-- @note: Incomplete rides are 5.7%-6.5% of completed rides on every vehicle. Vehicle breakdowns are not concentrated in any one fleet.
SELECT Vehicle_Type,
       SUM(CASE WHEN Incomplete_Rides_Reason = 'Customer Demand'   THEN 1 ELSE 0 END) AS Customer_Demand,
       SUM(CASE WHEN Incomplete_Rides_Reason = 'Vehicle Breakdown' THEN 1 ELSE 0 END) AS Vehicle_Breakdown,
       SUM(CASE WHEN Incomplete_Rides_Reason = 'Other Issue'       THEN 1 ELSE 0 END) AS Other_Issue,
       SUM(CASE WHEN Incomplete_Rides = 'Yes' THEN 1 ELSE 0 END)                       AS Incomplete_Total,
       ROUND(100.0 * SUM(CASE WHEN Incomplete_Rides = 'Yes' THEN 1 ELSE 0 END) / COUNT(*), 2) AS Incomplete_Pct_Of_Completed
FROM ola_rides
WHERE Is_Successful = 1
GROUP BY Vehicle_Type
ORDER BY Vehicle_Type;


-- #############################################################################
--  PART F - RATINGS
-- #############################################################################

-- @id: F01
-- @group: F. Ratings
-- @title: Rating distribution - drivers vs customers
-- @note: Ratings are spread evenly from 3.0 to 5.0 (each band holds 22-27% of rides) and none fall below 3.0 - a rating floor that makes the score almost useless for spotting bad experiences.
SELECT CASE WHEN Driver_Ratings < 3.5 THEN '3.0 - 3.4'
            WHEN Driver_Ratings < 4.0 THEN '3.5 - 3.9'
            WHEN Driver_Ratings < 4.5 THEN '4.0 - 4.4'
            ELSE '4.5 - 5.0' END AS Rating_Band,
       COUNT(*) AS Driver_Rated_Rides,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS Driver_Share_Pct
FROM ola_rides
WHERE Is_Successful = 1
GROUP BY CASE WHEN Driver_Ratings < 3.5 THEN '3.0 - 3.4'
              WHEN Driver_Ratings < 4.0 THEN '3.5 - 3.9'
              WHEN Driver_Ratings < 4.5 THEN '4.0 - 4.4'
              ELSE '4.5 - 5.0' END
ORDER BY Rating_Band;

-- @id: F02
-- @group: F. Ratings
-- @title: Customer vs driver ratings (cross-tab of rating bands)
-- @note: If good rides earned good ratings from both sides, the diagonal would dominate. Cells hold 5-7% each with no diagonal pattern - the two ratings are statistically independent (r = -0.003).
WITH banded AS (
    SELECT CASE WHEN Driver_Ratings  < 3.5 THEN 'D 3.0-3.4' WHEN Driver_Ratings  < 4.0 THEN 'D 3.5-3.9'
                WHEN Driver_Ratings  < 4.5 THEN 'D 4.0-4.4' ELSE 'D 4.5-5.0' END AS Driver_Band,
           CASE WHEN Customer_Rating < 3.5 THEN 'C 3.0-3.4' WHEN Customer_Rating < 4.0 THEN 'C 3.5-3.9'
                WHEN Customer_Rating < 4.5 THEN 'C 4.0-4.4' ELSE 'C 4.5-5.0' END AS Customer_Band
    FROM ola_rides
    WHERE Is_Successful = 1
)
SELECT Driver_Band,
       SUM(CASE WHEN Customer_Band = 'C 3.0-3.4' THEN 1 ELSE 0 END) AS C_3_0_to_3_4,
       SUM(CASE WHEN Customer_Band = 'C 3.5-3.9' THEN 1 ELSE 0 END) AS C_3_5_to_3_9,
       SUM(CASE WHEN Customer_Band = 'C 4.0-4.4' THEN 1 ELSE 0 END) AS C_4_0_to_4_4,
       SUM(CASE WHEN Customer_Band = 'C 4.5-5.0' THEN 1 ELSE 0 END) AS C_4_5_to_5_0
FROM banded
GROUP BY Driver_Band
ORDER BY Driver_Band;

-- @id: F03
-- @group: F. Ratings
-- @title: Share of low ratings (3.5 or below) by vehicle type
-- @note: 27-28% of rides earn a 3.5-or-below rating on every vehicle, for customers and drivers alike.
SELECT Vehicle_Type,
       ROUND(100.0 * SUM(CASE WHEN Customer_Rating <= 3.5 THEN 1 ELSE 0 END) / COUNT(Customer_Rating), 2) AS Low_Customer_Rating_Pct,
       ROUND(100.0 * SUM(CASE WHEN Driver_Ratings  <= 3.5 THEN 1 ELSE 0 END) / COUNT(Driver_Ratings), 2)  AS Low_Driver_Rating_Pct,
       COUNT(Customer_Rating) AS Rated_Rides
FROM ola_rides
GROUP BY Vehicle_Type
ORDER BY Vehicle_Type;

-- @id: F04
-- @group: F. Ratings
-- @title: Do longer waits hurt ratings? (ratings by V_TAT quartile)
-- @note: Hypothesis test: if long vehicle turn-around times annoyed riders, Q4 ratings would be lower. They are identical (~4.0), so ratings are not responding to service speed.
WITH q AS (
    SELECT V_TAT, Customer_Rating, Driver_Ratings,
           NTILE(4) OVER (ORDER BY V_TAT) AS V_TAT_Quartile
    FROM ola_rides
    WHERE Is_Successful = 1
)
SELECT V_TAT_Quartile,
       ROUND(MIN(V_TAT), 0)           AS V_TAT_From,
       ROUND(MAX(V_TAT), 0)           AS V_TAT_To,
       ROUND(AVG(Customer_Rating), 3) AS Avg_Customer_Rating,
       ROUND(AVG(Driver_Ratings), 3)  AS Avg_Driver_Rating,
       COUNT(*)                       AS Rides
FROM q
GROUP BY V_TAT_Quartile
ORDER BY V_TAT_Quartile;


-- #############################################################################
--  PART G - CUSTOMER BEHAVIOUR
-- #############################################################################

-- @id: G01
-- @group: G. Customers
-- @title: Bookings per customer (repeat-usage distribution)
-- @note: 91.6% of customers booked exactly once in July. Only 8.4% are repeat users, and no customer booked more than five times.
WITH per_customer AS (
    SELECT Customer_ID, COUNT(*) AS Rides
    FROM ola_rides
    GROUP BY Customer_ID
)
SELECT Rides AS Bookings_Per_Customer,
       COUNT(*) AS Customers,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS Share_Pct
FROM per_customer
GROUP BY Rides
ORDER BY Rides;

-- @id: G02
-- @group: G. Customers
-- @title: Customers who never completed a ride (anti-join pattern)
-- @note: 36.6% of customers (34,557) booked in July but never completed a single ride: acquisition spend that never converted, and the largest churn-risk pool in the data.
SELECT COUNT(*) AS Customers_Without_Completed_Ride,
       (SELECT COUNT(DISTINCT Customer_ID) FROM ola_rides) AS All_Customers,
       ROUND(100.0 * COUNT(*) / (SELECT COUNT(DISTINCT Customer_ID) FROM ola_rides), 2) AS Share_Pct
FROM (
    SELECT Customer_ID
    FROM ola_rides
    GROUP BY Customer_ID
    HAVING SUM(Is_Successful) = 0
) AS never_completed;

-- @id: G03
-- @group: G. Customers
-- @title: Customer value deciles (share of revenue by spend decile)
-- @note: The top 10% of paying customers contribute 35.5% of revenue, but this is fare-driven, not loyalty-driven: 80% of them completed a single ride and 79% of their spend came from single fares of INR 1,500+. No individual customer exceeds 0.02% of revenue.
WITH spend AS (
    SELECT Customer_ID, SUM(Booking_Value) AS Spend
    FROM ola_rides
    WHERE Is_Successful = 1
    GROUP BY Customer_ID
),
ranked AS (
    SELECT Customer_ID, Spend, NTILE(10) OVER (ORDER BY Spend DESC) AS Decile
    FROM spend
)
SELECT Decile,
       COUNT(*)   AS Customers,
       SUM(Spend) AS Revenue,
       ROUND(100.0 * SUM(Spend) / SUM(SUM(Spend)) OVER (), 2) AS Revenue_Share_Pct
FROM ranked
GROUP BY Decile
ORDER BY Decile;

-- @id: G04
-- @group: G. Customers
-- @title: Customers with repeated failed bookings (win-back list)
-- @note: 1,857 customers had two or more failed bookings in a single month; 64 had three or more. These are the customers most likely to leave and the cheapest group to win back with a priority-dispatch offer.
SELECT Customer_ID,
       COUNT(*)                                        AS Total_Bookings,
       SUM(CASE WHEN Is_Successful = 0 THEN 1 ELSE 0 END) AS Failed_Bookings,
       SUM(Is_Successful)                              AS Completed_Rides
FROM ola_rides
GROUP BY Customer_ID
HAVING SUM(CASE WHEN Is_Successful = 0 THEN 1 ELSE 0 END) >= 2
ORDER BY Failed_Bookings DESC, Total_Bookings DESC, Customer_ID
LIMIT 100;


-- #############################################################################
--  PART H - ANOMALY & FRAUD DETECTION
-- #############################################################################

-- @id: H01
-- @group: H. Anomalies & fraud
-- @title: Bookings where pickup equals drop
-- @note: 2,121 bookings (2.1%) start and end at the same place, and 1,306 of them were 'completed' with an average distance of 22.7 km. Either round trips or location errors - worth a data-capture review.
SELECT Booking_Status,
       COUNT(*)                     AS Bookings,
       ROUND(AVG(Ride_Distance), 1) AS Avg_Distance_Km,
       SUM(Booking_Value)           AS Booking_Value
FROM ola_rides
WHERE Pickup_Location = Drop_Location
GROUP BY Booking_Status
ORDER BY Bookings DESC;

-- @id: H02
-- @group: H. Anomalies & fraud
-- @title: Extreme fare per km (completed rides above INR 500/km)
-- @note: 889 completed rides were charged more than INR 500 per km (typical is ~INR 20/km). Review for mis-keyed distance, mis-priced fares or manual overrides.
SELECT Booking_ID, Customer_ID, Date, Vehicle_Type, Ride_Distance, Booking_Value, Fare_Per_Km, Payment_Method
FROM ola_rides
WHERE Is_Successful = 1 AND Fare_Per_Km > 500
ORDER BY Fare_Per_Km DESC, Booking_ID
LIMIT 100;

-- @id: H03
-- @group: H. Anomalies & fraud
-- @title: High fare on a very short ride (fare >= INR 1,500 and distance <= 5 km)
-- @note: 577 completed rides combine a premium fare with a trip of 5 km or less - the classic signature of fare inflation or mis-recorded distance.
SELECT Booking_ID, Customer_ID, Date, Vehicle_Type, Ride_Distance, Booking_Value, Payment_Method
FROM ola_rides
WHERE Is_Successful = 1 AND Booking_Value >= 1500 AND Ride_Distance <= 5
ORDER BY Booking_Value DESC, Booking_ID
LIMIT 100;

-- @id: H04
-- @group: H. Anomalies & fraud
-- @title: 'AC is Not working' cancellations on vehicles that have no AC (JOIN)
-- @note: 686 of the 1,568 AC-related cancellations (43.8%) came from Bike, eBike and Auto - vehicles with no AC. Customers are choosing a reason that cannot apply, so the reason picker needs to be vehicle-aware.
SELECT r.Vehicle_Type,
       COUNT(*) AS AC_Complaint_Cancellations
FROM ola_rides r
JOIN dim_vehicle d ON d.Vehicle_Type = r.Vehicle_Type
WHERE r.Canceled_Rides_by_Customer = 'AC is Not working' AND d.Has_AC = 0
GROUP BY r.Vehicle_Type
ORDER BY AC_Complaint_Cancellations DESC;

-- @id: H05
-- @group: H. Anomalies & fraud
-- @title: Large customer-vs-driver rating gaps (|gap| >= 1.5)
-- @note: 7.6% of completed rides (4,890) carry a rating gap of 1.5 stars or more - the pool to review for rating retaliation or disputes.
SELECT Booking_ID, Vehicle_Type, Driver_Ratings, Customer_Rating, Rating_Gap
FROM ola_rides
WHERE Is_Successful = 1 AND ABS(Rating_Gap) >= 1.5
ORDER BY ABS(Rating_Gap) DESC, Booking_ID
LIMIT 100;

-- @id: H06
-- @group: H. Anomalies & fraud
-- @title: Fare outliers - top 1% of completed fares
-- @note: The top percentile of fares starts at about INR 2,780. NTILE(100) is used because MySQL and SQLite have no portable PERCENTILE function.
WITH ranked AS (
    SELECT Booking_ID, Vehicle_Type, Ride_Distance, Booking_Value,
           NTILE(100) OVER (ORDER BY Booking_Value) AS Fare_Percentile
    FROM ola_rides
    WHERE Is_Successful = 1
)
SELECT Booking_ID, Vehicle_Type, Ride_Distance, Booking_Value
FROM ranked
WHERE Fare_Percentile = 100
ORDER BY Booking_Value DESC, Booking_ID
LIMIT 100;

-- @id: H07
-- @group: H. Anomalies & fraud
-- @title: Anomaly scorecard - one row per rule
-- @note: Combines the rules above into a single review queue size. Each row is a candidate for investigation, not proof of fraud.
SELECT 'Pickup equals drop' AS Rule, COUNT(*) AS Flagged_Bookings
FROM ola_rides WHERE Pickup_Location = Drop_Location
UNION ALL
SELECT 'Fare above INR 500 per km', COUNT(*)
FROM ola_rides WHERE Is_Successful = 1 AND Fare_Per_Km > 500
UNION ALL
SELECT 'Fare >= INR 1,500 on a <= 5 km ride', COUNT(*)
FROM ola_rides WHERE Is_Successful = 1 AND Booking_Value >= 1500 AND Ride_Distance <= 5
UNION ALL
SELECT 'AC complaint on a non-AC vehicle', COUNT(*)
FROM ola_rides r JOIN dim_vehicle d ON d.Vehicle_Type = r.Vehicle_Type
WHERE r.Canceled_Rides_by_Customer = 'AC is Not working' AND d.Has_AC = 0
UNION ALL
SELECT 'Rating gap of 1.5 or more', COUNT(*)
FROM ola_rides WHERE Is_Successful = 1 AND ABS(Rating_Gap) >= 1.5
UNION ALL
SELECT 'Duplicate Booking_ID', COUNT(*) - COUNT(DISTINCT Booking_ID)
FROM ola_rides;


-- #############################################################################
--  PART I - DATA QUALITY & VALIDATION
-- #############################################################################

-- @id: I01
-- @group: I. Data quality
-- @title: Row-count reconciliation against the source
-- @note: Must equal 103,024 rows, 63,967 + 18,434 + 10,499 + 10,124 by status, and 94,544 unique customers.
SELECT COUNT(*)                     AS Total_Rows,
       COUNT(DISTINCT Booking_ID)   AS Unique_Bookings,
       COUNT(DISTINCT Customer_ID)  AS Unique_Customers,
       MIN(Date)                    AS First_Date,
       MAX(Date)                    AS Last_Date
FROM ola_rides;

-- @id: I02
-- @group: I. Data quality
-- @title: Structural-null audit (NULLs exist only where they should)
-- @note: Ratings, payment, TAT and incomplete flags must be NULL on every failed booking and populated on every successful one. Any non-zero 'violations' column would signal a cleaning error.
SELECT Booking_Status,
       COUNT(*)                                                  AS Bookings,
       SUM(CASE WHEN Payment_Method  IS NULL THEN 1 ELSE 0 END)  AS Null_Payment,
       SUM(CASE WHEN Driver_Ratings  IS NULL THEN 1 ELSE 0 END)  AS Null_Driver_Rating,
       SUM(CASE WHEN Customer_Rating IS NULL THEN 1 ELSE 0 END)  AS Null_Customer_Rating,
       SUM(CASE WHEN V_TAT           IS NULL THEN 1 ELSE 0 END)  AS Null_V_TAT,
       SUM(CASE WHEN Ride_Distance = 0 THEN 1 ELSE 0 END)        AS Zero_Distance
FROM ola_rides
GROUP BY Booking_Status
ORDER BY Bookings DESC;

-- @id: I03
-- @group: I. Data quality
-- @title: Reason-code consistency (reasons must match the booking status)
-- @note: Every row must be 0: a customer reason only on 'Canceled by Customer', a driver reason only on 'Canceled by Driver', an incomplete reason only when Incomplete_Rides = 'Yes'.
SELECT SUM(CASE WHEN (Booking_Status = 'Canceled by Customer') <> (Canceled_Rides_by_Customer IS NOT NULL) THEN 1 ELSE 0 END) AS Customer_Reason_Mismatch,
       SUM(CASE WHEN (Booking_Status = 'Canceled by Driver')   <> (Canceled_Rides_by_Driver   IS NOT NULL) THEN 1 ELSE 0 END) AS Driver_Reason_Mismatch,
       SUM(CASE WHEN (Incomplete_Rides = 'Yes') <> (Incomplete_Rides_Reason IS NOT NULL) THEN 1 ELSE 0 END)                  AS Incomplete_Reason_Mismatch,
       SUM(CASE WHEN Driver_Ratings < 1 OR Driver_Ratings > 5 OR Customer_Rating < 1 OR Customer_Rating > 5 THEN 1 ELSE 0 END) AS Rating_Out_Of_Range
FROM ola_rides;
