# -*- coding: utf-8 -*-
"""Soona_mixmatch_implementation.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1WR-YGAKVseTa3gz8-sQQ9_O9Z6ibKI5d
"""

import torch 
import numpy as np
import imgaug.augmenters as iaa

def augmentation(images):
    seq = iaa.Sequential([
        iaa.Crop(px=(0, 16)),
        iaa.Fliplr(0.5),
        iaa.GaussianBlur(sigma=(0, 3.0)),
        iaa.Flipud(0.2),
    ])
    def augment():
        return seq.augment(images.transpose(0, 2, 3, 1)).transpose(0, 2, 3, 1)
    return augment

import torchvision.transforms as transforms

mean=[0.485, 0.456, 0.406]
std=[0.229, 0.224, 0.225]
normalize = transforms.Normalize(mean=mean, std=std)
train_transforms = transforms.Compose([transforms.RandomRotation(30),
                                       transforms.RandomResizedCrop(400),
                                       transforms.RandomHorizontalFlip(),
                                       transforms.ToTensor(),normalize])

def label_guessing(model, u_aug, k):
  return sum(map(lambda i: model(i), u_aug)) / K

def Sharpening(p,T):
  return p**(1/T) / p**(1/T).sum(axis=1, keepdims=True)

def MixUp(x1,p1,x2,p2,alpha):
  lamda = np.random.beta(alpha, alpha) 
  lamda_h = np.maximum(lamda, 1-lamda)
  x = lamda_h * x1 + (1 - lamda_h) * x2
  p = lamda_h * p1 + (1 - lamda_h) * p2
  return x,p

def mixmatch(model, x, p, u,augmentation, T=0.5, K=2, alpha=0.75):
  batch_size = x.shape[0]
  xb = augmentation(x)
  ub = [augmentation(u) for _ in range(K)]
  xb = x
  ub = [u for _ in range(K)]
  qb_h = label_guessing(model, ub, K)
  qb = Sharpening(qb_h,T)
  U_h = np.concatenate(ub, axis=0)
  U_hq = np.concatenate([qb for _ in range(K)], axis=0)
  indices = np.random.shuffle(np.arange(len(xb) + len(U_h)))
  W_ux = np.concatenate([U_h, xb], axis=0)[indices]
  W_qp = np.concatenate([qb, p], axis=0)[indices]
  X_, p = mixup(xb, p, W_ux[:len(xb)], W_qp[:len(xb)], alpha)
  U_, q = mixup(U_h, U_hq, W_ux[len(xb):], W_qp[len(xb):], alpha)
  return X_, U_, p, q

def ssLoss( p, pred_x, q, pred_u, lamda_u=100):
  l_x= torch.nn.CrossEntropyLoss(p,pred_x) 
  l_u= torch.nn.MSELoss(q,pred_u)
  return l_x + lamda_u*l_u

import torchvision.models as models
from torch.utils.data import Dataset, DataLoader
import torchvision
from sklearn.model_selection import train_test_split

wide_resnet_model=models.wide_resnet50_2(pretrained=False)

transform = transforms.Compose( 
    [transforms.ToTensor(),
     transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5))])

trainset = torchvision.datasets.CIFAR10(root='./data',
                                        download=True, transform=train_transforms)

# X_train = np.array(trainset.data)
# y_train = np.array(trainset.targets)
X_train =trainset.data
y_train =trainset.targets

# Train set / Validation set split
X_train, X_val, y_train, y_val = train_test_split(X_train, y_train, test_size=0.3, random_state=1,
                                                          shuffle=True, stratify=y_train)

# Train unsupervised / Train supervised split
X_train, X_u_train, y_train, y_u_train = train_test_split(X_train, y_train, test_size=0.7, random_state=1,
                                                          shuffle=True, stratify=y_train)

data = zip(X_train, X_u_train, y_train)

optimizer = torch.optim.Adam(wide_resnet_model.parameters(), weight_decay=0.0004 ) 
device = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')

def to_torch(*args, device='cuda'):
    convert_fn = lambda x: torch.from_numpy(x).to(device)
    return list(map(convert_fn, args))

def train(model ,data,optimizer,num_epochs):
  model.train()
  model.to(device)
  for epoch in range(1):
    for x,u,p in data:
      X, U, p, q = mixmatch(model,x,p,u,augmentation)
      print(X.shape, U.shape)
      X, U, p, q = to_torch(x, u, p, q, device=device)
      X_pred= model(X)
      U_pred = model(U)
      loss = ssLoss(p,X_pred, q, U_pred)
      print(epoch,loss.item())
      loss.backward()
      optimizer.step()

train(wide_resnet_model,data,optimizer,100)

