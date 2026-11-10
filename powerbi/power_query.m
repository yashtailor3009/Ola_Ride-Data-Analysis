// =============================================================================
//  OLA RIDE INSIGHTS - POWER QUERY (M)
//  Option A (recommended): load the already-cleaned dataset (fast, identical to SQL/Streamlit)
//  Option B: reproduce the cleaning in Power Query from the ORIGINAL workbook
//  Change the file paths, then paste each query into  Home > Get Data > Blank Query > Advanced Editor.
// =============================================================================

// ---------------- Option A: ola_rides (cleaned CSV, gzip) --------------------
let
    Source   = Csv.Document(Binary.Decompress(File.Contents("C:\OLA\ola_rides_clean.csv.gz"), Compression.GZip),
                            [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed    = Table.TransformColumnTypes(Promoted, {
        {"Date", type date}, {"Booking_Datetime", type datetime}, {"Ride_Hour", Int64.Type},
        {"Day_Of_Week_No", Int64.Type}, {"Is_Weekend", Int64.Type}, {"Is_Successful", Int64.Type},
        {"Is_Cancelled", Int64.Type}, {"Is_Same_Pickup_Drop", Int64.Type},
        {"V_TAT", type number}, {"C_TAT", type number}, {"Booking_Value", Int64.Type}, {"Ride_Distance", Int64.Type},
        {"Fare_Per_Km", type number}, {"Driver_Ratings", type number}, {"Customer_Rating", type number}, {"Rating_Gap", type number}
    }, "en-US")
in
    Typed


// ---------------- Option B: clean the ORIGINAL workbook (sheet "July") -------
let
    Source   = Excel.Workbook(File.Contents("C:\OLA\OLA_DataSet.xlsx"), null, true),
    July     = Source{[Item = "July", Kind = "Sheet"]}[Data],
    Promoted = Table.PromoteHeaders(July, [PromoteAllScalars = true]),
    // 1. keep only the 19 documented columns (drops the helper "Vehicle Images" column)
    Kept     = Table.SelectColumns(Promoted, {"Date", "Time", "Booking_ID", "Booking_Status", "Customer_ID", "Vehicle_Type",
               "Pickup_Location", "Drop_Location", "V_TAT", "C_TAT", "Canceled_Rides_by_Customer", "Canceled_Rides_by_Driver",
               "Incomplete_Rides", "Incomplete_Rides_Reason", "Booking_Value", "Payment_Method", "Ride_Distance",
               "Driver_Ratings", "Customer_Rating"}),
    // 2. the text 'null' -> a real null (structural nulls are kept, never imputed)
    NoNulls  = Table.ReplaceValue(Kept, "null", null, Replacer.ReplaceValue, Table.ColumnNames(Kept)),
    // 3. types
    Typed    = Table.TransformColumnTypes(NoNulls, {
        {"Date", type datetime}, {"V_TAT", type number}, {"C_TAT", type number}, {"Booking_Value", Int64.Type},
        {"Ride_Distance", Int64.Type}, {"Driver_Ratings", type number}, {"Customer_Rating", type number}}),
    // 4. derived features
    Hour     = Table.AddColumn(Typed, "Ride_Hour", each Time.Hour(DateTime.Time([Date])), Int64.Type),
    DayName  = Table.AddColumn(Hour, "Day_Name", each Date.DayOfWeekName(DateTime.Date([Date]), "en-US"), type text),
    Success  = Table.AddColumn(DayName, "Is_Successful", each if [Booking_Status] = "Success" then 1 else 0, Int64.Type),
    FailType = Table.AddColumn(Success, "Failure_Type", each
                  if [Booking_Status] = "Canceled by Customer" then "Customer cancellation"
                  else if [Booking_Status] = "Canceled by Driver" then "Driver cancellation"
                  else if [Booking_Status] = "Driver Not Found" then "No driver found" else null, type text),
    SamePD   = Table.AddColumn(FailType, "Is_Same_Pickup_Drop", each if [Pickup_Location] = [Drop_Location] then 1 else 0, Int64.Type),
    FarePKm  = Table.AddColumn(SamePD, "Fare_Per_Km", each if [Is_Successful] = 1 and [Ride_Distance] > 0
                  then [Booking_Value] / [Ride_Distance] else null, type number),
    DateOnly = Table.TransformColumns(FarePKm, {{"Date", each DateTime.Date(_), type date}})
in
    DateOnly
