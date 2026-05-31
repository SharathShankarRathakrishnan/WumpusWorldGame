import pygame
import sys
import os
import math
import random # For generating Wumpus, pits and gold.
import heapq # Provides priority queue functions for A* pathfinding algorithm
import time # For cooldown timer in scout mode
import asyncio # Required by pygbag for web builds
import sys
IS_WEB = sys.platform in ('emscripten', 'wasm32')  # True when running in browser via pygbag

# Base directory: folder where wumpus.py lives, so images are always found
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def load_sound(filename):
    """Load a sound file from the sounds subfolder, return None silently if missing."""
    path = os.path.join(BASE_DIR, 'sounds', filename)
    try:
        return pygame.mixer.Sound(path)
    except Exception as e:
        print(f"Could not load sound {path}: {e}")
        return None

def change_speed(sound, speed):
    """Return a new Sound played back at the given speed multiplier (requires numpy).
    Skipped on web builds — numpy import hangs the browser."""
    if IS_WEB:
        return sound  # skip on web: importing numpy blocks the browser runtime
    try:
        np = __import__('numpy')  # indirect import so pygbag's static packager doesn't try to bundle numpy
        samples = pygame.sndarray.array(sound)
        indices = np.arange(0, len(samples), speed).astype(int)
        indices = indices[indices < len(samples)]
        new_samples = samples[indices]
        return pygame.sndarray.make_sound(new_samples)
    except Exception as e:
        print(f"change_speed failed ({e}), using original sound.")
        return sound

# Sound globals — loaded inside main() after pygame.mixer.init()
snd_footstep = snd_gold_collected = snd_arrow_kill = snd_arrow_miss = None
snd_monster_footstep = snd_monster_scream = snd_falling_scream = None

def play(sound):
    """Play a sound safely — does nothing if sound failed to load."""
    if sound:
        sound.play()

# Constants
BASE_GRID_SIZE = 6  # Starting grid size of 6x6
MAX_GRID_SIZE = 10   # Maximum grid size of 10x10
CELL_SIZE = 80 # Size of each cell inside the grid
MARGIN = 45 # Space between the grid and window edges
WIDTH = MAX_GRID_SIZE * CELL_SIZE + 2 * MARGIN  # Use max size for window
HEIGHT = MAX_GRID_SIZE * CELL_SIZE + 2 * MARGIN + 80  # Extra space for buttons
WHITE = (255, 255, 255)
OFF_WHITE = (245, 245, 240)  # Off-white background color
BLACK = (0, 0, 0)
GRAY = (200, 200, 200)
RED = (255, 0, 0)
BLUE = (0, 0, 255)
GOLD = (255, 215, 0)
DARK_GOLD = (184, 134, 11)  # Dark gold for collected message
BUTTON_COLOR = (100, 200, 100)
BUTTON_HOVER = (100, 230, 100) # Highlights the button when cursor hovers over
CONTINUE_COLOR = (200, 150, 0)
CONTINUE_HOVER = (230, 180, 0) # Highlights the button when cursor hovers over
SCOUT_COLOR = (255, 255, 0, 150)  # Yellow with transparency for scout mode
RULES_BUTTON_COLOR = (100, 150, 200)  # Blue color for the rules button background
RULES_BUTTON_HOVER = (130, 180, 230)  # Lighter blue when mouse hovers over rules button
RULES_BG_COLOR = (50, 50, 50, 230)  # Dark semi-transparent background for rules modal overlay

# Medieval/Fantasy UI Colors
STONE_DARK = (60, 58, 55)  # Dark stone for unexplored cells
STONE_LIGHT = (95, 92, 88)  # Lighter stone for explored cells
STONE_BORDER = (40, 38, 35)  # Stone border color
PARCHMENT = (235, 222, 195)  # Parchment background for rules
PARCHMENT_BORDER = (180, 160, 130)  # Parchment border/dark edge
WOOD_DARK = (90, 65, 45)  # Dark wood for buttons
WOOD_LIGHT = (130, 95, 65)  # Lighter wood for button hover
WOOD_BORDER = (60, 45, 30)  # Wood border color
GOLD_GLOW = (255, 215, 0, 100)  # Gold shimmer effect

# Rules text to display on startup and when rules button is clicked
RULES_TEXT = [
    "WUMPUS WORLD - RULES",  # Title line for the rules screen
    "",  # Empty line for spacing
    "OBJECTIVE: Find the gold and return to the start position",  # Main goal of the game
    "",  # Empty line for spacing
    "DANGERS:",  # Section header for dangers
    "- Avoid the Wumpus (monster) - you will be eaten if you enter its cell",  # Warning about Wumpus
    "- Avoid pits - you will fall in if you enter a pit cell",  # Warning about pits
    "",  # Empty line for spacing
    "PERCEPTIONS:",  # Section header for perception cues
    "- Stench = Wumpus is in an adjacent cell",  # Stench meaning
    "- Breeze = Pit is in an adjacent cell",  # Breeze meaning
    "- Perceptions only appear in cells you have explored",  # Exploration requirement
    "",  # Empty line for spacing
    "WUMPUS BEHAVIOR:",  # Section header for Wumpus AI
    "- The Wumpus moves every 3 turns you take",  # Wumpus movement frequency
    "- It prefers to move to unexplored areas",  # Wumpus movement preference
    "- The screen shakes when the Wumpus moves - stay alert!",  # Screen shake hint
    "",  # Empty line for spacing
    "CONTROLS:",  # Section header for controls
    "- Arrow keys / D-pad: Move your agent up/down/left/right",
    "- SPACE / SHOOT button: Shoot arrow at the Wumpus",
    "- R / SCOUT button: Activate scout mode (reveals adjacent cells for 1 second)",
    "- Left-click / tap cell: Mark/unmark cells with danger warning (!)",
    "",  # Empty line for spacing
    "SCOUT MODE:",  # Section header for scout ability
    "- 10 second cooldown between uses",  # Cooldown duration
    "- Timer pauses when viewing these rules",  # Timer pause behavior
    "",  # Empty line for spacing
    "Click anywhere or press any key to continue..."  # Dismiss instructions
]

# Image size configurations
IMAGE_SIZES = {
    'agent': (30, 45),
    'gold': (60, 40),
    'wumpus': (50, 50),
    'pit': (50, 40),
    'stench': (30, 70),
    'breeze': (75, 30)
}

# Display, clock, font globals — initialised inside main()
screen = None
clock = None
VT323_FONT = VT323_FONT_SMALL = VT323_FONT_LARGE = VT323_FONT_TITLE = None

def load_image(image_name, default_color=None, target_size=None):
    image_path = os.path.join(BASE_DIR, image_name)
    try:
        original_img = pygame.image.load(image_path).convert_alpha() # Optimizes images for transparency
        
        if target_size:
            return pygame.transform.smoothscale(original_img, target_size) 
        else:
            img_type = image_name.split('.')[0]
            if img_type in IMAGE_SIZES:
                return pygame.transform.smoothscale(original_img, IMAGE_SIZES[img_type]) # Resizes the image smoothly to the target dimensions
            # If the image is not found in IMAGE_SIZES
            max_size = CELL_SIZE - 20 # Makes sure and image without pre-defined size fits in the cell.
            width, height = original_img.get_size()
            aspect_ratio = width / height
            
            if width > height: # Determines if the image is landscape or portrait
                new_width = max_size
                new_height = int(max_size / aspect_ratio)
            else:
                new_height = max_size
                new_width = int(max_size * aspect_ratio)
            
            return pygame.transform.smoothscale(original_img, (new_width, new_height)) # Final scaled image with preserved aspect ratio 
    except Exception as e:
        print(f"Error loading {image_path}: {e}")
        if target_size:
            surf = pygame.Surface(target_size, pygame.SRCALPHA) # Creates a blank image with transparency
        else:
            img_type = image_name.split('.')[0]
            size = IMAGE_SIZES.get(img_type, (CELL_SIZE-20, CELL_SIZE-20))
            surf = pygame.Surface(size, pygame.SRCALPHA)
        if default_color:
            if len(default_color) == 3:
                default_color = default_color + (155,)
            pygame.draw.rect(surf, default_color, surf.get_rect())
        return surf

# Animation helper functions
def get_animation_time():
    """Get current time in milliseconds for animations"""
    return pygame.time.get_ticks()

def create_stone_texture(width, height, base_color, dark_color, light_color):
    """Create a procedural stone texture surface"""
    surf = pygame.Surface((width, height))
    surf.fill(base_color)
    # Add subtle noise/variation
    for _ in range(20):
        x = random.randint(0, width - 2)
        y = random.randint(0, height - 2)
        size = random.randint(2, 6)
        color = random.choice([dark_color, light_color])
        pygame.draw.rect(surf, color, (x, y, size, size))
    return surf

