import torch

from backend.models.unet import UNet

model = UNet()

x = torch.randn(1, 3, 512, 512)

y = model(x)

print("Input :", x.shape)
print("Output:", y.shape)