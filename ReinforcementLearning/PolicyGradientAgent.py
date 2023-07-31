import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from CrewPairingEnv import CrewPairingEnv


#Policy를 파라미터화 하기 위한 신경망. 하이퍼파라미터 튜닝 작업 필요
#input: current state(all flight-> pairing * max flight 형태로 제공)
#output: probability of each action
class PolicyNetwork(nn.Module): 
    def __init__(self, n_inputs, n_outputs):
        super(PolicyNetwork, self).__init__()
        self.network = nn.Sequential(
            nn.Linear(n_inputs, 256),
            nn.ReLU(),
            nn.Linear(256, n_outputs),
            nn.Softmax(dim=-1)
        )

    def forward(self, x):
        return self.network(x)

class PolicyGradientAgent:
    def __init__(self, env, lr=0.01, gamma=0.99):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.env = env
        self.gamma = gamma

        n_pairings = len(env.initial_pairing_set)
        max_flights = env.max_flights
        n_inputs = n_pairings * max_flights
        n_outputs = n_pairings * max_flights * n_pairings * max_flights

        self.policy_net = PolicyNetwork(n_inputs, n_outputs)
        self.optimizer = optim.Adam(self.policy_net.parameters(), lr=lr) #using Adam for optimizing

        self.saved_log_probs = []
        self.rewards = []

    def select_action(self, state):
        state = torch.from_numpy(state).float().unsqueeze(0).to(self.device) #state를 Pytorch텐서로 변환, 배치 차원 추가 후 GPU로 이동
        action_probs = self.policy_net(state) #신경망에서 각 action의 확률 가져옴
        action_probs = action_probs.squeeze().cpu().detach().numpy() # 배치 제거, 텐서 cpu로 이동, 계산 그래프 분리, numpy로 변환
        selected_action = np.random.choice(len(action_probs), p=action_probs) #주어진 확률을 바탕으로 무작위 action 선택
        self.saved_log_probs.append(torch.log(action_probs[selected_action])) #선택 action 로그 확률 저장
        return selected_action

    def update(self):
        R = 0
        policy_loss = []
        returns = []
        for r in self.rewards[::-1]:
            R = r + self.gamma * R
            returns.insert(0, R)
        returns = torch.tensor(returns)
        returns = (returns - returns.mean()) / (returns.std() + 1e-9)
        for log_prob, R in zip(self.saved_log_probs, returns):
            policy_loss.append(-log_prob * R)
        self.optimizer.zero_grad()
        policy_loss = torch.cat(policy_loss).sum()
        policy_loss.backward()
        self.optimizer.step()
        del self.rewards[:]
        del self.saved_log_probs[:]

# Usage
initial_pairing_set = ...  # 받아올거임
cost_threshold = ...  # 설정해야됨.
env = CrewPairingEnv(initial_pairing_set, cost_threshold)
agent = PolicyGradientAgent(env)

for i_episode in range(1000):
    state = env.reset()
    for t in range(100):  
        action = agent.select_action(state)
        next_state, reward, done, _ = env.step(action)
        agent.rewards.append(reward)
        if done:
            break
        state = next_state
    agent.update()