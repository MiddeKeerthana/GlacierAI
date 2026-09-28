import cv2
import numpy as np


def clean_mask(mask):

    kernel = np.ones((3,3), np.uint8)

    cleaned = cv2.morphologyEx(
        mask,
        cv2.MORPH_OPEN,
        kernel,
        iterations=1
    )

    cleaned = cv2.morphologyEx(
        cleaned,
        cv2.MORPH_CLOSE,
        kernel,
        iterations=2
    )

    return cleaned