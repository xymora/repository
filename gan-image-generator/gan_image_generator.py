
import torch
import torchvision
import torchvision.transforms as transforms
from torch import nn, optim
from torchvision.utils import save_image
import os

transform = transforms.Compose([
    transforms.ToTensor(),
    transforms.Normalize((0.5,), (0.5,))
])

dataset = torchvision.datasets.FashionMNIST(root='./data', train=True, download=True, transform=transform)
dataloader = torch.utils.data.DataLoader(dataset, batch_size=128, shuffle=True)

class Generator(nn.Module):
    def __init__(self):
        super().__init__()
        self.main = nn.Sequential(
            nn.ConvTranspose2d(100, 64, 4, 1, 0, bias=False),
            nn.BatchNorm2d(64),
            nn.ReLU(True),
            nn.ConvTranspose2d(64, 1, 4, 2, 1, bias=False),
            nn.Tanh()
        )

    def forward(self, input):
        return self.main(input)

class Discriminator(nn.Module):
    def __init__(self):
        super().__init__()
        self.main = nn.Sequential(
            nn.Conv2d(1, 64, 4, 2, 1, bias=False),
            nn.LeakyReLU(0.2, inplace=True),
            nn.Flatten(),
            nn.Linear(64*14*14, 1),
            nn.Sigmoid()
        )

    def forward(self, input):
        return self.main(input)

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
G = Generator().to(device)
D = Discriminator().to(device)

loss = nn.BCELoss()
optimizerD = optim.Adam(D.parameters(), lr=0.0002)
optimizerG = optim.Adam(G.parameters(), lr=0.0002)

real_label = 1.
fake_label = 0.

fixed_noise = torch.randn(64, 100, 1, 1, device=device)

for epoch in range(1):
    for i, (data, _) in enumerate(dataloader):
        D.zero_grad()
        real = data.to(device)
        label = torch.full((real.size(0),), real_label, dtype=torch.float, device=device)
        output = D(real).view(-1)
        errD_real = loss(output, label)
        errD_real.backward()

        noise = torch.randn(real.size(0), 100, 1, 1, device=device)
        fake = G(noise)
        label.fill_(fake_label)
        output = D(fake.detach()).view(-1)
        errD_fake = loss(output, label)
        errD_fake.backward()
        optimizerD.step()

        G.zero_grad()
        label.fill_(real_label)
        output = D(fake).view(-1)
        errG = loss(output, label)
        errG.backward()
        optimizerG.step()

    with torch.no_grad():
        fake = G(fixed_noise).detach().cpu()
    save_image(fake, 'fashion_mnist_samples.png', normalize=True)