def draw_stone_button(surface, rect, color, border_color, hover=False, pressed=False):
    """Draw a stone slab style button with 3D effect"""
    # Base stone color
    base_color = color if not hover else (min(255, color[0] + 20), min(255, color[1] + 20), min(255, color[2] + 20))
    
    # Draw main button body
    pygame.draw.rect(surface, base_color, rect, border_radius=3)
    
    # Draw beveled edges for 3D stone effect
    lighter = (min(255, base_color[0] + 30), min(255, base_color[1] + 25), min(255, base_color[2] + 20))
    darker = (max(0, base_color[0] - 30), max(0, base_color[1] - 25), max(0, base_color[2] - 20))
    
    # Top and left (lighter - raised look)
    pygame.draw.line(surface, lighter, (rect.left + 2, rect.top + 2), (rect.right - 3, rect.top + 2), 2)
    pygame.draw.line(surface, lighter, (rect.left + 2, rect.top + 2), (rect.left + 2, rect.bottom - 3), 2)
    
    # Bottom and right (darker - shadow)
    pygame.draw.line(surface, darker, (rect.left + 3, rect.bottom - 2), (rect.right - 2, rect.bottom - 2), 2)
    pygame.draw.line(surface, darker, (rect.right - 2, rect.top + 3), (rect.right - 2, rect.bottom - 3), 2)
    
    # Border
    pygame.draw.rect(surface, border_color, rect, 2, border_radius=3)

def create_parchment_texture(width, height):
    """Create a parchment/paper texture for rules screen"""
    surf = pygame.Surface((width, height))
    # Base parchment color
    surf.fill(PARCHMENT)
    
    # Add subtle aging/staining
    for _ in range(50):
        x = random.randint(0, width - 1)
        y = random.randint(0, height - 1)
        size = random.randint(1, 3)
        # Random slight variations in color
        variation = random.choice([5, -5, 3, -3])
        color = (
            max(0, min(255, PARCHMENT[0] + variation)),
            max(0, min(255, PARCHMENT[1] + variation)),
            max(0, min(255, PARCHMENT[2] + variation))
        )
        pygame.draw.rect(surf, color, (x, y, size, size))
    
    return surf

def get_bounce_offset(cell_pos, animation_start_time, bounce_duration=500):
    """Calculate bounce animation offset for a newly marked cell"""
    elapsed = get_animation_time() - animation_start_time
    if elapsed > bounce_duration:
        return 0
    # Simple ease-out bounce: starts at -10, settles to 0
    progress = elapsed / bounce_duration
    bounce = -10 * (1 - progress) * (1 - progress)
    return int(bounce)

def get_shimmer_alpha(animation_time, period=2000):
    """Get pulsing alpha value for gold shimmer effect (0-100 range)"""
    elapsed = animation_time % period
    # Sine wave for smooth pulse: 0 -> 100 -> 0
    alpha = int(50 + 50 * math.sin(2 * math.pi * elapsed / period))
    return alpha

# Image globals — loaded inside main() after display is ready
agent_img = gold_img = wumpus_img = pit_img = stench_img = breeze_img = None
game_over_img = victory_img = rock_button_img = rules_button_img = gold_plate_img = None

