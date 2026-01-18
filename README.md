# Wumpus-World
An interactive implementation of the classic Wumpus World problem, demonstrating search algorithms, logical reasoning, and agent-based decision-making. Built in Python with a visual interface using Pygame.
The agent navigates a hazardous grid to collect gold while avoiding pits and a moving Wumpus.

## Key Features
- Procedurally generated grid (6×6 to 10×10)
- Dynamic hazards: pits, stench, breeze
- Moving Wumpus (moves every 3 player turns)
- A* pathfinding for:
- Map solvability validation
- Optimal move calculation
- Scout mode to reveal adjacent cells (cooldown-based)
- Arrow shooting to eliminate the Wumpus
- Multiple difficulty levels

## AI Concepts Used
- A* Search (Manhattan heuristic)
- State-space reasoning
- Agent perception (stench, breeze)
- Optimal path estimation

## Gameplay Objective
- Collect the gold
- Return safely to the starting position
- Avoid pits and the Wumpus
