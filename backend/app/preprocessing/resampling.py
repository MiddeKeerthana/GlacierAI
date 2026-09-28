import rasterio
from rasterio.enums import Resampling


def read_band_resampled(band_path, target_shape):

    with rasterio.open(band_path) as src:

        image = src.read(
            1,
            out_shape=target_shape,
            resampling=Resampling.bilinear,
        )

    return image