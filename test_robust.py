import os 
os.environ['CUDA_DEVICE_ORDER'] = 'PCI_BUS_ID'
os.environ['CUDA_VISIBLE_DEVICES'] = '1'

import torch
import torch.nn as nn
import torchvision.transforms as transforms
import torch.nn.functional as F
from torch.autograd.gradcheck import zero_gradients
from torch.autograd import Variable
import numpy as np
import time
import argparse
from torchsummary import summary

from utils.mnist_models import cnn_3l, cnn_3l_large
from utils.cifar10_models import WideResNet
from utils.test_utils import test, robust_test
from utils.data_utils import load_dataset, load_dataset_custom
from utils.io_utils import init_dirs


if __name__ == '__main__':
    torch.random.manual_seed(7)

    parser = argparse.ArgumentParser()
    # Data args
    parser.add_argument('--dataset_in', type=str, default='MNIST')
    parser.add_argument('--n_classes', type=int, default=10)
    parser.add_argument('--num_samples', type=int, default=None)
    
    # Model args
    parser.add_argument('--model', type=str, default='cnn_3l', choices=['wrn','cnn_3l', 'cnn_3l_large'])
    parser.add_argument('--conv_expand', type=int, default=1)
    parser.add_argument('--fc_expand', type=int, default=1)
    parser.add_argument('--depth', type=int, default=28)
    parser.add_argument('--width', type=int, default=10)
    parser.add_argument('--batch_size', type=int, default=128) 
    parser.add_argument('--test_batch_size', type=int, default=128)
    # parser.add_argument('--learning_rate', type=float, default=0.1)
    # parser.add_argument('--weight_decay', type=float, default=2e-4)

    # Defense args
    parser.add_argument('--is_adv', dest='is_adv', action='store_true')
    parser.add_argument('--attack', type=str, default='PGD_l2')
    parser.add_argument('--epsilon', type=float, default=8.0)
    parser.add_argument('--attack_iter', type=int, default=10)
    parser.add_argument('--eps_step', type=float, default=2.0)
    parser.add_argument('--is_dropping', dest='dropping', action='store_true')
    parser.add_argument('--rand_init', dest='rand_init', action='store_true')

    # Attack args
    parser.add_argument('--new_attack', type=str, default='PGD_l2')
    parser.add_argument('--new_epsilon', type=float, default=2.0)
    parser.add_argument('--new_attack_iter', type=int, default=20)
    parser.add_argument('--new_eps_step', type=float, default=0.25)
    parser.add_argument('--targeted', dest='targeted', action='store_true')
    parser.add_argument('--clip_min', type=float, default=0)
    parser.add_argument('--clip_max', type=float, default=1.0)
    parser.add_argument('--new_rand_init', dest='new_rand_init', action='store_true')

    # IO args
    parser.add_argument('--last_epoch', type=int, default=0)
    parser.add_argument('--checkpoint_path', type=str, default='trained_models')
    parser.add_argument('--is_viz', dest='viz', action='store_true')

    if torch.cuda.is_available():
        print('CUDA enabled')
    else:
        raise ValueError('Needs a working GPU!')

    args = parser.parse_args()
    model_dir_name, log_dir_name, figure_dir_name = init_dirs(args)
    print('Loading %s' % model_dir_name)

    # Setting to False to load all training data
    args.dropping = False
    
    if args.n_classes != 10:
        loader_train, loader_test, data_details = load_dataset_custom(args, data_dir='data')
    else:
        loader_train, loader_test, data_details = load_dataset(args, data_dir='data')

    if args.dataset_in == 'MNIST':
        if 'large' in args.model:
            net = cnn_3l_large(args.n_classes)
        else:
            net = cnn_3l(args.n_classes, args.conv_expand, args.fc_expand)
    elif args.dataset_in == 'CIFAR-10':
        if 'wrn' in args.model:
            net = WideResNet(depth=args.depth, num_classes=args.n_classes, widen_factor=args.width)
    
    if 'linf' in args.attack:
        args.epsilon /= 255.
        args.eps_step /= 255.

    if torch.cuda.device_count() > 1:
        print("Using multiple GPUs")
    net = nn.DataParallel(net)

    args.batch_size = args.batch_size * torch.cuda.device_count()
    print("Using batch size of {}".format(args.batch_size))

    net.cuda()

   # if args.dataset_in == 'MNIST':
       # summary(net, (1,28,28))

    criterion = nn.CrossEntropyLoss()  

    training = False
    net.eval()
    ckpt_path = 'checkpoint_' + str(args.last_epoch)
    print(model_dir_name)
    net.load_state_dict(torch.load(model_dir_name + ckpt_path))
    test(net, loader_train, figure_dir_name)
    robust_test(net, loader_train, args, figure_dir_name, n_batches=10)
    # test(net, loader_test, figure_dir_name)
    # robust_test(net, loader_test, args, figure_dir_name, n_batches=10)
