from magical_drones.models.base_gan.discriminator import BaseDiscriminator
from torch import nn, Tensor
import torch


class Discriminator(BaseDiscriminator):
    def __init__(
        self, channels: int = 3, num_features: int = 64, depth: int = 4, **kwargs
    ):
        super().__init__(channels)
        self.num_features = num_features
        self.depth = depth
        self.features = [num_features * 2**i for i in range(depth)]
        self.model = self._construct_model()

    def _construct_model(self):
        initial_layer = nn.Sequential(
            nn.Conv2d(
                self.channels,
                self.features[0],
                kernel_size=4,
                stride=2,
                padding=1,
                padding_mode="reflect",
            ),
            nn.LeakyReLU(0.2),
        )

        layers = []
        in_channels = self.features[0]

        for feature in self.features[1:]:
            layers.append(
                ConvBlock(
                    in_channels,
                    feature,
                    stride=1 if feature == self.features[-1] else 2,
                ),
            )
            in_channels = feature

        layers.append(
            nn.Conv2d(
                in_channels,
                1,
                kernel_size=4,
                stride=1,
                padding=1,
                padding_mode="reflect",
            )
        )

        model = nn.Sequential(initial_layer, *layers)

        return model

    def forward(self, x: Tensor) -> Tensor:
        return torch.sigmoid(self.model(x))


class ConvBlock(nn.Module):
    def __init__(
        self,
        in_channels: int,
        out_channels: int,
        stride: int,
    ):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv2d(
                in_channels,
                out_channels,
                kernel_size=4,
                stride=stride,
                padding=1,
                bias=True,
                padding_mode="reflect",
            ),
            nn.InstanceNorm2d(out_channels),
            nn.LeakyReLU(0.2),
        )

    def forward(self, x):
        return self.conv(x)
