import numpy as np
import matplotlib.pyplot as plt
import os

def generate_simple_map(width=20, height=20, output_path="data/simple_map.png"):
    """Generate a simple grid-based map with random obstacles."""
    # 0: Floor, 1: Wall
    grid = np.random.choice([0, 1], size=(height, width), p=[0.8, 0.2])
    
    plt.figure(figsize=(10, 10))
    plt.imshow(grid, cmap='binary')
    plt.title("Dungeon Map Draft")
    plt.axis('off')
    
    # Ensure data directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    plt.savefig(output_path)
    plt.close()
    print(f"Map saved to {output_path}")

if __name__ == "__main__":
    generate_simple_map()
