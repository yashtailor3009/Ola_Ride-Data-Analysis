"""
ola.dictionary
==============
Data dictionary for the cleaned table: (column, type, source, meaning).
Used by the app's About page, the README and the PDF report.
"""
DATA_DICTIONARY = [
    # --- original columns ---------------------------------------------------
    ("Booking_ID", "text", "source", "Unique booking identifier (no duplicates)."),
    ("Customer_ID", "text", "source", "Customer identifier; 94,544 distinct customers."),
    ("Date", "date", "source (split)", "Calendar date of the booking (the workbook's Date also carried the clock time)."),
    ("Time", "text HH:MM:SS", "source", "Clock time of the booking."),
    ("Booking_Status", "text", "source", "Success | Canceled by Customer | Canceled by Driver | Driver Not Found."),
    ("Vehicle_Type", "text", "source", "Auto, Bike, eBike, Mini, Prime Plus, Prime Sedan, Prime SUV."),
    ("Pickup_Location / Drop_Location", "text", "source", "One of 50 Bengaluru areas."),
    ("V_TAT / C_TAT", "number", "source", "Vehicle / customer turn-around time (units undocumented). Completed rides only."),
    ("Canceled_Rides_by_Customer", "text", "source", "Customer's cancellation reason (only on 'Canceled by Customer')."),
    ("Canceled_Rides_by_Driver", "text", "source", "Driver's cancellation reason (only on 'Canceled by Driver')."),
    ("Incomplete_Rides / _Reason", "Yes/No, text", "source", "Whether a completed booking ended early, and why. Completed rides only."),
    ("Booking_Value", "INR", "source", "Fare. Quoted fare for failed bookings; revenue only when Success."),
    ("Payment_Method", "text", "source", "Cash | UPI | Credit Card | Debit Card. Completed rides only."),
    ("Ride_Distance", "km", "source", "Distance driven; 0 for every non-completed booking."),
    ("Driver_Ratings / Customer_Rating", "1-5", "source", "Ratings; completed rides only; observed range 3.0-5.0."),
    # --- derived columns ----------------------------------------------------
    ("Booking_Datetime", "timestamp", "derived", "Full timestamp (Date + Time)."),
    ("Ride_Hour", "0-23", "derived", "Hour of the booking."),
    ("Day_Name / Day_Of_Week_No", "text / 1-7", "derived", "Weekday name; 1 = Monday ... 7 = Sunday."),
    ("Is_Weekend", "0/1", "derived", "1 for Saturday and Sunday."),
    ("Time_Band", "text", "derived", "Night 00-05, Morning 06-11, Afternoon 12-17, Evening 18-23 (equal 6-hour windows)."),
    ("Is_Successful / Is_Cancelled", "0/1", "derived", "Outcome flags (Is_Cancelled excludes 'Driver Not Found')."),
    ("Failure_Type", "text", "derived", "Customer cancellation | Driver cancellation | No driver found."),
    ("Failure_Reason", "text", "derived", "Unified reason column across the three failure types."),
    ("Is_Same_Pickup_Drop", "0/1", "derived", "Pickup equals drop - anomaly rule."),
    ("Distance_Band", "text", "derived", "1-5, 6-10, 11-20, 21-30, 31-40, 41-50 km; 'Not completed' otherwise."),
    ("Fare_Per_Km", "INR/km", "derived", "Booking_Value / Ride_Distance on completed rides."),
    ("Rating_Gap", "number", "derived", "Driver rating minus customer rating."),
]
