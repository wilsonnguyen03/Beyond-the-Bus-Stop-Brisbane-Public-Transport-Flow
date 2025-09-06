import streamlit as st
import geopandas as gpd
import pandas as pd
import os
import folium
from streamlit_folium import st_folium
from folium.plugins import PolyLineTextPath
import matplotlib

st.set_page_config(layout="wide")
st.title("Brisbane Suburb Transport Trip Explorer (Multi-Select)")

direction = st.radio("Select direction", ["Inbound", "Outbound"])

# Load Brisbane suburb boundaries
suburbs_gdf = gpd.read_file(
    r"QSC_Extracted_Data_20250416_015956289270-10580/QSC_Extracted_Data_20250416_015956289270-10580/data.gdb",
    layer="Locality_Boundaries"
).to_crs(epsg=4326)

suburbs_gdf = suburbs_gdf[suburbs_gdf["adminareaname"].str.contains("BRISBANE CITY", case=False)]
suburbs_gdf["adminareaname"] = suburbs_gdf["adminareaname"].astype(str)
geojson_data = suburbs_gdf[["adminareaname", "geometry"]].to_json()

# Track selected suburbs
if "selected_suburbs" not in st.session_state:
    st.session_state.selected_suburbs = set()

# Layout
col1, col2 = st.columns(2)

# ----------------- LEFT MAP -----------------
with col1:
    st.markdown("### 1. Click suburbs to toggle selection")

    brisbane_center = [-27.4698, 153.0251]
    m1 = folium.Map(location=brisbane_center, zoom_start=11, tiles="CartoDB positron")

    def style_suburb(feature):
        name = feature["properties"]["adminareaname"]
        selected = any(name.upper().startswith(s) for s in st.session_state.selected_suburbs)
        return {
            "fillColor": "#f94144" if selected else "#c8d5f3",
            "color": "black",
            "weight": 2 if selected else 1,
            "fillOpacity": 0.6 if selected else 0.3,
        }

    folium.GeoJson(
        data=geojson_data,
        name="Brisbane Suburbs",
        tooltip=folium.GeoJsonTooltip(fields=["adminareaname"], aliases=["Suburb:"]),
        popup=folium.GeoJsonPopup(fields=["adminareaname"]),
        style_function=style_suburb,
        highlight_function=lambda x: {
            "fillColor": "yellow",
            "color": "black",
            "weight": 2,
            "fillOpacity": 0.5,
        }
    ).add_to(m1)

    map_data = st_folium(m1, width=500, height=600)
    popup_val = map_data.get("last_object_clicked_popup")

    if popup_val:
        suburb_name = popup_val.replace("adminareaname", "").strip().split(",")[0].strip().upper()
        if suburb_name in st.session_state.selected_suburbs:
            st.session_state.selected_suburbs.remove(suburb_name)
        else:
            st.session_state.selected_suburbs.add(suburb_name)

# ----------------- RIGHT MAP -----------------
with col2:
    st.markdown("### 2. Trip Map")

    trip_map = folium.Map(location=[-27.4698, 153.0251], zoom_start=11, tiles="CartoDB positron")
    trip_data_found = False
    all_trips = []

    if st.session_state.selected_suburbs:
        st.subheader(f"Top 1% {direction} trips from: " + ", ".join(st.session_state.selected_suburbs))

        for suburb in st.session_state.selected_suburbs:
            filename = f"{suburb.replace(' ', '_')}_{direction.lower()}.csv"
            file_path = os.path.join("output_top1", filename)

            if not os.path.exists(file_path):
                st.warning(f"⚠️ Missing file: {filename}")
                continue

            df = pd.read_csv(file_path)
            if df.empty or "quantity" not in df.columns:
                continue

            all_trips.append(df)
            trip_data_found = True

            # Highlight suburb on trip map
            selected_gdf = suburbs_gdf[suburbs_gdf["adminareaname"].str.startswith(suburb)]
            folium.GeoJson(
                selected_gdf.__geo_interface__,
                style_function=lambda x: {
                    "fillColor": "#f94144",
                    "color": "black",
                    "weight": 2,
                    "fillOpacity": 0.3
                }
            ).add_to(trip_map)

        if all_trips:
            df_all = pd.concat(all_trips, ignore_index=True)

            min_q = df_all["quantity"].min()
            max_q = df_all["quantity"].max()
            df_all["normalized_quantity"] = (df_all["quantity"] - min_q) / (max_q - min_q + 1e-6)
            df_all["color"] = df_all["normalized_quantity"].apply(
                lambda q: matplotlib.colors.to_hex(matplotlib.cm.Blues(q))
            )

            for _, row in df_all.iterrows():
                coords = [
                    [row["origin_stop_lat"], row["origin_stop_lon"]],
                    [row["destination_stop_lat"], row["destination_stop_lon"]],
                ]
                line = folium.PolyLine(
                    locations=coords,
                    color=row["color"],
                    weight=2 + row["normalized_quantity"] * 6,
                    opacity=0.9,
                    tooltip=f"{row['quantity']} to {row['destination_stop_name']}"
                ).add_to(trip_map)

                PolyLineTextPath(
                    line,
                    "➤",
                    repeat=True,
                    offset=7,
                    attributes={"fill": row["color"], "font-weight": "bold", "font-size": "16"}
                ).add_to(trip_map)
        else:
            st.warning("No trips to display.")
    else:
        st.info("Click suburbs on the left to display trips.")

    # Always show map
    st_folium(trip_map, width=1000, height=800)


    # Show trip tuples after map
    if trip_data_found and all_trips:
        st.markdown("### 🧾 Top 1% Trip Tuples")
        st.dataframe(df_all[[
            "origin_stop_name", "destination_stop_name", "route", "quantity"
        ]].sort_values("quantity", ascending=False).reset_index(drop=True))
