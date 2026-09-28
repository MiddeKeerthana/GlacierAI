from torch.utils.data import DataLoader

from backend.utils.dataset import GlacierDataset

dataset = GlacierDataset(
    "datasets/training/train/images",
    "datasets/training/train/masks"
)

print("Dataset size:", len(dataset))

loader = DataLoader(
    dataset,
    batch_size=4,
    shuffle=True
)

images, masks = next(iter(loader))

print("Images:", images.shape)
print("Masks :", masks.shape)