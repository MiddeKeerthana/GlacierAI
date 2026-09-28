import numpy as np


def ndsi_threshold(ndsi, threshold=0.4):
    """
    Convert NDSI into a binary snow mask.

    Pixels >= threshold become 1.
    Others become 0.
    """

    mask = np.where(ndsi >= threshold, 1, 0)

    return mask.astype(np.uint8)