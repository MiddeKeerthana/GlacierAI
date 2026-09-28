from pathlib import Path
import geopandas as gpd

PROJECT_ROOT = Path(__file__).resolve().parents[2]

rgi_file = PROJECT_ROOT / "datasets" / "processed" / "global_rgi.gpkg"

rgi = gpd.read_file(rgi_file)

print("Total glaciers:", len(rgi))

print("\nGeometry types:")
print(rgi.geometry.geom_type.value_counts())

print("\nFirst 10 geometry types:")
print(rgi.geometry.geom_type.head(10))

print("\nValid geometries:", rgi.is_valid.sum())
print("Invalid geometries:", (~rgi.is_valid).sum())

print("\nFirst geometry:")
print(rgi.geometry.iloc[0])

print("\nBounds:")
print(rgi.geometry.iloc[0].bounds)