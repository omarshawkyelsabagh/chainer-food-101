import argparse
import logging
import random

import matplotlib
matplotlib.use('Agg')  # to prevent software hang

import numpy as np
try:
    import cupy as xp
except ImportError:
    import numpy as xp

import chainer
import chainer.links as L
from chainer.datasets import split_dataset_random
from chainer.iterators import MultiprocessIterator, MultithreadIterator, SerialIterator
from chainer import training
from chainer.training import extensions
from chainer.training.triggers import MinValueTrigger

from dataset import FoodDataset
from network import MobilenetV2

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def train(args=None):
    dataset = FoodDataset(train=True)
    train_dataset, valid_dataset = split_dataset_random(
        dataset, int(0.9 * len(dataset)), seed=args.seed)
    train_iter = MultiprocessIterator(
        train_dataset, args.batch_size)
    val_iter = MultiprocessIterator(
        valid_dataset, args.batch_size, repeat=False, shuffle=False)

    model = MobilenetV2(num_classes=101, depth_multiplier=1.0)
    model = L.Classifier(model)
    if args.device >= 0:
        chainer.backends.cuda.get_device_from_id(args.device).use()
        model.to_gpu()

    optimizer = chainer.optimizers.SGD()
    optimizer.setup(model)

    train, test = chainer.datasets.get_mnist()
    updater = training.updaters.StandardUpdater(
        train_iter, optimizer, device=args.device)
    trainer = training.Trainer(
        updater, (args.epoch, 'epoch'), out=args.destination)

    snapshot_interval = (1, 'epoch')

    trainer.extend(extensions.Evaluator(val_iter, model, device=args.device),
                   trigger=snapshot_interval)
    trainer.extend(extensions.ProgressBar())
    trainer.extend(extensions.LogReport(trigger=snapshot_interval,
                                        log_name='log.json'))
    trainer.extend(extensions.snapshot(
        filename='snapshot_epoch_{.updater.epoch}.npz'), trigger=snapshot_interval)
    trainer.extend(extensions.snapshot_object(
        model, 'model_epoch_{.updater.epoch}.npz'), trigger=snapshot_interval)

    if extensions.PlotReport.available():
        trainer.extend(extensions.PlotReport(['main/loss', 'validation/main/loss'], 'epoch', file_name='loss.png'),
                       trigger=snapshot_interval)
        trainer.extend(extensions.PlotReport(['main/accuracy', 'validation/main/accuracy'], 'epoch', file_name='accuracy.png'),
                       trigger=snapshot_interval)

    if args.resume:
        chainer.serializers.load_npz(args.resume, trainer)
    trainer.run()


def set_random_seed(seed):
    random.seed(seed)
    np.random.seed(seed)
    xp.random.seed(seed)


def parse_argument():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=12345)
    parser.add_argument("--device", type=int, default=0)
    parser.add_argument("--multiplier", type=float, default=1.0)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--destination", type=str, default="logs")
    parser.add_argument("--resume", type=str, default="")
    parser.add_argument("--epoch", type=int, default=100)
    args = parser.parse_args()
    return args


def main():
    args = parse_argument()
    set_random_seed(args.seed)
    train(args)
if __name__ == '__main__':
    main()