class GameWorld:
    def __init__(self):
        self.grid_size = BASE_GRID_SIZE
        self.marked_cells = set() # Creates a set to track cells marked by the player
        self.marked_cell_times = {}  # Track when each cell was marked (for animation)
        self.scout_mode = False
        self.scout_cooldown = 10 # Initial 30-second cooldown
        self.scout_start_time = time.time() # Records the timestamp when scout mode was last activated (for cooldown calculation)
        self.scout_visible_time = 0 # Tracks when scout mode was last made visible (for duration control)
        self.scout_adjacent_cells = set() # Stores cells revealed during scout mode
        self.show_rules = True  # Flag to control whether rules screen is displayed (starts True for startup)
        self.scout_time_paused = False  # Flag to track if scout cooldown timer is currently paused
        self.scout_pause_start = 0  # Timestamp when scout timer was paused (for calculating elapsed pause time)
        self.new_game_button_pressed = False  # Flag for button press animation
        self.show_mobile_controls = False    # Only enabled when a touch device is detected
        self.reset_world()
        
    def _path_exists_a_star(self):
        "A* pathfinding check to ensure path from start to gold exists"
        start = tuple(self.agent_pos) # Converts agent position to a tuple
        gold = self.gold_pos # Position of gold
        
        def heuristic(a, b): # Defines Manhattan distance heuristic for A* algorithm
            return abs(a[0] - b[0]) + abs(a[1] - b[1])
        
        open_set = []
        heapq.heappush(open_set, (0, start)) # Initializes the priority queue with the starting position and priority 0
        came_from = {} # Tracks the path
        g_score = {start: 0} # Cost from start to current node
        f_score = {start: heuristic(start, gold)} # Estimated total cost (g_score + heuristic)
        
        directions = [(0,1), (1,0), (0,-1), (-1,0)] # Possible movement directions (up, right, down, left)
        
        while open_set:
            _, current = heapq.heappop(open_set) # Processes nodes in the priority queue until empty
            
            if current == gold: # If gold is reached it returns true
                return True
            
            for dx, dy in directions:
                neighbor = (current[0] + dx, current[1] + dy) # Calculates neighbor coordinates
                
                if (0 <= neighbor[0] < self.grid_size and 
                    0 <= neighbor[1] < self.grid_size and 
                    neighbor not in self.pits): # Checks if neighbor is within bounds and not a pit
                    
                    tentative_g_score = g_score[current] + 1 # This is just the cost so far plus the cost to move to the next cell
                    
                    if neighbor not in g_score or tentative_g_score < g_score[neighbor]: # This checks if we have visited the neighbor cell already
                        came_from[neighbor] = current # If we haven't visited neighbor then this means that I reached neighbor from prev.cell
                        g_score[neighbor] = tentative_g_score
                        f_score[neighbor] = tentative_g_score + heuristic(neighbor, gold)
                        heapq.heappush(open_set, (f_score[neighbor], neighbor))
        
        return False # return False if no path exists
        
    def calculate_optimal_moves(self):
        """Optimized calculation of moves to gold and back using single A* search"""
        start = (0, self.grid_size-1)
        gold = self.gold_pos
        
        # A* from start to gold
        open_set = []
        heapq.heappush(open_set, (0, start))
        came_from = {}
        g_score = {start: 0}
        f_score = {start: abs(start[0]-gold[0]) + abs(start[1]-gold[1])}
        
        directions = [(0,1),(1,0),(0,-1),(-1,0)]
        
        while open_set:
            _, current = heapq.heappop(open_set)
            
            if current == gold:
                break
            
            for dx, dy in directions:
                neighbor = (current[0] + dx, current[1] + dy)
                
                if (0 <= neighbor[0] < self.grid_size and 
                    0 <= neighbor[1] < self.grid_size and 
                    neighbor not in self.pits):
                    
                    tentative_g_score = g_score[current] + 1
                    
                    if neighbor not in g_score or tentative_g_score < g_score[neighbor]:
                        came_from[neighbor] = current
                        g_score[neighbor] = tentative_g_score
                        f_score[neighbor] = tentative_g_score + abs(neighbor[0]-gold[0]) + abs(neighbor[1]-gold[1])
                        heapq.heappush(open_set, (f_score[neighbor], neighbor))
        
        # Reconstruct path to gold
        path_to_gold = []
        if gold in came_from:
            current = gold
            while current != start:
                path_to_gold.append(current)
                current = came_from[current]
            path_to_gold.reverse()
        
        # Return double the one-way path length (to gold and back)
        return len(path_to_gold) * 2 if path_to_gold else float('inf')
        
    def reset_world(self, new_size=None):
        """Initialize or reset the game world with random positions"""
        pygame.mixer.stop()  # Stop any sounds still playing from the previous game
        if new_size is None:
            self.grid_size = BASE_GRID_SIZE
        else:
            self.grid_size = new_size
            
        self.agent_pos = [0, self.grid_size-1]
        self.move_count = 0
        self.player_move_count = 0
        self.has_gold = False
        self.has_arrow = True
        self.wumpus_alive = True
        self.game_over = False
        self.game_over_message = []
        self.gold_collected_message = ""
        self.wumpus_killed_message = ""  # Message displayed when Wumpus is killed
        self.arrow_miss_message = ""     # Message displayed when arrow misses
        self.explored = set()
        self.explored.add((0, self.grid_size-1))
        self.show_continue = False
        self.optimal_moves = 0
        self.marked_cells = set()
        self.marked_cell_times = {}  # Reset animation tracking
        self.scout_mode = False
        self.scout_cooldown = 10
        self.scout_start_time = time.time()
        self.scout_visible_time = 0
        self.scout_adjacent_cells = set()
        self.new_game_button_pressed = False  # Reset button press state
        self.shake_start_time = 0        # When screen shake started (ms)
        self.shake_duration = 450        # How long shake lasts (ms)
        self.shake_amplitude = 9         # Max shake pixels
        self.gold_collect_anim_start = 0 # When gold was collected (ms, 0 = not collecting)
        self.gold_collect_anim_duration = 650  # Gold pickup animation duration (ms)
        
        # Place Wumpus
        while True:
            x, y = random.randint(0, self.grid_size-1), random.randint(0, self.grid_size-1) # This generates a random value for x,y in the range 0, grid_size - 1
            if (x, y) != tuple(self.agent_pos): # This checks that the generated value is not same as agent position
                self.wumpus_pos = (x, y) # If it is not the same as agent then the Wumpus is placed there
                break
        
        # Place Gold
        while True:
            x, y = random.randint(0, self.grid_size-1), random.randint(0, self.grid_size-1)
            if (x, y) != tuple(self.agent_pos) and (x, y) != self.wumpus_pos: # This checks that the generated value is not same as agent position and Wumpus position
                self.gold_pos = (x, y) # Places the gold
                break
        
        # Calculate number of pits
        num_pits = 3 + 4 * (self.grid_size - BASE_GRID_SIZE) # This is to add 4 more pits for next level
        
        # Place Pits
        self.pits = []
        start_x, start_y = 0, self.grid_size-1 # The actual start in our game
        # Prohibited pit locations, all 4 sides of start
        adjacent_to_start = [ 
            (start_x + 1, start_y),
            (start_x, start_y - 1),
            (start_x, start_y + 1),
            (start_x - 1, start_y)
        ]
        
        attempts = 0 # Tracks the attempts to place pits and makes sure it won't be an infinite loop, so max is 100 attempts
        max_attempts = 100
        
        while len(self.pits) < num_pits and attempts < max_attempts:
            attempts += 1
            x, y = random.randint(0, self.grid_size-1), random.randint(0, self.grid_size-1) # Generates random x and y for pit coordinates
            pos = (x, y) # Stores them as pos
            # Checks if pos is not same as agent, gold, Wumpus, already placed pit, and not in prohibited locations
            if (pos != tuple(self.agent_pos) and 
                pos != self.wumpus_pos and 
                pos != self.gold_pos and 
                pos not in self.pits and 
                pos not in adjacent_to_start):
                
                self.pits.append(pos) # Adds the pit to list
                
                if not self._path_exists_a_star(): # After placing the pit, the A* pathfinding function is called to check if a path exists to gold, if not remove that pit
                    self.pits.pop()
        
        if attempts >= max_attempts: 
            print(f"Warning: Could only place {len(self.pits)} of {num_pits} pits while maintaining valid path")
        
        self.optimal_moves = self.calculate_optimal_moves() # Calculates the optimal moves
        self.update_perceptions() 
    
    def activate_scout_mode(self):
        """Activate scout mode to reveal adjacent cells"""
        current_time = time.time() # Gets the current time
        if current_time - self.scout_start_time >= 10 and self.scout_cooldown <= 0: # Checks if 30 seconds are over and cooldown is ready
            self.scout_mode = True # Enable scout mode
            self.scout_visible_time = current_time # Record when scout mode was activated
            self.scout_cooldown = 10 # Reset cooldown timer to 30 seconds
            self.scout_start_time = current_time # Update last activation time
            
            x, y = self.agent_pos # Gets the position of agent
            self.scout_adjacent_cells = set() # Empty set for adjacent cells
            for dx, dy in [(0,1),(1,0),(0,-1),(-1,0)]: # All 4 adjacent directions
                nx, ny = x + dx, y + dy # Calculates neighbor coordinates
                if 0 <= nx < self.grid_size and 0 <= ny < self.grid_size: # Checks if neighbor within grid bounds
                    self.scout_adjacent_cells.add((nx, ny)) # Adds the neighbor to set
                    self.explored.add((nx, ny)) # Adds neighbor to explored set
    
    def move_wumpus(self):
        """Move the Wumpus every 3 player moves"""
        if not self.wumpus_alive: # Check if Wumpus is alive
            return
            
        wx, wy = self.wumpus_pos # Get current location of Wumpus
        candidates = [] # Empty candidates list
        for dx, dy in [(0,1),(1,0),(0,-1),(-1,0)]: # All 4 adjacent directions Wumpus can move to
            nx, ny = wx + dx, wy + dy # New locations of Wumpus
            if 0 <= nx < self.grid_size and 0 <= ny < self.grid_size: # Checks if neighbor within grid bounds
                if (nx, ny) not in self.pits: # Checks if position has a pit
                    weight = 3 if (nx, ny) not in self.explored else 1 # Unexplored cells have a 3x chance to be picked
                    candidates.extend([(nx, ny)] * weight) # Adds each valid position to candidate multiplied by their weights
        
        if candidates:
            # Filter out the player's current cell so the Wumpus can't move onto them silently
            safe_candidates = [c for c in candidates if tuple(c) != tuple(self.agent_pos)]
            if not safe_candidates:
                safe_candidates = candidates  # Nowhere else to go — keep all options
            new_pos = random.choice(safe_candidates) # Randomly picking one from the candidates list
            if new_pos != self.wumpus_pos:
                self.wumpus_pos = new_pos # Move wumpus to new position
                self.update_perceptions()
                self.shake_start_time = pygame.time.get_ticks()  # Trigger screen shake
                if snd_monster_footstep:
                    snd_monster_footstep.stop()   # Cut off any still-playing instance
                    snd_monster_footstep.play()   # Always restart from the beginning
                print(f"Wumpus moved to {self.wumpus_pos}!")
    
    def update_perceptions(self):
        """Update stench and breeze locations"""
        self.stench = set() # Empty set for stench cells
        self.breeze = set() # Empty set for breeze cells
        
        if self.wumpus_alive: # When Wumpus is alive
            wx, wy = self.wumpus_pos # Get Wumpus position
            for dx, dy in [(0,1),(1,0),(0,-1),(-1,0)]: # Check all 4 adjacent cells for stench
                nx, ny = wx + dx, wy + dy # Calculate neighbor coordinates
                if 0 <= nx < self.grid_size and 0 <= ny < self.grid_size: # Ensures neighbor within grid bounds
                    self.stench.add((nx, ny)) # Adds stench to valid cells
        
        for px, py in self.pits: # Checks each pit in pits list
            for dx, dy in [(0,1),(1,0),(0,-1),(-1,0)]: 
                nx, ny = px + dx, py + dy
                if 0 <= nx < self.grid_size and 0 <= ny < self.grid_size:
                    self.breeze.add((nx, ny)) # Adds breeze to valid cells
    
    def get_current_perceptions(self):
        """Get the perceptions that should be visible based on current agent position"""
        current_perceptions = {
            'stench': set(), # Empty set for stench
            'breeze': set() # Empty set for breeze
        }
        
        for cell in self.explored: # Loops through the cells explored by the player
            if cell in self.stench: # Checks if the current explored cell has a stench
                current_perceptions['stench'].add(cell) # If yes, adds that explored cell to stench set
            if cell in self.breeze: # Checks if the current explored cell has a breeze
                current_perceptions['breeze'].add(cell) # If yes, adds that explored cell to breeze set
        
        return current_perceptions # Return the result

