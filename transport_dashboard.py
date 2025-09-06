import streamlit as st
import geopandas as gpd
import pandas as pd
import os
import folium
from streamlit_folium import st_folium
from folium.plugins import PolyLineTextPath

# ----------------- Setup -----------------
st.set_page_config(layout="wide")
st.title("Brisbane Suburb Transport Trip Explorer")

# Direction selector
direction = st.radio("Select direction", ["Inbound", "Outbound"])

# ----------------- Load suburb boundaries -----------------
suburbs_gdf = gpd.read_file(
    r"QSC_Extracted_Data_20250416_015956289270-10580/QSC_Extracted_Data_20250416_015956289270-10580/data.gdb",
    layer="Locality_Boundaries"
).to_crs(epsg=4326)

suburbs_gdf = suburbs_gdf[suburbs_gdf["adminareaname"].str.contains("BRISBANE CITY", case=False)]
suburbs_gdf["suburb_clean"] = suburbs_gdf["adminareaname"].str.replace(", BRISBANE CITY", "", case=False).str.strip().str.upper()

# ----------------- Center Map -----------------
suburbs_projected = suburbs_gdf.to_crs(epsg=3857)
center = suburbs_projected.geometry.unary_union.centroid.coords[0][::-1]  # lat/lon

# ----------------- Map -----------------
m = folium.Map(location=center, zoom_start=11, tiles=None)
folium.TileLayer(
    tiles="https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png",
    attr="CartoDB Positron No Labels",
    control=False
).add_to(m)

# Session state to track selection
if "selected_suburb" not in st.session_state:
    st.session_state.selected_suburb = None

# ----------------- Suburb Styling -----------------
def style_suburb(row):
    if st.session_state.selected_suburb == row["suburb_clean"]:
        return {
            "fillColor": "#f94144",  # Red for selected
            "color": "black",
            "weight": 2,
            "fillOpacity": 0.7,
        }
    return {
        "fillColor": "#c8d5f3",
        "color": "black",
        "weight": 1,
        "fillOpacity": 0.3,
    }

# ----------------- Add polygons -----------------
for _, row in suburbs_gdf.iterrows():
    folium.GeoJson(
        data=row["geometry"],
        tooltip=row["adminareaname"],
        popup=folium.Popup(row["adminareaname"], max_width=250),
        style_function=lambda x, row=row: style_suburb(row),
        highlight_function=lambda x: {
            "fillColor": "yellow",
            "color": "black",
            "weight": 2,
            "fillOpacity": 0.5,
        }
    ).add_to(m)

# ----------------- Capture Map Click -----------------
map_data = st_folium(m, width=1000, height=600)
popup_val = map_data.get("last_object_clicked_popup")

if popup_val:
    suburb_clean = popup_val.split(",")[0].strip().upper()
    st.session_state.selected_suburb = suburb_clean

# ----------------- If suburb is selected -----------------
if st.session_state.selected_suburb:
    selected_suburb = st.session_state.selected_suburb
    st.subheader(f"Top 1% {direction} trips from {selected_suburb.replace('_', ' ').title()}")

    filename = f"output_data/{selected_suburb}_{direction.lower()}.csv"

    if os.path.exists(filename):
        df = pd.read_csv(filename)

        if df.empty:
            st.warning("No trips found for this suburb and direction.")
        else:
            st.success(f"Loaded {len(df)} trips.")
            trip_map = folium.Map(
                location=[df["origin_stop_lat"].iloc[0], df["origin_stop_lon"].iloc[0]],
                zoom_start=13,
                tiles=None
            )
            folium.TileLayer(
                tiles="https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png",
                attr="CartoDB Positron No Labels",
                control=False
            ).add_to(trip_map)

            # Normalize quantity for line thickness
            min_q = df["quantity"].min()
            max_q = df["quantity"].max()
            df["normalized_quantity"] = (df["quantity"] - min_q) / (max_q - min_q + 1e-6)

            for _, row in df.iterrows():
                coords = [
                    [row["origin_stop_lat"], row["origin_stop_lon"]],
                    [row["destination_stop_lat"], row["destination_stop_lon"]],
                ]
                line = folium.PolyLine(
                    locations=coords,
                    color="blue",
                    weight=2 + row["normalized_quantity"] * 6,
                    opacity=0.8,
                    tooltip=f"{row['quantity']} to {row['destination_suburb']}"
                ).add_to(trip_map)

                PolyLineTextPath(
                    line,
                    "➤",
                    repeat=True,
                    offset=7,
                    attributes={"fill": "blue", "font-weight": "bold", "font-size": "16"}
                ).add_to(trip_map)

            st_folium(trip_map, width=1000, height=600)

    else:
        st.warning("No preprocessed trip data for this suburb and direction.")
else:
    st.info("🖱️ Click a suburb to load its top trips.")
