import numpy as np


def normalize_band(image: np.ndarray) -> np.ndarray:
    """
    Normalize a Sentinel-2 band to the range [0, 1].

    Parameters:
        image (numpy.ndarray): uint16 Sentinel-2 band

    Returns:
        numpy.ndarray: float32 normalized band
    """

    image = image.astype(np.float32)

    valid_pixels = image > 0

    if np.any(valid_pixels):
        min_val = image[valid_pixels].min()
        max_val = image[valid_pixels].max()

        image[valid_pixels] = (
            image[valid_pixels] - min_val
        ) / (max_val - min_val)

    return image