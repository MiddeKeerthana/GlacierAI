from pathlib import Path

import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from tqdm import tqdm

from backend.models.unet import UNet
from backend.utils.dataset import GlacierDataset

# ==========================================================
# Device
# ==========================================================

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

print(f"Using: {DEVICE}")

# ==========================================================
# Dataset
# ==========================================================

train_dataset = GlacierDataset(
    "datasets/training/train/images",
    "datasets/training/train/masks",
)

val_dataset = GlacierDataset(
    "datasets/training/val/images",
    "datasets/training/val/masks",
)

train_loader = DataLoader(
    train_dataset,
    batch_size=4,
    shuffle=True,
    num_workers=0,
    pin_memory=(DEVICE.type == "cuda"),
)

val_loader = DataLoader(
    val_dataset,
    batch_size=4,
    shuffle=False,
    num_workers=0,
    pin_memory=(DEVICE.type == "cuda"),
)

print(f"Training Images   : {len(train_dataset)}")
print(f"Validation Images : {len(val_dataset)}")

# ==========================================================
# Model
# ==========================================================

model = UNet().to(DEVICE)

criterion = nn.BCEWithLogitsLoss()

optimizer = torch.optim.Adam(
    model.parameters(),
    lr=1e-4,
)

# ==========================================================
# Checkpoints
# ==========================================================

CHECKPOINT_DIR = Path("checkpoints")
CHECKPOINT_DIR.mkdir(exist_ok=True)

best_loss = float("inf")

# ==========================================================
# Training
# ==========================================================

EPOCHS = 20

for epoch in range(EPOCHS):

    model.train()

    running_loss = 0.0

    progress = tqdm(
        train_loader,
        desc=f"Epoch {epoch+1}/{EPOCHS}",
        leave=True,
    )

    for images, masks in progress:

        images = images.to(DEVICE)
        masks = masks.to(DEVICE)

        optimizer.zero_grad()

        outputs = model(images)

        loss = criterion(outputs, masks)

        loss.backward()

        optimizer.step()

        running_loss += loss.item()

        progress.set_postfix(loss=f"{loss.item():.4f}")

    train_loss = running_loss / len(train_loader)

    # ======================================================
    # Validation
    # ======================================================

    model.eval()

    val_loss = 0.0

    with torch.no_grad():

        for images, masks in val_loader:

            images = images.to(DEVICE)
            masks = masks.to(DEVICE)

            outputs = model(images)

            loss = criterion(outputs, masks)

            val_loss += loss.item()

    val_loss /= len(val_loader)

    print("\n" + "=" * 45)
    print(f"Epoch {epoch+1}/{EPOCHS} Completed")
    print("=" * 45)
    print(f"Train Loss : {train_loss:.4f}")
    print(f"Val Loss   : {val_loss:.4f}")

    if val_loss < best_loss:

        best_loss = val_loss

        torch.save(
            {
                "epoch": epoch + 1,
                "model_state_dict": model.state_dict(),
                "optimizer_state_dict": optimizer.state_dict(),
                "val_loss": val_loss,
            },
            CHECKPOINT_DIR / "best_unet.pth",
        )

        print("✅ Best model saved")

print("\n🎉 Training Complete!")