from pytorch_lightning import LightningDataModule
from torch.utils.data import Dataset, DataLoader
from datasets import load_dataset
from torchvision.transforms import v2
import torch
from omegaconf import DictConfig


class MagMapDataSet(Dataset):
    def __init__(self, data, transform=None, sat_transform=None):
        self.data = data
        self.transform = transform if transform is not None else self._to_tensor()
        self.sat_transform = (
            sat_transform if sat_transform is not None else v2.Identity()
        )

    def _to_tensor(self):
        return v2.Compose(
            [
                v2.ToImage(),
                v2.ToDtype(torch.float32, scale=True),
                v2.Normalize(mean=[0.5, 0.5, 0.5], std=[0.5, 0.5, 0.5]),
            ]
        )

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        sample = self.data[idx]
        try:
            sat_image, map_image = (
                sample["sat_image"].convert("RGB"),
                sample["map_image"].convert("RGB"),
            )
            sat_image = self.sat_transform(
                sat_image
            )  # transform performed only on sat image (color jitter etc.)
            sat_image, map_image = self.transform(sat_image, map_image)
        except Exception as e:
            raise ValueError(f"Error processing sample {idx}: {e}")
        return sat_image, map_image


class MagMapV1(LightningDataModule):
    def __init__(self, cfg: DictConfig):
        super().__init__()
        self.cfg = cfg
        self.data_link = cfg.data_link
        self.data_files = cfg.get("data_files")
        self.data_dir = cfg.get("data_dir", "./data")
        self.split_for_upload = cfg.get("split_for_upload", [80, 10, 10, "%"])
        self.batch_size = cfg.batch_size
        self.num_workers = cfg.get("num_workers", 4)
        self.prefetch_factor = cfg.get("prefetch_factor", 2)

        self.train_transform = make_tfms(**cfg.train_transforms)
        self.valid_transform = make_tfms(**cfg.valid_transforms)
        self.test_transform = make_tfms(**cfg.test_transforms)

    def setup(self, stage: str = None):
        data_dict = load_dataset(
            self.data_link,
            data_files=self.data_files,
            cache_dir=self.data_dir,
        )
        data = data_dict["train"]

        split_train, split_val, split_test, unit = self.split_for_upload
        total_len = len(data)

        if unit == "%":
            train_len = int(split_train / 100 * total_len)
            val_len = int(split_val / 100 * total_len)
        else:
            train_len = split_train
            val_len = split_val

        test_len = total_len - train_len - val_len
        assert train_len + val_len + test_len == total_len, "Invalid split"

        self.train_dataset = MagMapDataSet(
            data.select(range(0, train_len)),
            transform=self.train_transform,
            sat_transform=sat_tfms,
        )
        self.val_dataset = MagMapDataSet(
            data.select(range(train_len, train_len + val_len)),
            transform=self.valid_transform,
        )
        self.test_dataset = MagMapDataSet(
            data.select(range(train_len + val_len, total_len)),
            transform=self.test_transform,
        )

    def train_dataloader(self):
        return DataLoader(
            self.train_dataset,
            batch_size=self.batch_size,
            num_workers=self.num_workers,
            prefetch_factor=self.prefetch_factor,
            shuffle=True,
            pin_memory=True,
        )

    def val_dataloader(self):
        return DataLoader(
            self.val_dataset,
            batch_size=self.batch_size,
            num_workers=self.num_workers,
            prefetch_factor=self.prefetch_factor,
            pin_memory=True,
        )

    def test_dataloader(self):
        return DataLoader(
            self.test_dataset,
            batch_size=self.batch_size,
            num_workers=self.num_workers,
            prefetch_factor=self.prefetch_factor,
            pin_memory=True,
        )


def make_tfms(
    size: int = 256,
    degrees: int = 0,
    translate: tuple[float] | None = None,
    flip_p: float = 0.0,
    scale: tuple[float] | None = None,
    shear: tuple[float] | None = None,
    channel_shuffle: bool = False,
):
    tfms = [
        v2.ToImage(),
        v2.Resize(size=size),
        v2.ToDtype(torch.float32, scale=True),
        v2.Normalize(mean=[0.5, 0.5, 0.5], std=[0.5, 0.5, 0.5]),
    ]
    if degrees or translate or scale or shear:
        tfms.append(
            v2.RandomAffine(
                degrees=degrees, translate=translate, scale=scale, shear=shear
            )
        )
    if flip_p > 0:
        tfms.append(v2.RandomHorizontalFlip(flip_p))
    if channel_shuffle:
        tfms.append(v2.RandomChannelPermutation())
    return v2.Compose(tfms)


sat_tfms = v2.Compose(
    [
        v2.ColorJitter(
            brightness=(0.5, 1.5), contrast=(0.5, 1.5), saturation=(0.5, 1.5)
        ),
        v2.RandomAdjustSharpness(1.5, p=0.5),
    ]
)
