import numpy as np
import matplotlib.pyplot as plt

# Parámetros del entorno simulado
np.random.seed(42)
grid_size = 20
n_ticks = 50

# Matriz: 0 = libre, 1 = fuego, 2 = agua/espuma activada
grid = np.zeros((grid_size, grid_size), dtype=int)
ignition_points = [(5, 5), (14, 10)]
for x, y in ignition_points:
    grid[x, y] = 1

# Zonas perimetrales con aspersores de niebla/espuma (círculo externo)
def is_perimeter(x, y, margin=2):
    return (x < margin or x >= grid_size - margin or y < margin or y >= grid_size - margin)

# Simulación de propagación del fuego y respuesta automática
snapshots = [grid.copy()]
for tick in range(n_ticks):
    new_grid = grid.copy()
    for x in range(grid_size):
        for y in range(grid_size):
            if grid[x, y] == 1:  # fuego activo
                for dx in [-1, 0, 1]:
                    for dy in [-1, 0, 1]:
                        nx, ny = x + dx, y + dy
                        if 0 <= nx < grid_size and 0 <= ny < grid_size and grid[nx, ny] == 0:
                            new_grid[nx, ny] = 1 if not is_perimeter(nx, ny) else 2
    grid = new_grid
    snapshots.append(grid.copy())

# Visualización final
fig, axes = plt.subplots(5, 5, figsize=(12, 12))
for i, ax in enumerate(axes.flat):
    if i < len(snapshots):
        ax.imshow(snapshots[i], cmap="hot", interpolation="nearest")
        ax.set_title(f"Tick {i}")
        ax.axis("off")
plt.tight_layout()
plt.savefig("fire_suppression_simulation.png")
plt.close()
