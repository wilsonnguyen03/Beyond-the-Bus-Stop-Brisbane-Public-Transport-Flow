import polars as pl
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

# Step 1: Load raw dataset
df = pl.read_csv(
    "brisbane_data_distance.csv/brisbane_data_distance.csv",
    ignore_errors=True,
    null_values=["", "NA", "N310"],
    schema_overrides={
        "origin_stop_lat": pl.Float64,
        "origin_stop_lon": pl.Float64,
        "destination_stop_lat": pl.Float64,
        "destination_stop_lon": pl.Float64,
        "quantity": pl.Int64,
        "distance": pl.Float64,
        "route": pl.Utf8  # allow nulls (e.g., "", NA, N310) in route column
    }
)

# Step 2: Drop unnecessary columns
df = df.drop("time").drop("month")

# Step 3: Load suburb boundaries
suburbs_gdf = gpd.read_file(
    r"QSC_Extracted_Data_20250416_015956289270-10580/QSC_Extracted_Data_20250416_015956289270-10580/data.gdb",
    layer="Locality_Boundaries"
)
suburbs_gdf = suburbs_gdf.to_crs(epsg=4326)

# Step 4: Tag origin and destination suburbs in chunks
chunk_size = 250_000
origin_chunks = []
destination_chunks = []

for i in range(0, df.height, chunk_size):
    chunk_df = df.slice(i, chunk_size).to_pandas()

    # Origin suburb tagging
    chunk_df["geometry"] = chunk_df.apply(
        lambda row: Point(row["origin_stop_lon"], row["origin_stop_lat"]), axis=1
    )
    origin_gdf = gpd.GeoDataFrame(chunk_df, geometry="geometry", crs="EPSG:4326")
    origin_joined = gpd.sjoin(origin_gdf, suburbs_gdf, how="left", predicate="within")
    origin_chunk = origin_joined[["adminareaname"]].rename(columns={"adminareaname": "origin_suburb"})
    origin_chunks.append(origin_chunk)

    # Destination suburb tagging
    chunk_df["geometry"] = chunk_df.apply(
        lambda row: Point(row["destination_stop_lon"], row["destination_stop_lat"]), axis=1
    )
    destination_gdf = gpd.GeoDataFrame(chunk_df, geometry="geometry", crs="EPSG:4326")
    destination_joined = gpd.sjoin(destination_gdf, suburbs_gdf, how="left", predicate="within")
    destination_chunk = destination_joined[["adminareaname"]].rename(columns={"adminareaname": "destination_suburb"})
    destination_chunks.append(destination_chunk)

# Step 5: Attach suburb columns to the main DataFrame
origin_suburbs = pd.concat(origin_chunks, ignore_index=True)
destination_suburbs = pd.concat(destination_chunks, ignore_index=True)

df_pd = df.to_pandas()
df_pd["origin_suburb"] = origin_suburbs["origin_suburb"].values
df_pd["destination_suburb"] = destination_suburbs["destination_suburb"].values

# Step 6: Convert back to Polars and write to Parquet
df_final = pl.from_pandas(df_pd)
df_final.write_parquet("cleaned_trip_data.parquet")

print("Parquet file written successfully: cleaned_trip_data.parquet")

