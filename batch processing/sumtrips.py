import polars as pl
import os

# Load your full dataset
df = pl.read_parquet("cleaned_trip_data.parquet")

# Ensure output directory exists
os.makedirs("output_top1", exist_ok=True)

# Get all unique origin suburbs from Brisbane City
suburbs = (
    df
    .filter(pl.col("origin_suburb").str.to_uppercase().str.contains("BRISBANE CITY"))
    .select("origin_suburb")
    .unique()
    .to_series()
    .to_list()
)

for suburb in suburbs:
    suburb_clean = suburb.split(",")[0].strip().upper().replace(" ", "_")

    # Base filter: trips from this suburb
    base_df = df.filter(
        pl.col("origin_suburb").str.strip_chars().str.to_uppercase() == suburb.strip().upper()
    )

    if base_df.is_empty():
        continue

    # Inbound: going TO Brisbane City
    inbound_df = base_df.filter(
        pl.col("destination_suburb").str.to_uppercase().str.contains("BRISBANE CITY")
    )

    # Outbound: leaving FROM Brisbane City
    outbound_df = base_df.filter(
        pl.col("origin_suburb").str.to_uppercase().str.contains("BRISBANE CITY")
    )

    # Other: not matching either inbound or outbound (anti-join on origin+destination)
    known_pairs = pl.concat([inbound_df, outbound_df])
    other_df = base_df.join(
        known_pairs.select(["origin_stop", "destination_stop"]).unique(),
        on=["origin_stop", "destination_stop"],
        how="anti"
    )

    def process_and_save(df_subset, file_suffix):
        if df_subset.is_empty():
            return

        grouped_df = df_subset.group_by([
            "origin_stop", "origin_stop_type",
            "destination_stop", "destination_stop_type"
        ]).agg([
            pl.first("origin_suburb").alias("origin_suburb"),
            pl.first("destination_suburb").alias("destination_suburb"),
            pl.first("operator").alias("operator"),
            pl.first("route").alias("route"),
            pl.first("direction").alias("direction"),
            pl.first("ticket_type").alias("ticket_type"),
            pl.first("origin_stop_name").alias("origin_stop_name"),
            pl.first("origin_stop_lat").alias("origin_stop_lat"),
            pl.first("origin_stop_lon").alias("origin_stop_lon"),
            pl.first("destination_stop_name").alias("destination_stop_name"),
            pl.first("destination_stop_lat").alias("destination_stop_lat"),
            pl.first("destination_stop_lon").alias("destination_stop_lon"),
            pl.sum("quantity").alias("quantity"),
            pl.first("distance").alias("distance")
        ])

        if grouped_df.is_empty():
            return

        # Sort and get top 0.5% by quantity
        grouped_df = grouped_df.sort("distance")
        df_pd = grouped_df.to_pandas()
        threshold = df_pd["quantity"].quantile(0.99)
        top_trips = df_pd[df_pd["quantity"] >= threshold]

        output_name = f"{suburb_clean}_{file_suffix}.csv"
        output_path = os.path.join("output_top1", output_name)
        top_trips.to_csv(output_path, index=False)
        print(f"Saved: {output_name}")

    # Save each category
    process_and_save(inbound_df, "inbound")
    process_and_save(outbound_df, "outbound")

    # Save ambiguous trips into both
    if not other_df.is_empty():
        process_and_save(other_df, "inbound")
        process_and_save(other_df, "outbound")
