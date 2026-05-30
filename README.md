# Wumpus World Game

An interactive, visually-driven simulation of the classic Wumpus World AI problem. Built in Python with Pygame, featuring player-controlled navigation, dynamic hazards, sound effects, animations, and full mobile touch support.

---

## Gameplay Objective

- Find the gold hidden somewhere on the grid
- Return safely to the starting cell (bottom-left, green)
- Avoid pits and the Wumpus — both will end your run instantly

---

## Features

### Core Gameplay
- Procedurally generated grid across **6 levels** (6×6 up to 10×10)
- Moving Wumpus — relocates every 3 player turns, preferring unexplored cells
- One arrow per game — use it wisely (must be adjacent to the Wumpus to kill)
- Scout mode — reveals adjacent cells for 1 second (10s cooldown)
- Left-click / tap any cell to mark it with a danger warning `!`

### Visuals
- Fog of war — unexplored cells are greyed out, explored cells light up
- Distinct start cell (green), agent cell highlight (blue-white)
- Stench icon (bottom-left of cell) and Breeze icon (bottom-right) — never overlap
- Gold pickup animation — scales up and fades out on collection
- Screen shake when the Wumpus moves
- Pulsing gold/red border glow on the victory/game over screen

### Sound Effects
| Event | Sound |
|---|---|
| Player moves | Footstep |
| Arrow fired & hits | Arrow + monster death |
| Arrow fired & misses | Arrow whoosh |
| Wumpus moves | Monster footsteps |
| Player eaten by Wumpus | Monster scream |
| Player falls in pit | Falling scream |
| Gold collected | Coin sound |

### Mobile Support
- On-screen D-pad and SHOOT / SCOUT buttons appear automatically on touch devices
- Cell size scales down dynamically on smaller screens so large grids never clutter the display
- Touch controls are hidden on desktop — keyboard only

### AI / Pathfinding
- **A\* Search** (Manhattan heuristic) validates map solvability after each pit placement
- Optimal move count calculated at game start and compared against your score on the victory screen
- Efficiency percentage shown at the end

---

## Controls

| Input | Action |
|---|---|
| Arrow keys / D-pad | Move agent |
| Space / SHOOT | Fire arrow |
| R / SCOUT | Activate scout mode |
| Left-click / Tap | Mark / unmark cell |

---

## How to Run

```bash
# 1. Clone the repo
git clone https://github.com/SharathShankarRathakrishnan/WumpusWorldGame.git
cd WumpusWorldGame

# 2. Install dependencies
pip install pygame numpy

# 3. Run
python wumpus.py
```

---

## Project Structure

```
WumpusWorldGame/
├── wumpus.py              # Main game file
├── sounds/                # Sound effects (.wav / .mp3 / .ogg)
├── *.png / *.jpg          # Game images and UI assets
├── VT323-Regular.ttf      # Arcade font
└── README.md
```

---

## AI Concepts Demonstrated

- **A\* Search** — pathfinding and solvability validation
- **Agent perception** — stench (Wumpus nearby) and breeze (pit nearby)
- **State-space reasoning** — tracking explored vs unexplored cells
- **Optimal path estimation** — efficiency scoring against A\* baseline
