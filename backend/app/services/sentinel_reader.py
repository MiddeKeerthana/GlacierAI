from pathlib import Path
import rasterio


def find_safe_folder(sentinel_root, tile=None):
    """
    Find a SAFE folder.
    """

    sentinel_root = Path(sentinel_root)

    safe_dirs = list(sentinel_root.rglob("*.SAFE"))

    if not safe_dirs:
        raise FileNotFoundError("No SAFE folders found.")

    if tile:

        for folder in safe_dirs:

            if tile in folder.name:
                return folder

        raise FileNotFoundError(f"{tile} SAFE folder not found.")

    return safe_dirs[0]


def find_band(safe_folder, band):

    safe_folder = Path(safe_folder)

    matches = list(safe_folder.rglob(f"*{band}*.jp2"))

    if not matches:
        raise FileNotFoundError(f"{band} band not found.")

    return str(matches[0])


def get_band_path(safe_folder, band):
    return find_band(safe_folder, band)


def read_band(safe_folder, band):

    band_path = find_band(safe_folder, band)

    with rasterio.open(band_path) as src:
        return src.read(1)


def get_band_metadata(safe_folder, band):

    band_path = find_band(safe_folder, band)

    with rasterio.open(band_path) as src:

        return {
            "band": Path(band_path).name,
            "width": src.width,
            "height": src.height,
            "crs": str(src.crs),
            "driver": src.driver,
            "dtype": str(src.dtypes[0]),
        }