def process_game_action(world, action):
    """Handle a single game action ('up','down','left','right','shoot','scout').
    Called from both keyboard events and on-screen touch buttons."""
    if world.game_over or world.show_rules:
        return

    x, y = world.agent_pos
    moved = False
    shot  = False

    if action == 'up' and y > 0:
        world.agent_pos[1] -= 1;  moved = True
    elif action == 'down' and y < world.grid_size - 1:
        world.agent_pos[1] += 1;  moved = True
    elif action == 'left' and x > 0:
        world.agent_pos[0] -= 1;  moved = True
    elif action == 'right' and x < world.grid_size - 1:
        world.agent_pos[0] += 1;  moved = True
    elif action == 'shoot' and world.has_arrow:
        world.has_arrow = False
        wx, wy = world.wumpus_pos
        ax, ay = world.agent_pos
        if (abs(ax - wx) == 1 and ay == wy) or (abs(ay - wy) == 1 and ax == wx):
            world.wumpus_alive = False
            world.wumpus_killed_message = "You killed the Wumpus!"
            play(snd_arrow_kill)
            world.update_perceptions()
        else:
            world.arrow_miss_message = "Arrow missed!"
            play(snd_arrow_miss)
        shot = True
        world.move_count += 1
        world.player_move_count += 1
        if world.player_move_count % 3 == 0:
            world.move_wumpus()
    elif action == 'scout':
        world.activate_scout_mode()
        return

    if moved or shot:
        if moved:
            world.arrow_miss_message = ""
            play(snd_footstep)
            world.move_count += 1
            world.player_move_count += 1
            current_pos = tuple(world.agent_pos)
            world.explored.add(current_pos)
            print(f"Moved to: ({current_pos[0]+1},{world.grid_size-current_pos[1]})")
            if world.player_move_count % 3 == 0:
                world.move_wumpus()

        current_pos = tuple(world.agent_pos)

        if world.wumpus_alive and current_pos == world.wumpus_pos:
            world.game_over = True
            play(snd_monster_scream)
            world.game_over_message = ["You were eaten by the Wumpus!",
                                       "Click anywhere to start a new game"]
        elif current_pos in world.pits:
            world.game_over = True
            play(snd_falling_scream)
            world.game_over_message = ["You fell into a pit!",
                                       "Click anywhere to start a new game"]
        elif current_pos == world.gold_pos and not world.has_gold:
            world.has_gold = True
            play(snd_gold_collected)
            world.gold_collected_message = "Gold collected! Return to start!"
            world.wumpus_killed_message = ""
            world.gold_collect_anim_start = pygame.time.get_ticks()
        elif current_pos == (0, world.grid_size - 1) and world.has_gold:
            world.game_over = True
            world.game_over_message = ["You won! Gold safely returned!",
                                       "Click anywhere to start a new game"]


# --- Mobile / touch controls ---

