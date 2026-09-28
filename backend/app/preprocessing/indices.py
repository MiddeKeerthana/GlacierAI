import numpy as np


def compute_ndsi(green, swir):

    green = green.astype(np.float32)

    swir = swir.astype(np.float32)

    return (green - swir) / (green + swir + 1e-6)