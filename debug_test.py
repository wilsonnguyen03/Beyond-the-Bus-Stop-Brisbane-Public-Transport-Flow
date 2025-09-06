import streamlit as st
import geopandas as gpd
import os
import folium
from streamlit_folium import st_folium

st.set_page_config(layout="wide")
st.title("🧪 DEBUG TEST: Suburb Click + Direction + File Check")

# ----------------- Direction Selector -----------------
direction = st.radio("Select direction:", ["Inbound", "Outbound"])

# ----------------- Load Suburbs -----------------
suburbs_gdf = gpd.read_file(
    r"QSC_Extracted_Data_20250416_015956289270-10580/QSC_Extracted_Data_20250416_015956289270-10580/data.gdb",
    layer="Locality_Boundaries"
).to_crs(epsg=4326)

suburbs_gdf = suburbs_gdf[suburbs_gdf["adminareaname"].str.contains("BRISBANE CITY", case=False)]
suburbs_gdf["adminareaname"] = suburbs_gdf["adminareaname"].astype(str)

# ----------------- Convert to GeoJSON -----------------
geojson_data = suburbs_gdf[["adminareaname", "geometry"]].to_json()

# ----------------- Create Map -----------------
brisbane_center = [-27.4698, 153.0251]
m = folium.Map(location=brisbane_center, zoom_start=11, tiles="CartoDB positron")

folium.GeoJson(
    data=geojson_data,
    name="Brisbane Suburbs",
    tooltip=folium.GeoJsonTooltip(fields=["adminareaname"], aliases=["Suburb:"]),
    popup=folium.GeoJsonPopup(fields=["adminareaname"]),
    style_function=lambda x: {
        "fillColor": "#c8d5f3",
        "color": "black",
        "weight": 1,
        "fillOpacity": 0.3,
    },
    highlight_function=lambda x: {
        "fillColor": "yellow",
        "color": "black",
        "weight": 2,
        "fillOpacity": 0.6,
    }
).add_to(m)

# ----------------- Show Map -----------------
map_data = st_folium(m, width=800, height=600)

# ----------------- Handle Click -----------------
st.markdown("## Output")
popup_val = map_data.get("last_object_clicked_popup")
st.write("popup_val:", popup_val)

if popup_val:
    # ✅ Clean the popup value
    popup_clean = popup_val.replace("adminareaname", "").strip()
    cleaned = popup_clean.split(",")[0].strip().upper()
    st.write("Cleaned suburb name:", cleaned)

    # Generate expected filename
    filename = f"{cleaned.replace(' ', '_')}_{direction.lower()}.csv"
    st.write("Expected filename:", filename)

    file_path = os.path.join("output_data", filename)

    if os.path.exists(file_path):
        st.success(f"✅ Found matching file: {file_path}")
    else:
        st.error(f"❌ File not found: {file_path}")
else:
    st.info("Click a suburb polygon to test.")