def get_mobile_rects(screen_width, screen_height):
    """Return dict of on-screen button Rects, anchored to bottom corners."""
    btn  = 62   # D-pad button size
    gap  = 8    # gap between D-pad buttons
    cx   = 115  # D-pad horizontal centre from left edge
    cy   = screen_height - 170  # D-pad vertical centre

    aw, ah = 92, 58   # action button width / height
    agap   = 12
    ay_btn = screen_height - 130

    return {
        'up':    pygame.Rect(cx - btn//2,          cy - btn - gap//2, btn, btn),
        'down':  pygame.Rect(cx - btn//2,          cy + gap//2,       btn, btn),
        'left':  pygame.Rect(cx - btn - gap//2,    cy - btn//2,       btn, btn),
        'right': pygame.Rect(cx + gap//2,          cy - btn//2,       btn, btn),
        'shoot': pygame.Rect(screen_width - 2*aw - agap - 15, ay_btn, aw, ah),
        'scout': pygame.Rect(screen_width - aw - 15,           ay_btn, aw, ah),
    }

def draw_mobile_controls(surface, world, screen_width, screen_height):
    """Draw the on-screen D-pad and action buttons (touch devices only)."""
    if not world.show_mobile_controls or world.game_over or world.show_rules:
        return

    rects     = get_mobile_rects(screen_width, screen_height)
    mouse_pos = pygame.mouse.get_pos()

    BASE   = {'up':(72,67,63),'down':(72,67,63),'left':(72,67,63),'right':(72,67,63),
              'shoot':(130,45,45),'scout':(85,85,30)}
    HOVER  = {'up':(105,100,95),'down':(105,100,95),'left':(105,100,95),'right':(105,100,95),
              'shoot':(170,65,65),'scout':(120,120,45)}
    BORDER = (35, 33, 30)
    LABELS = {'up':'▲','down':'▼','left':'◄','right':'►',
              'shoot':'SHOOT','scout':'SCOUT'}

    for key, rect in rects.items():
        hover  = rect.collidepoint(mouse_pos)
        color  = HOVER[key] if hover else BASE[key]

        # Button body
        pygame.draw.rect(surface, color, rect, border_radius=10)

        # Bevel highlight (top-left edge lighter)
        lighter = tuple(min(255, c + 35) for c in color)
        darker  = tuple(max(0,   c - 35) for c in color)
        pygame.draw.line(surface, lighter, (rect.left+3,  rect.top+3),  (rect.right-4, rect.top+3),  2)
        pygame.draw.line(surface, lighter, (rect.left+3,  rect.top+3),  (rect.left+3,  rect.bottom-4), 2)
        pygame.draw.line(surface, darker,  (rect.left+3,  rect.bottom-3),(rect.right-3, rect.bottom-3), 2)
        pygame.draw.line(surface, darker,  (rect.right-3, rect.top+3),  (rect.right-3, rect.bottom-3), 2)

        # Border
        pygame.draw.rect(surface, BORDER, rect, 2, border_radius=10)

        # Label
        font  = VT323_FONT if key in ('shoot','scout') else VT323_FONT_LARGE
        label = font.render(LABELS[key], True, (240, 235, 220))
        surface.blit(label, (rect.centerx - label.get_width()  // 2,
                             rect.centery - label.get_height() // 2))


def get_cell_size(world, screen_width, screen_height):
    """Return the right cell size for the device.
    Desktop: always CELL_SIZE (80px).
    Mobile: shrinks so the grid fits above the touch controls without clutter."""
    if not world.show_mobile_controls:
        return CELL_SIZE
    # Reserve ~90px for top HUD and ~250px for bottom controls
    available_w = (screen_width  - 20) // world.grid_size
    available_h = (screen_height - 90 - 250) // world.grid_size
    cs = min(available_w, available_h)
    return max(28, min(cs, CELL_SIZE))  # clamp: 28px min, 80px max


def draw_game(world):
    """Draw the entire game state"""
    screen.fill(OFF_WHITE) # Off-white background to the game screen
    mouse_pos = pygame.mouse.get_pos() # Tracks mouse position for mouse hover effects
    
    # Get current screen dimensions for proper centering
    screen_width, screen_height = screen.get_size() # Get the actual window size (may have changed from resize)
    
    # Update scout mode cooldown
    current_time = time.time() # Gets current time
    # Check if rules screen is currently being displayed - if so, pause the cooldown timer
    if world.show_rules:
        # If rules just opened, record when we paused the timer
        if not world.scout_time_paused:
            world.scout_time_paused = True  # Set flag indicating timer is now paused
            world.scout_pause_start = current_time  # Store the timestamp when pause began
    else:
        # Rules are not shown - check if we were previously paused
        if world.scout_time_paused:
            # Calculate how long the timer was paused while viewing rules
            pause_duration = current_time - world.scout_pause_start
            # Extend the scout_start_time by the pause duration so cooldown doesn't count down during pause
            world.scout_start_time += pause_duration
            world.scout_time_paused = False  # Clear the pause flag since rules are now closed
        # Update the cooldown value based on elapsed time (excluding pause periods)
        if world.scout_cooldown > 0:
            world.scout_cooldown = max(0, 10 - (current_time - world.scout_start_time))
    
    # Check if scout mode should be deactivated
    if world.scout_mode and current_time - world.scout_visible_time >= 1:
        world.scout_mode = False
    
    # Animation time for effects
    anim_time = get_animation_time()

    # --- Screen shake ---
    shake_x, shake_y = 0, 0
    shake_elapsed = anim_time - world.shake_start_time
    if 0 < shake_elapsed < world.shake_duration:
        progress = shake_elapsed / world.shake_duration
        amplitude = world.shake_amplitude * (1 - progress)  # Decay to zero
        shake_x = int(amplitude * math.sin(shake_elapsed * 0.18))
        shake_y = int(amplitude * math.cos(shake_elapsed * 0.23))

    if not world.game_over:
        # Compute dynamic cell size and store it so the event handler can use it
        cs = get_cell_size(world, screen_width, screen_height)
        world.cell_size = cs  # shared with click-detection in the event loop

        grid_width  = world.grid_size * cs
        grid_height = world.grid_size * cs

        if world.show_mobile_controls:
            # On mobile, centre the grid in the space between HUD and touch controls
            top_hud    = 90
            bot_ctrl   = 250
            avail_h    = screen_height - top_hud - bot_ctrl
            grid_x = (screen_width - grid_width)  // 2 + shake_x
            grid_y = top_hud + (avail_h - grid_height) // 2 + shake_y
        else:
            grid_x = (screen_width  - grid_width)  // 2 + shake_x
            grid_y = (screen_height - grid_height - 40) // 2 + shake_y
        
        # Display pit count
        pit_font = VT323_FONT_SMALL
        pit_text = pit_font.render(f"Pits: {len(world.pits)}", True, BLUE)
        screen.blit(pit_text, (screen_width - 100, 50)) # Placing the pit text on top right corner of the game window
        
        # Get current visible perceptions
        current_perceptions = world.get_current_perceptions()
        
        # Draw grid cells
        PERC_SIZE = max(14, cs // 3)  # Perception icons scale with cell size
        for row in range(world.grid_size):
            for col in range(world.grid_size):
                rect = pygame.Rect(
                    grid_x + col * cs,
                    grid_y + row * cs,
                    cs, cs
                )

                # --- Start cell: soft green tint ---
                if (col, row) == (0, world.grid_size - 1):
                    pygame.draw.rect(screen, (180, 230, 180), rect)

                # --- Agent current cell highlight ---
                if (col, row) == (world.agent_pos[0], world.agent_pos[1]):
                    pygame.draw.rect(screen, (220, 240, 255), rect)

                # --- Unexplored fog overlay ---
                if (col, row) not in world.explored:
                    fog = pygame.Surface((cs, cs), pygame.SRCALPHA)
                    fog.fill((100, 100, 110, 120))
                    screen.blit(fog, (rect.x, rect.y))

                # Draw cell border
                pygame.draw.rect(screen, BLACK, rect, 1)

                # Draw scout mode highlight
                if world.scout_mode and (col, row) in world.scout_adjacent_cells:
                    highlight = pygame.Surface((cs, cs), pygame.SRCALPHA)
                    highlight.fill(SCOUT_COLOR)
                    screen.blit(highlight, (rect.x, rect.y))

                # Coordinate labels (hide on very small cells to avoid clutter)
                if cs >= 40:
                    font = VT323_FONT_SMALL
                    coord_text = font.render(f"{col+1},{world.grid_size-row}", True, BLACK)
                    screen.blit(coord_text, (rect.x + 3, rect.y + 2))

                # Draw red exclamation mark if cell is marked
                if (col, row) in world.marked_cells:
                    mark_font = VT323_FONT_SMALL
                    mark_text = mark_font.render("!", True, RED)
                    screen.blit(mark_text, (rect.right - 14, rect.top - 2))

                # Draw perceptions — small icons pinned to bottom corners
                # Stench: bottom-left  |  Breeze: bottom-right
                if (col, row) in current_perceptions['stench']:
                    s_icon = pygame.transform.smoothscale(stench_img, (PERC_SIZE, PERC_SIZE))
                    screen.blit(s_icon, (rect.x + 2, rect.bottom - PERC_SIZE - 2))
                if (col, row) in current_perceptions['breeze']:
                    b_icon = pygame.transform.smoothscale(breeze_img, (PERC_SIZE, PERC_SIZE))
                    screen.blit(b_icon, (rect.right - PERC_SIZE - 2, rect.bottom - PERC_SIZE - 2))
        
        def place_img(img, gx, gy):
            """Scale img to fit the cell and centre it."""
            max_dim = cs - 8
            w, h = img.get_size()
            if w > max_dim or h > max_dim:
                scale = max_dim / max(w, h)
                img = pygame.transform.smoothscale(img, (max(1,int(w*scale)), max(1,int(h*scale))))
                w, h = img.get_size()
            x = grid_x + gx * cs + (cs - w) // 2
            y = grid_y + gy * cs + (cs - h) // 2
            screen.blit(img, (x, y))

        # Draw gold (with pickup animation)
        gx, gy = world.gold_pos
        gold_anim_elapsed = anim_time - world.gold_collect_anim_start
        if not world.has_gold and (gx, gy) in world.explored:
            place_img(gold_img, gx, gy)
        elif world.has_gold and world.gold_collect_anim_start > 0 and gold_anim_elapsed < world.gold_collect_anim_duration:
            progress = gold_anim_elapsed / world.gold_collect_anim_duration
            scale = 1.0 + 1.2 * progress
            alpha = int(255 * (1.0 - progress))
            base_w, base_h = gold_img.get_width(), gold_img.get_height()
            new_w = max(1, int(base_w * scale))
            new_h = max(1, int(base_h * scale))
            scaled = pygame.transform.smoothscale(gold_img, (new_w, new_h))
            scaled.set_alpha(alpha)
            anim_x = grid_x + gx * cs + (cs - new_w) // 2
            anim_y = grid_y + gy * cs + (cs - new_h) // 2
            screen.blit(scaled, (anim_x, anim_y))

        # Draw Wumpus (only when alive and explored)
        if world.wumpus_alive and world.wumpus_pos in world.explored:
            place_img(wumpus_img, *world.wumpus_pos)

        # Draw pits
        for px, py in world.pits:
            if (px, py) in world.explored:
                place_img(pit_img, px, py)

        # Draw agent
        place_img(agent_img, *world.agent_pos)
        
        # Draw gold collection message
        if world.gold_collected_message: # set to "Gold collected! Return to start!"
            font = VT323_FONT_LARGE
            text = font.render(world.gold_collected_message, True, DARK_GOLD)
            screen.blit(text, (screen_width // 2 - text.get_width() // 2, 20)) # Places the text on center top of screen based on current window width
        
        # Draw Wumpus killed message
        if world.wumpus_killed_message:
            font = VT323_FONT_LARGE
            text = font.render(world.wumpus_killed_message, True, (200, 50, 50))
            screen.blit(text, (screen_width // 2 - text.get_width() // 2, 50))

        # Draw arrow miss message
        if world.arrow_miss_message:
            font = VT323_FONT_LARGE
            text = font.render(world.arrow_miss_message, True, (180, 80, 0))  # Orange for miss
            screen.blit(text, (screen_width // 2 - text.get_width() // 2, 50))

        
        # Draw arrow status
        arrow_font = VT323_FONT_SMALL
        arrow_text = arrow_font.render(f"Arrows: {1 if world.has_arrow else 0}", True, BLACK) 
        screen.blit(arrow_text, (screen_width - 100, 20)) # Places arrow count on top right of screen
        
        # Draw scout mode status
        scout_font = VT323_FONT_SMALL
        # Use world.scout_cooldown which properly pauses when rules are shown
        if world.scout_cooldown > 0: # Check if cooldown is still active
            scout_text = scout_font.render(f"Scout: {int(world.scout_cooldown)}s", True, (200, 0, 0))
        else: # Scout mode is ready (no active use, no cooldown)
            scout_text = scout_font.render("Scout: Ready (R)", True, (0, 150, 0))
        screen.blit(scout_text, (screen_width - 100, 80))
        
        # Draw Rules button (image)
        rules_button_rect = pygame.Rect(screen_width - 200, 20, 80, 25)
        rules_hover = rules_button_rect.collidepoint(mouse_pos) and not world.show_rules
        # Apply hover effect (slightly larger) only when rules not showing
        if rules_hover:
            hover_img = pygame.transform.smoothscale(rules_button_img, (85, 30))
            hover_x = rules_button_rect.x - 2
            hover_y = rules_button_rect.y - 2
            screen.blit(hover_img, (hover_x, hover_y))
            # Hover text
            rules_font = VT323_FONT_SMALL
            rules_text_render = rules_font.render("Rules", True, BLACK)
            screen.blit(rules_text_render, (rules_button_rect.centerx - rules_text_render.get_width() // 2,
                                    rules_button_rect.centery - rules_text_render.get_height() // 2))
        else:
            screen.blit(rules_button_img, (rules_button_rect.x, rules_button_rect.y))
            # Normal text
            rules_font = VT323_FONT_SMALL
            rules_text_render = rules_font.render("Rules", True, BLACK)
            screen.blit(rules_text_render, (rules_button_rect.centerx - rules_text_render.get_width() // 2,
                                    rules_button_rect.centery - rules_text_render.get_height() // 2))
        
        # Draw mobile touch controls
        draw_mobile_controls(screen, world, screen_width, screen_height)

        # Draw New Game button (rock button image)
        button_rect = pygame.Rect(screen_width // 2 - 75, screen_height - 50, 150, 30)
        # Check if mouse is hovering over button
        button_hover = button_rect.collidepoint(mouse_pos)
        # Apply hover effect (slightly larger and brighter)
        if world.new_game_button_pressed:
            # Pressed state: offset down-right and darken
            pressed_x = button_rect.x + 3
            pressed_y = button_rect.y + 3
            # Create darkened version
            darkened_img = rock_button_img.copy()
            dark_overlay = pygame.Surface((150, 30), pygame.SRCALPHA)
            dark_overlay.fill((0, 0, 0, 60))  # Semi-transparent black
            darkened_img.blit(dark_overlay, (0, 0))
            screen.blit(darkened_img, (pressed_x, pressed_y))
            # Text also offset
            button_font = VT323_FONT
            button_text = button_font.render("New Game", True, BLACK)
            screen.blit(button_text, (button_rect.centerx + 3 - button_text.get_width() // 2,
                                    button_rect.centery + 3 - button_text.get_height() // 2))
        elif button_hover:
            # Scale up slightly on hover (155x35 instead of 150x30)
            hover_img = pygame.transform.smoothscale(rock_button_img, (155, 35))
            # Calculate centered position for larger image
            hover_x = button_rect.x - 2
            hover_y = button_rect.y - 2
            screen.blit(hover_img, (hover_x, hover_y))
            # Hover text
            button_font = VT323_FONT
            button_text = button_font.render("New Game", True, BLACK)
            screen.blit(button_text, (button_rect.centerx - button_text.get_width() // 2,
                                    button_rect.centery - button_text.get_height() // 2))
        else:
            # Normal state
            screen.blit(rock_button_img, (button_rect.x, button_rect.y))
            button_font = VT323_FONT
            button_text = button_font.render("New Game", True, BLACK)
            screen.blit(button_text, (button_rect.centerx - button_text.get_width() // 2,
                                    button_rect.centery - button_text.get_height() // 2))
    else:
        # Victory Screen - use dynamic screen size
        screen_width, screen_height = screen.get_size() # Get current window size

        # Game Over or Victory Screen
        overlay = pygame.Surface((screen_width, screen_height), pygame.SRCALPHA) # Cover entire screen with black
        overlay.fill((0, 0, 0, 255))
        screen.blit(overlay, (0, 0)) # Covers from (0,0) to (WIDTH, HEIGHT)
        
        is_victory = "won" in world.game_over_message[0].lower()
        if is_victory:
            end_img = victory_img # Displays victory image
            if world.grid_size < MAX_GRID_SIZE:
                world.show_continue = True # Continue button if not maximum grid size
            glow_color = (255, 215, 0)   # Gold glow for victory
        else:
            end_img = game_over_img # Displays game over image
            world.show_continue = False
            glow_color = (200, 0, 0)     # Red glow for game over

        # Pulsing border glow around the entire screen
        pulse = 0.5 + 0.5 * math.sin(anim_time * 0.005)  # 0.0 → 1.0 pulse
        glow_alpha = int(60 + 120 * pulse)
        for thickness in range(12, 0, -3):
            border_surf = pygame.Surface((screen_width, screen_height), pygame.SRCALPHA)
            r, g, b = glow_color
            pygame.draw.rect(border_surf, (r, g, b, glow_alpha // thickness),
                             (0, 0, screen_width, screen_height), thickness * 3)
            screen.blit(border_surf, (0, 0))

        img_x = (screen_width - end_img.get_width()) // 2 # Horizontal centering
        img_y = (screen_height - end_img.get_height()) // 2 - 50 # Vertical centering
        screen.blit(end_img, (img_x, img_y))
        
        message_font = VT323_FONT_LARGE # Arcade font for game over message
        y_offset = img_y + end_img.get_height() + 20 # Sets up message font and starting Y position below the image
        
        if "won" in world.game_over_message[0].lower(): # Check if game is won
            optimal_text = f"Optimal moves: {world.optimal_moves}" 
            optimal_render = message_font.render(optimal_text, True, WHITE) # Display optimal moves 
            screen.blit(optimal_render, (screen_width // 2 - optimal_render.get_width() // 2, y_offset))
            y_offset += 30
            
            player_text = f"Your moves: {world.move_count}"
            player_render = message_font.render(player_text, True, WHITE)
            screen.blit(player_render, (screen_width // 2 - player_render.get_width() // 2, y_offset)) # Centers text and starts from y offset
            y_offset += 30 # So that next text has gap
            
            if world.optimal_moves > 0: # If optimal moves exist
                efficiency = (world.optimal_moves / world.move_count) * 100 # Calculates efficiency
                eff_text = f"Efficiency: {min(100, efficiency):.1f}%" # In case player beats A*
                eff_render = message_font.render(eff_text, True, WHITE)
                screen.blit(eff_render, (screen_width // 2 - eff_render.get_width() // 2, y_offset))
                y_offset += 30
        
        for line in world.game_over_message: # Loops through all the game over messages
            message_text = message_font.render(line, True, WHITE)
            screen.blit(message_text, (screen_width // 2 - message_text.get_width() // 2, y_offset))
            y_offset += 30
        
        if world.show_continue:
            continue_rect = pygame.Rect(screen_width // 2 - 100, screen_height - 110, 200, 50)
            hover = continue_rect.collidepoint(mouse_pos)
            if hover:
                hover_img = pygame.transform.smoothscale(gold_plate_img, (208, 54))
                screen.blit(hover_img, (continue_rect.x - 4, continue_rect.y - 2))
            else:
                screen.blit(gold_plate_img, (continue_rect.x, continue_rect.y))
            continue_font = VT323_FONT_LARGE
            continue_text = continue_font.render("Continue", True, BLACK)
            screen.blit(continue_text, (continue_rect.centerx - continue_text.get_width() // 2,
                                        continue_rect.centery - continue_text.get_height() // 2))
    
    # Always show move counter, level, and pit count
    move_font = VT323_FONT
    move_text = move_font.render(f"Moves: {world.move_count}", True, RED) # Adds move counter to top right of screen
    screen.blit(move_text, (20, 20))
    level_text = move_font.render(f"Level: {world.grid_size}x{world.grid_size}", True, BLUE) # Adds level near move counter
    screen.blit(level_text, (20 + move_text.get_width() + 10, 20))
    pit_count_text = move_font.render(f"Pits: {len(world.pits)}", True, BLUE) # Display pit count below moves
    screen.blit(pit_count_text, (20, 20 + move_text.get_height() + 5))

def draw_scroll_shape(surface, x, y, width, height, scroll_depth=25):
    """Draw a scroll shape with curved top and bottom edges"""

    # Create a surface for the scroll with alpha
    scroll_surf = pygame.Surface((width, height), pygame.SRCALPHA)
    
    # Main parchment color
    parchment_color = PARCHMENT
    
    # Create the main body rectangle (slightly smaller for the scroll effect)
    body_margin = 10
    body_rect = pygame.Rect(body_margin, scroll_depth, width - 2*body_margin, height - 2*scroll_depth)
    
    # Fill the main body with parchment texture
    parchment = create_parchment_texture(body_rect.width, body_rect.height)
    scroll_surf.blit(parchment, (body_rect.x, body_rect.y))
    
    # Draw the body border
    pygame.draw.rect(scroll_surf, PARCHMENT_BORDER, body_rect, 2)
    
    # Draw top rolled edge (curved)
    for i in range(scroll_depth):
        progress = i / scroll_depth
        # Create a slight curve effect
        curve_offset = int(5 * math.sin(progress * math.pi))
        line_color = (
            int(parchment_color[0] * (0.8 + 0.2 * progress)),
            int(parchment_color[1] * (0.8 + 0.2 * progress)),
            int(parchment_color[2] * (0.8 + 0.2 * progress))
        )
        # Draw horizontal line with curve
        pygame.draw.line(scroll_surf, line_color, 
                        (body_margin + curve_offset, i),
                        (width - body_margin - curve_offset, i), 1)
    
    # Draw bottom rolled edge (curved)
    for i in range(scroll_depth):
        progress = i / scroll_depth
        # Reverse the curve for bottom
        curve_offset = int(5 * math.sin((1 - progress) * math.pi))
        line_color = (
            int(parchment_color[0] * (0.8 + 0.2 * (1 - progress))),
            int(parchment_color[1] * (0.8 + 0.2 * (1 - progress))),
            int(parchment_color[2] * (0.8 + 0.2 * (1 - progress)))
        )
        y_pos = height - scroll_depth + i
        pygame.draw.line(scroll_surf, line_color, 
                        (body_margin + curve_offset, y_pos),
                        (width - body_margin - curve_offset, y_pos), 1)
    
    # Draw side edges of the scroll (giving the rolled look)
    side_color = (PARCHMENT[0] - 30, PARCHMENT[1] - 25, PARCHMENT[2] - 20)
    # Left side roll
    pygame.draw.ellipse(scroll_surf, side_color, 
                       (0, scroll_depth - 5, 20, height - 2*scroll_depth + 10))
    # Right side roll
    pygame.draw.ellipse(scroll_surf, side_color, 
                       (width - 20, scroll_depth - 5, 20, height - 2*scroll_depth + 10))
    
    # Draw decorative end caps for top and bottom scroll rolls
    cap_color = (PARCHMENT[0] - 40, PARCHMENT[1] - 35, PARCHMENT[2] - 30)
    # Top cap
    pygame.draw.ellipse(scroll_surf, cap_color, (-5, -5, width + 10, scroll_depth + 10))
    # Bottom cap
    pygame.draw.ellipse(scroll_surf, cap_color, (-5, height - scroll_depth - 5, width + 10, scroll_depth + 10))
    
    # Draw inner highlight lines to give depth to the rolls
    highlight_color = (PARCHMENT[0] + 20, PARCHMENT[1] + 15, PARCHMENT[2] + 10)
    shadow_color = (PARCHMENT[0] - 50, PARCHMENT[1] - 45, PARCHMENT[2] - 40)
    
    # Top roll highlight
    pygame.draw.arc(scroll_surf, highlight_color, 
                   (-5, 0, width + 10, scroll_depth * 2), 0, math.pi, 2)
    # Bottom roll shadow
    pygame.draw.arc(scroll_surf, shadow_color, 
                   (-5, height - 2*scroll_depth, width + 10, scroll_depth * 2), 
                   math.pi, 2*math.pi, 2)
    
    # Blit the scroll onto the main surface
    surface.blit(scroll_surf, (x, y))

def draw_rules_screen():
    """Draw the rules screen overlay on top of the game"""
    # Get current screen dimensions
    screen_width, screen_height = screen.get_size() # Get the actual window size for proper centering
    
    # Create a semi-transparent dark overlay that covers the entire game screen
    overlay = pygame.Surface((screen_width, screen_height), pygame.SRCALPHA)  # Creates a surface with alpha transparency support
    overlay.fill(RULES_BG_COLOR)  # Fills the overlay with the semi-transparent dark background color
    screen.blit(overlay, (0, 0))  # Draws the overlay at position (0,0) covering the entire screen
    
    # Pre-calculate panel height based on actual content so nothing gets clipped
    title_font_temp  = VT323_FONT_TITLE
    section_font_temp = VT323_FONT
    text_font_temp   = pygame.font.Font(None, 17)
    needed_height = 30  # top padding
    for line in RULES_TEXT:
        if not line:
            needed_height += 10
        elif "WUMPUS WORLD" in line:
            needed_height += title_font_temp.size(line)[1] + 6
        elif line.endswith(":"):
            needed_height += section_font_temp.size(line)[1] + 6
        else:
            needed_height += text_font_temp.size(line)[1] + 6
    needed_height += 20  # bottom padding

    panel_width  = 720
    panel_height = min(needed_height, screen_height - 40)  # Never taller than the window
    panel_x = (screen_width  - panel_width)  // 2
    panel_y = (screen_height - panel_height) // 2
    panel_rect = pygame.Rect(panel_x, panel_y, panel_width, panel_height)
    
    # Draw parchment texture background
    parchment_surf = create_parchment_texture(panel_width, panel_height)
    screen.blit(parchment_surf, (panel_x, panel_y))
    
    # Draw aged border effect
    pygame.draw.rect(screen, PARCHMENT_BORDER, panel_rect, 4, border_radius=5)  # Draws aged border
    pygame.draw.rect(screen, (100, 85, 70), panel_rect, 2, border_radius=5)  # Darker inner border
    
    # Render each line of the rules text
    title_font   = VT323_FONT_TITLE
    section_font = VT323_FONT
    text_font    = pygame.font.Font(None, 17)
    
    y_offset = panel_y + 20  # Starting Y position for text (20 pixels from top of panel)
    for line in RULES_TEXT:  # Loops through each line of rules text
        if not line:  # Checks if line is empty (used for spacing)
            y_offset += 10  # Adds 10 pixels of vertical spacing for empty lines
            continue  # Skips to next line
        
        # Determine font and color based on line content (dark text for parchment)
        if "WUMPUS WORLD" in line:  # Checks if this is the title line
            font = title_font  # Uses title font for the main heading
            color = (150, 30, 30)  # Dark red for title on parchment
        elif line.endswith(":"):  # Checks if line ends with colon (section headers)
            font = section_font  # Uses section font for headers
            color = (50, 50, 120)  # Dark blue for headers on parchment
        else:  # Regular text line
            font = text_font  # Uses normal text font
            color = (40, 40, 40)  # Dark gray text for parchment background
        
        # Render the text line
        text_surface = font.render(line, True, color)  # Renders the text with chosen font and color
        text_x = panel_x + (panel_width - text_surface.get_width()) // 2  # Centers text horizontally in panel
        screen.blit(text_surface, (text_x, y_offset))  # Draws the text at calculated position
        y_offset += text_surface.get_height() + 5  # Moves down for next line (with 5px gap)

def _stage(msg):
    """Show progress as green text on the page so we can see exactly how far
    startup gets in the browser, without needing the dev console."""
    print("STAGE:", msg)
    try:
        import platform as _pf
        d = _pf.window.document
        e = d.getElementById("wstage")
        if e is None:
            e = d.createElement("div")
            e.id = "wstage"
            e.style.cssText = ("position:fixed;left:0;top:0;z-index:99999;"
                               "background:#002;color:#0f0;font:16px monospace;padding:6px;")
            d.body.appendChild(e)
        e.textContent = "STAGE: " + msg
    except Exception:
        pass


async def main():
    global screen, clock
    global VT323_FONT, VT323_FONT_SMALL, VT323_FONT_LARGE, VT323_FONT_TITLE
    global agent_img, gold_img, wumpus_img, pit_img, stench_img, breeze_img
    global game_over_img, victory_img, rock_button_img, rules_button_img, gold_plate_img
    global snd_footstep, snd_gold_collected, snd_arrow_kill, snd_arrow_miss
    global snd_monster_footstep, snd_monster_scream, snd_falling_scream

    # ── Initialise pygame ──
    _stage("pygame.init")
    pygame.init()
    try:
        pygame.mixer.init()
    except BaseException as e:
        print(f"mixer.init() failed (audio disabled): {e}")

    _stage("set_mode")
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Wumpus World by Sharath Shankar Rathakrishnan")
    clock = pygame.time.Clock()
    await asyncio.sleep(0)

    # Load fonts — three levels of fallback so we always get something
    try:
        _font_path = os.path.join(BASE_DIR, 'VT323-Regular.ttf')
        VT323_FONT       = pygame.font.Font(_font_path, 24)
        VT323_FONT_SMALL = pygame.font.Font(_font_path, 20)
        VT323_FONT_LARGE = pygame.font.Font(_font_path, 32)
        VT323_FONT_TITLE = pygame.font.Font(_font_path, 48)
    except BaseException:
        try:
            VT323_FONT       = pygame.font.SysFont('Courier New', 24, bold=True)
            VT323_FONT_SMALL = pygame.font.SysFont('Courier New', 20, bold=True)
            VT323_FONT_LARGE = pygame.font.SysFont('Courier New', 32, bold=True)
            VT323_FONT_TITLE = pygame.font.SysFont('Courier New', 48, bold=True)
        except BaseException:
            VT323_FONT       = pygame.font.Font(None, 24)
            VT323_FONT_SMALL = pygame.font.Font(None, 20)
            VT323_FONT_LARGE = pygame.font.Font(None, 32)
            VT323_FONT_TITLE = pygame.font.Font(None, 48)

    try:
        # Load images (requires display to be initialised first)
        _stage("load images")
        agent_img       = load_image('agent.png',       default_color=(0, 0, 255))
        gold_img        = load_image('gold.png',         default_color=(255, 215, 0))
        wumpus_img      = load_image('wumpus.png',       default_color=(255, 0, 0))
        pit_img         = load_image('pit.png',          default_color=(0, 0, 0))
        stench_img      = load_image('stench.png',       default_color=(200, 0, 0, 150))
        breeze_img      = load_image('breeze.png',       default_color=(100, 100, 255, 150))
        game_over_img   = load_image('game_over.png',    default_color=(200, 0, 0, 200),  target_size=(400, 200))
        victory_img     = load_image('victory.png',      default_color=(0, 200, 0, 200),  target_size=(400, 200))
        rock_button_img = load_image('rock_button.jpg',  default_color=(100, 100, 100),   target_size=(150, 30))
        rules_button_img= load_image('rules.png',        default_color=(100, 100, 100),   target_size=(80, 25))
        gold_plate_img  = load_image('gold_plate.png',   default_color=(200, 150, 0),     target_size=(200, 50))

        # Load sounds (requires mixer to be initialised first)
        _stage("load sounds")
        snd_footstep         = load_sound('footstep.ogg')
        snd_gold_collected   = load_sound('gold_collected.ogg')
        snd_arrow_kill       = load_sound('arrow_sound+monster_dying.ogg')
        snd_arrow_miss       = load_sound('arrow_sound.ogg')
        snd_monster_footstep = load_sound('monster_footsteps.ogg')
        snd_monster_scream   = load_sound('monster_scream.ogg')
        snd_falling_scream   = load_sound('falling_scream.ogg')

        if snd_gold_collected:   snd_gold_collected   = change_speed(snd_gold_collected,   1.5)
        if snd_arrow_kill:       snd_arrow_kill        = change_speed(snd_arrow_kill,       1.5)
        if snd_arrow_miss:       snd_arrow_miss        = change_speed(snd_arrow_miss,       1.5)
        if snd_monster_scream:   snd_monster_scream    = change_speed(snd_monster_scream,   2.5)
        if snd_falling_scream:   snd_falling_scream    = change_speed(snd_falling_scream,   1.25)
        if snd_monster_footstep: snd_monster_footstep  = change_speed(snd_monster_footstep, 1.5)

    except Exception as _load_err:
        import traceback
        _tb = traceback.format_exc()
        print("LOAD ERROR:", _tb)
        # Show error on canvas so we can read it without a console
        screen.fill((0, 0, 0))
        _ef = pygame.font.Font(None, 22)
        _y = 10
        for _line in (["LOAD ERROR — check browser console:"] + _tb.splitlines())[:30]:
            screen.blit(_ef.render(_line[:90], True, (255, 80, 80)), (10, _y))
            _y += 22
        pygame.display.flip()
        while True:
            for _e in pygame.event.get():
                if _e.type == pygame.QUIT:
                    pygame.quit()
                    return
            await asyncio.sleep(0)

    _stage("create GameWorld")
    try:
        world = GameWorld() # Creates the game world with default 6x6 grid
    except Exception as _we:
        import traceback; _tb2 = traceback.format_exc()
        print("WORLD INIT ERROR:", _tb2)
        screen.fill((0,0,0))
        _ef2 = pygame.font.Font(None, 22)
        _y2 = 10
        for _line2 in (["WORLD INIT ERROR:"] + _tb2.splitlines())[:30]:
            screen.blit(_ef2.render(_line2[:90], True, (255, 80, 80)), (10, _y2)); _y2 += 22
        pygame.display.flip()
        while True:
            for _e2 in pygame.event.get():
                if _e2.type == pygame.QUIT: pygame.quit(); return
            await asyncio.sleep(0)

    _stage("entering game loop")
    running = True
    _frame = 0
    while running:
        _frame += 1
        if _frame <= 3:
            _stage(f"loop frame {_frame}")
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.MOUSEBUTTONDOWN:
                screen_width, screen_height = screen.get_size()

                if world.show_rules:
                    world.show_rules = False
                    continue

                if world.game_over:
                    if world.show_continue:
                        continue_rect = pygame.Rect(screen_width // 2 - 100, screen_height - 110, 200, 50)
                        if continue_rect.collidepoint(event.pos):
                            new_size = world.grid_size + 1
                            world.reset_world(new_size=new_size)
                            continue
                    world.reset_world()
                else:
                    rules_button_rect = pygame.Rect(screen_width - 200, 20, 80, 25)
                    if rules_button_rect.collidepoint(event.pos):
                        world.show_rules = True
                        continue

                    cs = getattr(world, 'cell_size', CELL_SIZE)
                    gw = world.grid_size * cs
                    gh = world.grid_size * cs
                    if world.show_mobile_controls:
                        grid_x = (screen_width - gw) // 2
                        grid_y = 90 + ((screen_height - 90 - 250 - gh) // 2)
                    else:
                        grid_x = (screen_width - gw) // 2
                        grid_y = (screen_height - gh - 40) // 2

                    if (grid_x <= event.pos[0] < grid_x + gw and
                            grid_y <= event.pos[1] < grid_y + gh):
                        col = (event.pos[0] - grid_x) // cs
                        row = (event.pos[1] - grid_y) // cs
                        if event.button == 1:
                            if (col, row) in world.marked_cells:
                                world.marked_cells.remove((col, row))
                                del world.marked_cell_times[(col, row)]
                            else:
                                world.marked_cells.add((col, row))
                                world.marked_cell_times[(col, row)] = get_animation_time()

                    button_rect = pygame.Rect(screen_width // 2 - 75, screen_height - 50, 150, 30)
                    if button_rect.collidepoint(event.pos):
                        world.new_game_button_pressed = True

                    if world.show_mobile_controls:
                        for action, rect in get_mobile_rects(screen_width, screen_height).items():
                            if rect.collidepoint(event.pos):
                                process_game_action(world, action)
                                break

            elif event.type == pygame.MOUSEBUTTONUP:
                if world.new_game_button_pressed:
                    world.new_game_button_pressed = False
                    screen_width, screen_height = screen.get_size()
                    button_rect = pygame.Rect(screen_width // 2 - 75, screen_height - 50, 150, 30)
                    if button_rect.collidepoint(pygame.mouse.get_pos()):
                        world.reset_world()

            elif event.type == pygame.FINGERDOWN:
                world.show_mobile_controls = True

            elif event.type == pygame.KEYDOWN:
                if world.show_rules:
                    world.show_rules = False
                    continue
                if world.game_over:
                    continue
                key_action = {
                    pygame.K_UP:    'up',
                    pygame.K_DOWN:  'down',
                    pygame.K_LEFT:  'left',
                    pygame.K_RIGHT: 'right',
                    pygame.K_SPACE: 'shoot',
                    pygame.K_r:     'scout',
                }
                if event.key in key_action:
                    process_game_action(world, key_action[event.key])

        try:
            draw_game(world)
            if world.show_rules:
                draw_rules_screen()
        except Exception as _re:
            import traceback
            _tb3 = traceback.format_exc()
            print("DRAW ERROR:", _tb3)
            screen.fill((0, 0, 0))
            _ef3 = pygame.font.Font(None, 22)
            _y3 = 10
            for _line3 in (["DRAW ERROR:"] + _tb3.splitlines())[:30]:
                screen.blit(_ef3.render(_line3[:90], True, (255, 80, 80)), (10, _y3))
                _y3 += 22

        pygame.display.flip()
        await asyncio.sleep(0)
        clock.tick(30)

    pygame.quit()


def _report_fatal(tb_text):
    """Make a fatal startup error impossible to miss in the browser:
    write it to the page title and a big on-page banner, and also try
    to paint it on the pygame canvas."""
    print("FATAL:", tb_text)
    # 1) Surface to the DOM / tab title so it's readable without a console
    try:
        import platform as _pf
        _doc = _pf.window.document
        _doc.title = "WUMPUS ERROR: " + tb_text.strip().splitlines()[-1][:80]
        _banner = _doc.createElement("div")
        _banner.style.cssText = (
            "position:fixed;left:0;top:0;right:0;z-index:99999;"
            "background:#900;color:#fff;font:14px monospace;"
            "white-space:pre-wrap;padding:12px;max-height:60vh;overflow:auto;")
        _banner.textContent = "WUMPUS WORLD FAILED TO START:\n\n" + tb_text
        _doc.body.appendChild(_banner)
    except Exception as _e:
        print("(could not write DOM banner:", _e, ")")
    # 2) Try to paint on the canvas too
    try:
        _scr = pygame.display.get_surface()
        if _scr is not None:
            _scr.fill((0, 0, 0))
            _f = pygame.font.Font(None, 22)
            _yy = 10
            for _ln in (["WUMPUS WORLD FAILED TO START:"] + tb_text.splitlines())[:30]:
                _scr.blit(_f.render(_ln[:90], True, (255, 90, 90)), (10, _yy))
                _yy += 22
            pygame.display.flip()
    except Exception as _e2:
        print("(could not paint canvas error:", _e2, ")")


async def _guarded_main():
    try:
        await main()
    except BaseException:
        import traceback
        _report_fatal(traceback.format_exc())
        # keep the runtime alive so the banner stays visible
        while True:
            await asyncio.sleep(1)

asyncio.run(_guarded_main())