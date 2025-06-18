import torch
import torch.nn as nn
import torch.optim as optim

# Simple dataset
data = torch.tensor([[0.1, 0.2], [0.2, 0.1], [0.9, 0.8], [0.8, 0.9]])
labels = torch.tensor([0, 0, 1, 1])

# Simple neural network
class Net(nn.Module):
    def __init__(self):
        super(Net, self).__init__()
        self.fc1 = nn.Linear(2, 3)
        self.fc2 = nn.Linear(3, 2)

    def forward(self, x):
        x = torch.relu(self.fc1(x))
        x = self.fc2(x)
        return x

net = Net()
criterion = nn.CrossEntropyLoss()
optimizer = optim.SGD(net.parameters(), lr=0.01)

import pobshell; pobshell.shell()
# Training loop
for epoch in range(100):
    optimizer.zero_grad()
    outputs = net(data)
    loss = criterion(outputs, labels)
    loss.backward()
    optimizer.step()

print("Training complete.")
