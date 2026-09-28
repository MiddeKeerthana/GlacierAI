from pathlib import Path

import cv2
import torch
from torch.utils.data import Dataset


class GlacierDataset(Dataset):

    def __init__(self, image_dir, mask_dir):

        self.image_dir = Path(image_dir)
        self.mask_dir = Path(mask_dir)

        self.images = sorted(self.image_dir.glob("*.png"))

    def __len__(self):
        return len(self.images)

    def __getitem__(self, idx):

        image_path = self.images[idx]

        mask_path = self.mask_dir / image_path.name

        # -----------------------------
        # Read RGB image
        # -----------------------------

        image = cv2.imread(str(image_path))

        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        image = image.astype("float32") / 255.0

        # -----------------------------
        # Read mask
        # -----------------------------

        mask = cv2.imread(
            str(mask_path),
            cv2.IMREAD_GRAYSCALE
        )

        mask = (mask > 127).astype("float32")

        # -----------------------------
        # HWC -> CHW
        # -----------------------------

        image = torch.tensor(image).permute(2, 0, 1)

        mask = torch.tensor(mask).unsqueeze(0)

        return image, mask