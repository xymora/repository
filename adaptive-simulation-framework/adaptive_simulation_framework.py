import numpy as np
import matplotlib.pyplot as plt

# Parámetros del entorno
n_states = 10
n_actions = 2
n_episodes = 1000
alpha = 0.1       # tasa de aprendizaje
gamma = 0.9       # factor de descuento
epsilon = 0.1     # política epsilon-greedy

# Inicializar matriz Q
Q = np.zeros((n_states, n_actions))

# Simulación del entorno
def get_next_state_reward(state, action):
    if action == 0:  # mover izquierda
        next_state = max(0, state - 1)
    else:            # mover derecha
        next_state = min(n_states - 1, state + 1)
    reward = 1 if next_state == n_states - 1 else 0
    return next_state, reward

# Ejecutar episodios de entrenamiento
rewards_per_episode = []
for episode in range(n_episodes):
    state = np.random.randint(0, n_states)
    total_reward = 0
    for _ in range(50):  # tiempo máximo por episodio
        if np.random.rand() < epsilon:
            action = np.random.randint(n_actions)
        else:
            action = np.argmax(Q[state])

        next_state, reward = get_next_state_reward(state, action)
        best_next = np.max(Q[next_state])
        Q[state, action] += alpha * (reward + gamma * best_next - Q[state, action])
        state = next_state
        total_reward += reward
        if reward == 1:
            break
    rewards_per_episode.append(total_reward)

# Guardar gráfico de resultados
plt.figure(figsize=(10, 5))
plt.plot(np.convolve(rewards_per_episode, np.ones(100)/100, mode='valid'))
plt.title("Reward per Episode (Moving Avg)")
plt.xlabel("Episode")
plt.ylabel("Reward")
plt.grid(True)
plt.tight_layout()
plt.savefig("adaptive_simulation_rewards.png")
plt.close()
