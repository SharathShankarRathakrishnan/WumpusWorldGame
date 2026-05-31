/* Wumpus World — JavaScript / HTML5 Canvas port of wumpus.py
   Faithful reimplementation of the Pygame original by Sharath Shankar Rathakrishnan.
   Runs natively in any browser: no WebAssembly, no external CDN, instant load. */

"use strict";

/* ---------------------------------------------------------------- constants */
const BASE_GRID_SIZE = 6;
const MAX_GRID_SIZE  = 10;
const CELL_SIZE      = 80;   // reference cell size (matches the desktop .py version)

const OFF_WHITE  = "rgb(245,245,240)";
const BLACK      = "rgb(0,0,0)";
const RED        = "rgb(255,0,0)";
const BLUE       = "rgb(0,0,255)";
const WHITE      = "rgb(255,255,255)";
const DARK_GOLD  = "rgb(184,134,11)";
const PARCHMENT       = [235, 222, 195];
const PARCHMENT_BORDER = "rgb(180,160,130)";

// Per-image target sizes at the reference cell size, mirroring IMAGE_SIZES in
// the original. Entities scale proportionally with the live cell size.
const IMAGE_SIZES = {
  agent:  [30, 45],
  gold:   [60, 40],
  wumpus: [50, 50],
  pit:    [50, 40],
  stench: [30, 70],
  breeze: [75, 30],
};

const RULES_TEXT = [
  "WUMPUS WORLD - RULES",
  "",
  "OBJECTIVE: Find the gold and return to the start position",
  "",
  "DANGERS:",
  "- Avoid the Wumpus (monster) - you will be eaten if you enter its cell",
  "- Avoid pits - you will fall in if you enter a pit cell",
  "",
  "PERCEPTIONS:",
  "- Stench = Wumpus is in an adjacent cell",
  "- Breeze = Pit is in an adjacent cell",
  "- Perceptions only appear in cells you have explored",
  "",
  "WUMPUS BEHAVIOR:",
  "- The Wumpus moves every 3 turns you take",
  "- It prefers to move to unexplored areas",
  "- The screen shakes when the Wumpus moves - stay alert!",
  "",
  "CONTROLS:",
  "- Arrow keys / D-pad: Move your agent up/down/left/right",
  "- SPACE / SHOOT button: Shoot arrow at the Wumpus",
  "- R / SCOUT button: Activate scout mode (reveals adjacent cells for 1 second)",
  "- Left-click / tap cell: Mark/unmark cells with danger warning (!)",
  "",
  "SCOUT MODE:",
  "- 10 second cooldown between uses",
  "- Timer pauses when viewing these rules",
  "",
  "Click anywhere or press any key to continue...",
];

/* ---------------------------------------------------------------- helpers */
const key = (c, r) => c + "," + r;
const nowMs = () => performance.now();
const nowS  = () => performance.now() / 1000;
const DIRS  = [[0, 1], [1, 0], [0, -1], [-1, 0]];

/* ---------------------------------------------------------------- canvas / viewport */
const canvas = document.getElementById("game");
const ctx = canvas.getContext("2d");

let VW = window.innerWidth;   // logical viewport width  (CSS px)
let VH = window.innerHeight;  // logical viewport height (CSS px)
let DPR = window.devicePixelRatio || 1;

function resizeCanvas() {
  DPR = window.devicePixelRatio || 1;
  VW = window.innerWidth;
  VH = window.innerHeight;
  canvas.width  = Math.round(VW * DPR);
  canvas.height = Math.round(VH * DPR);
  canvas.style.width  = VW + "px";
  canvas.style.height = VH + "px";
  ctx.setTransform(DPR, 0, 0, DPR, 0, 0); // draw in logical CSS px
}

// Reserved vertical space for the HUD (top) and the New Game button / touch controls (bottom).
function topHudHeight()  { return 90; }
function bottomHeight(world) { return world.show_mobile_controls ? 250 : 90; }

// Fullscreen behaviour: the grid scales UP to fill the available space.
function get_cell_size(world) {
  const availW = VW - 40;
  const availH = VH - topHudHeight() - bottomHeight(world);
  const cs = Math.floor(Math.min(availW / world.grid_size, availH / world.grid_size));
  return Math.max(36, Math.min(cs, 160));
}

/* ---------------------------------------------------------------- assets */
const IMAGE_FILES = {
  agent: "agent.png", gold: "gold.png", wumpus: "wumpus.png", pit: "pit.png",
  stench: "stench.png", breeze: "breeze.png",
  game_over: "game_over.png", victory: "victory.png",
  rock_button: "rock_button.jpg", rules: "rules.png", gold_plate: "gold_plate.png",
};
const images = {};

const SOUND_FILES = {
  footstep:        ["sounds/footstep.ogg", 1.0],
  gold_collected:  ["sounds/gold_collected.ogg", 1.5],
  arrow_kill:      ["sounds/arrow_sound+monster_dying.ogg", 1.5],
  arrow_miss:      ["sounds/arrow_sound.ogg", 1.5],
  monster_footstep:["sounds/monster_footsteps.ogg", 1.5],
  monster_scream:  ["sounds/monster_scream.ogg", 2.5],
  falling_scream:  ["sounds/falling_scream.ogg", 1.25],
};
const sounds = {};

function loadImage(src) {
  return new Promise((resolve) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => resolve(null); // fail silently, like the original
    img.src = src;
  });
}

async function loadAllAssets() {
  const imgJobs = Object.entries(IMAGE_FILES).map(async ([name, file]) => {
    images[name] = await loadImage(file);
  });
  for (const [name, [file, rate]] of Object.entries(SOUND_FILES)) {
    sounds[name] = { url: file, rate };
  }
  await Promise.all(imgJobs);
  if (document.fonts && document.fonts.load) {
    try { await document.fonts.load("24px VT323"); } catch (e) {}
  }
}

function play(name) {
  const s = sounds[name];
  if (!s) return;
  try {
    const a = new Audio(s.url);
    a.playbackRate = s.rate;
    a.play().catch(() => {});
  } catch (e) {}
}

/* ---------------------------------------------------------------- fonts */
const F = {
  base:  '24px "VT323", monospace',
  small: '20px "VT323", monospace',
  large: '32px "VT323", monospace',
  title: '48px "VT323", monospace',
  tiny:  '17px monospace',
};
function setFont(f) { ctx.font = f; }
function textWidth(str, f) { setFont(f); return ctx.measureText(str).width; }
function drawText(str, x, y, color, f, align = "left", baseline = "top") {
  setFont(f);
  ctx.fillStyle = color;
  ctx.textAlign = align;
  ctx.textBaseline = baseline;
  ctx.fillText(str, x, y);
}

/* ---------------------------------------------------------------- GameWorld */
class GameWorld {
  constructor() {
    this.grid_size = BASE_GRID_SIZE;
    this.marked_cells = new Set();
    this.scout_mode = false;
    this.scout_cooldown = 10;
    this.scout_start_time = nowS();
    this.scout_visible_time = 0;
    this.scout_adjacent_cells = new Set();
    this.show_rules = true;
    this.scout_time_paused = false;
    this.scout_pause_start = 0;
    this.new_game_button_pressed = false;
    this.show_mobile_controls = false;
    this.cell_size = CELL_SIZE;
    this.reset_world();
  }

  inBounds(x, y) { return x >= 0 && x < this.grid_size && y >= 0 && y < this.grid_size; }

  _path_exists_a_star() {
    const start = [this.agent_pos[0], this.agent_pos[1]];
    const goal = this.gold_pos;
    const pitSet = new Set(this.pits.map(p => key(p[0], p[1])));
    const h = (a) => Math.abs(a[0] - goal[0]) + Math.abs(a[1] - goal[1]);
    const open = [[h(start), start]];
    const g = { [key(start[0], start[1])]: 0 };
    while (open.length) {
      open.sort((a, b) => a[0] - b[0]);
      const [, cur] = open.shift();
      if (cur[0] === goal[0] && cur[1] === goal[1]) return true;
      for (const [dx, dy] of DIRS) {
        const nx = cur[0] + dx, ny = cur[1] + dy;
        if (!this.inBounds(nx, ny)) continue;
        if (pitSet.has(key(nx, ny))) continue;
        const tg = g[key(cur[0], cur[1])] + 1;
        const k = key(nx, ny);
        if (!(k in g) || tg < g[k]) {
          g[k] = tg;
          open.push([tg + Math.abs(nx - goal[0]) + Math.abs(ny - goal[1]), [nx, ny]]);
        }
      }
    }
    return false;
  }

  calculate_optimal_moves() {
    const start = [0, this.grid_size - 1];
    const goal = this.gold_pos;
    const pitSet = new Set(this.pits.map(p => key(p[0], p[1])));
    const h = (a) => Math.abs(a[0] - goal[0]) + Math.abs(a[1] - goal[1]);
    const open = [[h(start), start]];
    const g = { [key(start[0], start[1])]: 0 };
    const came = {};
    while (open.length) {
      open.sort((a, b) => a[0] - b[0]);
      const [, cur] = open.shift();
      if (cur[0] === goal[0] && cur[1] === goal[1]) break;
      for (const [dx, dy] of DIRS) {
        const nx = cur[0] + dx, ny = cur[1] + dy;
        if (!this.inBounds(nx, ny)) continue;
        if (pitSet.has(key(nx, ny))) continue;
        const tg = g[key(cur[0], cur[1])] + 1;
        const k = key(nx, ny);
        if (!(k in g) || tg < g[k]) {
          g[k] = tg;
          came[k] = key(cur[0], cur[1]);
          open.push([tg + Math.abs(nx - goal[0]) + Math.abs(ny - goal[1]), [nx, ny]]);
        }
      }
    }
    const goalK = key(goal[0], goal[1]);
    const startK = key(start[0], start[1]);
    let path = 0;
    if (goalK in came) {
      let cur = goalK;
      while (cur !== startK) { path++; cur = came[cur]; }
    }
    return path > 0 ? path * 2 : Infinity;
  }

  reset_world(new_size = null) {
    this.grid_size = (new_size == null) ? BASE_GRID_SIZE : new_size;
    this.agent_pos = [0, this.grid_size - 1];
    this.move_count = 0;
    this.player_move_count = 0;
    this.has_gold = false;
    this.has_arrow = true;
    this.wumpus_alive = true;
    this.game_over = false;
    this.game_over_message = [];
    this.gold_collected_message = "";
    this.wumpus_killed_message = "";
    this.arrow_miss_message = "";
    this.explored = new Set();
    this.explored.add(key(0, this.grid_size - 1));
    this.show_continue = false;
    this.optimal_moves = 0;
    this.marked_cells = new Set();
    this.scout_mode = false;
    this.scout_cooldown = 10;
    this.scout_start_time = nowS();
    this.scout_visible_time = 0;
    this.scout_adjacent_cells = new Set();
    this.new_game_button_pressed = false;
    this.shake_start_time = 0;
    this.shake_duration = 450;
    this.shake_amplitude = 9;
    this.gold_collect_anim_start = 0;
    this.gold_collect_anim_duration = 650;

    const rint = (n) => Math.floor(Math.random() * n);

    while (true) {
      const x = rint(this.grid_size), y = rint(this.grid_size);
      if (x !== this.agent_pos[0] || y !== this.agent_pos[1]) { this.wumpus_pos = [x, y]; break; }
    }
    while (true) {
      const x = rint(this.grid_size), y = rint(this.grid_size);
      if ((x !== this.agent_pos[0] || y !== this.agent_pos[1]) &&
          (x !== this.wumpus_pos[0] || y !== this.wumpus_pos[1])) { this.gold_pos = [x, y]; break; }
    }

    const num_pits = 3 + 4 * (this.grid_size - BASE_GRID_SIZE);
    this.pits = [];
    const sx = 0, sy = this.grid_size - 1;
    const adjStart = new Set([key(sx + 1, sy), key(sx, sy - 1), key(sx, sy + 1), key(sx - 1, sy)]);

    let attempts = 0;
    const maxAttempts = 100;
    while (this.pits.length < num_pits && attempts < maxAttempts) {
      attempts++;
      const x = rint(this.grid_size), y = rint(this.grid_size);
      const k = key(x, y);
      const isAgent  = (x === this.agent_pos[0] && y === this.agent_pos[1]);
      const isWumpus = (x === this.wumpus_pos[0] && y === this.wumpus_pos[1]);
      const isGold   = (x === this.gold_pos[0] && y === this.gold_pos[1]);
      const isPit    = this.pits.some(p => p[0] === x && p[1] === y);
      if (!isAgent && !isWumpus && !isGold && !isPit && !adjStart.has(k)) {
        this.pits.push([x, y]);
        if (!this._path_exists_a_star()) this.pits.pop();
      }
    }

    this.optimal_moves = this.calculate_optimal_moves();
    this.update_perceptions();
  }

  activate_scout_mode() {
    const t = nowS();
    if (t - this.scout_start_time >= 10 && this.scout_cooldown <= 0) {
      this.scout_mode = true;
      this.scout_visible_time = t;
      this.scout_cooldown = 10;
      this.scout_start_time = t;
      const [x, y] = this.agent_pos;
      this.scout_adjacent_cells = new Set();
      for (const [dx, dy] of DIRS) {
        const nx = x + dx, ny = y + dy;
        if (this.inBounds(nx, ny)) {
          this.scout_adjacent_cells.add(key(nx, ny));
          this.explored.add(key(nx, ny));
        }
      }
    }
  }

  move_wumpus() {
    if (!this.wumpus_alive) return;
    const [wx, wy] = this.wumpus_pos;
    const candidates = [];
    for (const [dx, dy] of DIRS) {
      const nx = wx + dx, ny = wy + dy;
      if (!this.inBounds(nx, ny)) continue;
      if (this.pits.some(p => p[0] === nx && p[1] === ny)) continue;
      const weight = this.explored.has(key(nx, ny)) ? 1 : 3;
      for (let i = 0; i < weight; i++) candidates.push([nx, ny]);
    }
    if (candidates.length) {
      let safe = candidates.filter(c => !(c[0] === this.agent_pos[0] && c[1] === this.agent_pos[1]));
      if (!safe.length) safe = candidates;
      const np = safe[Math.floor(Math.random() * safe.length)];
      if (np[0] !== this.wumpus_pos[0] || np[1] !== this.wumpus_pos[1]) {
        this.wumpus_pos = np;
        this.update_perceptions();
        this.shake_start_time = nowMs();
        play("monster_footstep");
      }
    }
  }

  update_perceptions() {
    this.stench = new Set();
    this.breeze = new Set();
    if (this.wumpus_alive) {
      const [wx, wy] = this.wumpus_pos;
      for (const [dx, dy] of DIRS) {
        const nx = wx + dx, ny = wy + dy;
        if (this.inBounds(nx, ny)) this.stench.add(key(nx, ny));
      }
    }
    for (const [px, py] of this.pits) {
      for (const [dx, dy] of DIRS) {
        const nx = px + dx, ny = py + dy;
        if (this.inBounds(nx, ny)) this.breeze.add(key(nx, ny));
      }
    }
  }

  get_current_perceptions() {
    const cp = { stench: new Set(), breeze: new Set() };
    for (const cell of this.explored) {
      if (this.stench.has(cell)) cp.stench.add(cell);
      if (this.breeze.has(cell)) cp.breeze.add(cell);
    }
    return cp;
  }
}

/* ---------------------------------------------------------------- actions */
function process_game_action(world, action) {
  if (world.game_over || world.show_rules) return;
  let [x, y] = world.agent_pos;
  let moved = false, shot = false;

  if (action === "up" && y > 0)                          { world.agent_pos[1]--; moved = true; }
  else if (action === "down" && y < world.grid_size - 1) { world.agent_pos[1]++; moved = true; }
  else if (action === "left" && x > 0)                   { world.agent_pos[0]--; moved = true; }
  else if (action === "right" && x < world.grid_size-1)  { world.agent_pos[0]++; moved = true; }
  else if (action === "shoot" && world.has_arrow) {
    world.has_arrow = false;
    const [wx, wy] = world.wumpus_pos;
    const [ax, ay] = world.agent_pos;
    if ((Math.abs(ax - wx) === 1 && ay === wy) || (Math.abs(ay - wy) === 1 && ax === wx)) {
      world.wumpus_alive = false;
      world.wumpus_killed_message = "You killed the Wumpus!";
      play("arrow_kill");
      world.update_perceptions();
    } else {
      world.arrow_miss_message = "Arrow missed!";
      play("arrow_miss");
    }
    shot = true;
    world.move_count++;
    world.player_move_count++;
    if (world.player_move_count % 3 === 0) world.move_wumpus();
  } else if (action === "scout") {
    world.activate_scout_mode();
    return;
  }

  if (moved || shot) {
    if (moved) {
      world.arrow_miss_message = "";
      play("footstep");
      world.move_count++;
      world.player_move_count++;
      world.explored.add(key(world.agent_pos[0], world.agent_pos[1]));
      if (world.player_move_count % 3 === 0) world.move_wumpus();
    }
    const cx = world.agent_pos[0], cy = world.agent_pos[1];
    const onPit = world.pits.some(p => p[0] === cx && p[1] === cy);

    if (world.wumpus_alive && cx === world.wumpus_pos[0] && cy === world.wumpus_pos[1]) {
      world.game_over = true;
      play("monster_scream");
      world.game_over_message = ["You were eaten by the Wumpus!", "Click anywhere to start a new game"];
    } else if (onPit) {
      world.game_over = true;
      play("falling_scream");
      world.game_over_message = ["You fell into a pit!", "Click anywhere to start a new game"];
    } else if (cx === world.gold_pos[0] && cy === world.gold_pos[1] && !world.has_gold) {
      world.has_gold = true;
      play("gold_collected");
      world.gold_collected_message = "Gold collected! Return to start!";
      world.wumpus_killed_message = "";
      world.gold_collect_anim_start = nowMs();
    } else if (cx === 0 && cy === world.grid_size - 1 && world.has_gold) {
      world.game_over = true;
      world.game_over_message = ["You won! Gold safely returned!", "Click anywhere to start a new game"];
    }
  }
}

/* ---------------------------------------------------------------- mobile controls */
function get_mobile_rects() {
  const btn = 62, gap = 8, cx = 115, cy = VH - 170;
  const aw = 92, ah = 58, agap = 12, ay = VH - 130;
  return {
    up:    { x: cx - btn / 2,        y: cy - btn - gap / 2, w: btn, h: btn },
    down:  { x: cx - btn / 2,        y: cy + gap / 2,       w: btn, h: btn },
    left:  { x: cx - btn - gap / 2,  y: cy - btn / 2,       w: btn, h: btn },
    right: { x: cx + gap / 2,        y: cy - btn / 2,       w: btn, h: btn },
    shoot: { x: VW - 2 * aw - agap - 15, y: ay, w: aw, h: ah },
    scout: { x: VW - aw - 15,            y: ay, w: aw, h: ah },
  };
}

function rectHit(r, px, py) {
  return px >= r.x && px < r.x + r.w && py >= r.y && py < r.y + r.h;
}

function roundRect(x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

function draw_mobile_controls(world) {
  if (!world.show_mobile_controls || world.game_over || world.show_rules) return;
  const rects = get_mobile_rects();
  const BASE = { up:"rgb(72,67,63)",down:"rgb(72,67,63)",left:"rgb(72,67,63)",right:"rgb(72,67,63)",
                 shoot:"rgb(130,45,45)",scout:"rgb(85,85,30)" };
  const LABELS = { up:"▲", down:"▼", left:"◄", right:"►", shoot:"SHOOT", scout:"SCOUT" };
  for (const k of Object.keys(rects)) {
    const r = rects[k];
    ctx.fillStyle = BASE[k];
    roundRect(r.x, r.y, r.w, r.h, 10); ctx.fill();
    ctx.lineWidth = 2; ctx.strokeStyle = "rgb(35,33,30)";
    roundRect(r.x, r.y, r.w, r.h, 10); ctx.stroke();
    const f = (k === "shoot" || k === "scout") ? F.base : F.large;
    drawText(LABELS[k], r.x + r.w / 2, r.y + r.h / 2, "rgb(240,235,220)", f, "center", "middle");
  }
}

/* ---------------------------------------------------------------- rendering */
// Draw a grid entity at the proportional size the desktop .py version uses.
function drawEntity(name, gx, gy, gridX, gridY, cs) {
  const img = images[name];
  if (!img) return;
  const base = IMAGE_SIZES[name] || [cs - 20, cs - 20];
  const factor = cs / CELL_SIZE;
  let w = base[0] * factor, h = base[1] * factor;
  const maxDim = cs - 8;
  if (w > maxDim || h > maxDim) { const s = maxDim / Math.max(w, h); w *= s; h *= s; }
  const x = gridX + gx * cs + (cs - w) / 2;
  const y = gridY + gy * cs + (cs - h) / 2;
  ctx.drawImage(img, x, y, w, h);
}

function draw_game(world) {
  ctx.fillStyle = OFF_WHITE;
  ctx.fillRect(0, 0, VW, VH);

  const sw = VW, sh = VH;
  const t = nowS();

  // Scout cooldown timer with pause-during-rules behaviour
  if (world.show_rules) {
    if (!world.scout_time_paused) { world.scout_time_paused = true; world.scout_pause_start = t; }
  } else {
    if (world.scout_time_paused) {
      world.scout_start_time += t - world.scout_pause_start;
      world.scout_time_paused = false;
    }
    if (world.scout_cooldown > 0) {
      world.scout_cooldown = Math.max(0, 10 - (t - world.scout_start_time));
    }
  }
  if (world.scout_mode && t - world.scout_visible_time >= 1) world.scout_mode = false;

  const animMs = nowMs();

  // screen shake
  let shakeX = 0, shakeY = 0;
  const shakeElapsed = animMs - world.shake_start_time;
  if (shakeElapsed > 0 && shakeElapsed < world.shake_duration) {
    const progress = shakeElapsed / world.shake_duration;
    const amp = world.shake_amplitude * (1 - progress);
    shakeX = Math.round(amp * Math.sin(shakeElapsed * 0.18));
    shakeY = Math.round(amp * Math.cos(shakeElapsed * 0.23));
  }

  if (!world.game_over) {
    const cs = get_cell_size(world);
    world.cell_size = cs;
    const gw = world.grid_size * cs, gh = world.grid_size * cs;
    const topHud = topHudHeight();
    const availH = sh - topHud - bottomHeight(world);
    const gridX = (sw - gw) / 2 + shakeX;
    const gridY = topHud + (availH - gh) / 2 + shakeY;
    world._gridX = gridX; world._gridY = gridY;

    const cp = world.get_current_perceptions();
    const PERC = Math.max(14, Math.floor(cs / 3));
    const coordFont = cs >= 56 ? F.small : F.tiny;

    for (let row = 0; row < world.grid_size; row++) {
      for (let col = 0; col < world.grid_size; col++) {
        const rx = gridX + col * cs, ry = gridY + row * cs;

        if (col === 0 && row === world.grid_size - 1) { ctx.fillStyle = "rgb(180,230,180)"; ctx.fillRect(rx, ry, cs, cs); }
        if (col === world.agent_pos[0] && row === world.agent_pos[1]) { ctx.fillStyle = "rgb(220,240,255)"; ctx.fillRect(rx, ry, cs, cs); }
        if (!world.explored.has(key(col, row))) { ctx.fillStyle = "rgba(100,100,110,0.47)"; ctx.fillRect(rx, ry, cs, cs); }

        ctx.lineWidth = 1; ctx.strokeStyle = BLACK; ctx.strokeRect(rx + 0.5, ry + 0.5, cs - 1, cs - 1);

        if (world.scout_mode && world.scout_adjacent_cells.has(key(col, row))) {
          ctx.fillStyle = "rgba(255,255,0,0.59)"; ctx.fillRect(rx, ry, cs, cs);
        }

        if (cs >= 40) drawText(`${col + 1},${world.grid_size - row}`, rx + 3, ry + 2, BLACK, coordFont);

        if (world.marked_cells.has(key(col, row))) drawText("!", rx + cs - 14, ry - 2, RED, F.small);

        if (cp.stench.has(key(col, row)) && images.stench)
          ctx.drawImage(images.stench, rx + 2, ry + cs - PERC - 2, PERC, PERC);
        if (cp.breeze.has(key(col, row)) && images.breeze)
          ctx.drawImage(images.breeze, rx + cs - PERC - 2, ry + cs - PERC - 2, PERC, PERC);
      }
    }

    // gold (with pickup anim)
    const [gx, gy] = world.gold_pos;
    const goldElapsed = animMs - world.gold_collect_anim_start;
    if (!world.has_gold && world.explored.has(key(gx, gy))) {
      drawEntity("gold", gx, gy, gridX, gridY, cs);
    } else if (world.has_gold && world.gold_collect_anim_start > 0 && goldElapsed < world.gold_collect_anim_duration && images.gold) {
      const progress = goldElapsed / world.gold_collect_anim_duration;
      const scale = 1.0 + 1.2 * progress;
      const factor = cs / CELL_SIZE;
      const bw = IMAGE_SIZES.gold[0] * factor, bh = IMAGE_SIZES.gold[1] * factor;
      const w = Math.max(1, bw * scale), h = Math.max(1, bh * scale);
      const ax = gridX + gx * cs + (cs - w) / 2, ay = gridY + gy * cs + (cs - h) / 2;
      ctx.save();
      ctx.globalAlpha = Math.max(0, 1 - progress);
      ctx.drawImage(images.gold, ax, ay, w, h);
      ctx.restore();
    }

    if (world.wumpus_alive && world.explored.has(key(world.wumpus_pos[0], world.wumpus_pos[1])))
      drawEntity("wumpus", world.wumpus_pos[0], world.wumpus_pos[1], gridX, gridY, cs);

    for (const [px, py] of world.pits)
      if (world.explored.has(key(px, py))) drawEntity("pit", px, py, gridX, gridY, cs);

    drawEntity("agent", world.agent_pos[0], world.agent_pos[1], gridX, gridY, cs);

    if (world.gold_collected_message)
      drawText(world.gold_collected_message, sw / 2, 20, DARK_GOLD, F.large, "center");
    if (world.wumpus_killed_message)
      drawText(world.wumpus_killed_message, sw / 2, 50, "rgb(200,50,50)", F.large, "center");
    if (world.arrow_miss_message)
      drawText(world.arrow_miss_message, sw / 2, 50, "rgb(180,80,0)", F.large, "center");

    // Top-right status: Arrows / Pits / Scout (single pit counter, matches .py)
    drawText(`Arrows: ${world.has_arrow ? 1 : 0}`, sw - 100, 20, BLACK, F.small);
    drawText(`Pits: ${world.pits.length}`, sw - 100, 50, BLUE, F.small);
    if (world.scout_cooldown > 0)
      drawText(`Scout: ${Math.floor(world.scout_cooldown)}s`, sw - 100, 80, "rgb(200,0,0)", F.small);
    else
      drawText("Scout: Ready (R)", sw - 100, 80, "rgb(0,150,0)", F.small);

    // Rules button (with hover enlarge)
    const rb = { x: sw - 200, y: 20, w: 80, h: 25 };
    const rbHover = rectHit(rb, mouse.x, mouse.y);
    if (images.rules) {
      if (rbHover) ctx.drawImage(images.rules, rb.x - 2, rb.y - 2, rb.w + 5, rb.h + 5);
      else         ctx.drawImage(images.rules, rb.x, rb.y, rb.w, rb.h);
    } else {
      ctx.fillStyle = rbHover ? "rgb(130,180,230)" : "rgb(100,150,200)";
      ctx.fillRect(rb.x, rb.y, rb.w, rb.h);
    }
    drawText("Rules", rb.x + rb.w / 2, rb.y + rb.h / 2, BLACK, F.small, "center", "middle");

    draw_mobile_controls(world);

    // New Game button (with hover enlarge)
    const nb = { x: sw / 2 - 75, y: sh - 50, w: 150, h: 30 };
    const nbHover = rectHit(nb, mouse.x, mouse.y);
    if (images.rock_button) {
      if (nbHover) ctx.drawImage(images.rock_button, nb.x - 2, nb.y - 2, nb.w + 5, nb.h + 5);
      else         ctx.drawImage(images.rock_button, nb.x, nb.y, nb.w, nb.h);
    } else {
      ctx.fillStyle = nbHover ? "rgb(120,120,120)" : "rgb(100,100,100)";
      ctx.fillRect(nb.x, nb.y, nb.w, nb.h);
    }
    drawText("New Game", nb.x + nb.w / 2, nb.y + nb.h / 2, BLACK, F.base, "center", "middle");
  } else {
    // Game over / victory overlay
    ctx.fillStyle = "rgb(0,0,0)";
    ctx.fillRect(0, 0, sw, sh);

    const isVictory = world.game_over_message[0].toLowerCase().includes("won");
    let endImg, glow;
    if (isVictory) {
      endImg = images.victory;
      if (world.grid_size < MAX_GRID_SIZE) world.show_continue = true;
      glow = [255, 215, 0];
    } else {
      endImg = images.game_over;
      world.show_continue = false;
      glow = [200, 0, 0];
    }

    const pulse = 0.5 + 0.5 * Math.sin(animMs * 0.005);
    const glowAlpha = Math.floor(60 + 120 * pulse);
    for (let thickness = 12; thickness > 0; thickness -= 3) {
      ctx.strokeStyle = `rgba(${glow[0]},${glow[1]},${glow[2]},${(glowAlpha / thickness) / 255})`;
      ctx.lineWidth = thickness * 3;
      ctx.strokeRect((thickness * 3) / 2, (thickness * 3) / 2, sw - thickness * 3, sh - thickness * 3);
    }

    const ew = 400, eh = 200;
    const imgX = (sw - ew) / 2, imgY = (sh - eh) / 2 - 50;
    if (endImg) ctx.drawImage(endImg, imgX, imgY, ew, eh);

    let yOff = imgY + eh + 20;
    if (isVictory) {
      drawText(`Optimal moves: ${world.optimal_moves}`, sw / 2, yOff, WHITE, F.large, "center"); yOff += 30;
      drawText(`Your moves: ${world.move_count}`, sw / 2, yOff, WHITE, F.large, "center"); yOff += 30;
      if (world.optimal_moves > 0 && isFinite(world.optimal_moves)) {
        const eff = (world.optimal_moves / world.move_count) * 100;
        drawText(`Efficiency: ${Math.min(100, eff).toFixed(1)}%`, sw / 2, yOff, WHITE, F.large, "center"); yOff += 30;
      }
    }
    for (const line of world.game_over_message) {
      drawText(line, sw / 2, yOff, WHITE, F.large, "center"); yOff += 30;
    }

    if (world.show_continue) {
      const cr = { x: sw / 2 - 100, y: sh - 110, w: 200, h: 50 };
      const crHover = rectHit(cr, mouse.x, mouse.y);
      if (images.gold_plate) {
        if (crHover) ctx.drawImage(images.gold_plate, cr.x - 4, cr.y - 2, cr.w + 8, cr.h + 4);
        else         ctx.drawImage(images.gold_plate, cr.x, cr.y, cr.w, cr.h);
      } else {
        ctx.fillStyle = crHover ? "rgb(230,180,0)" : "rgb(200,150,0)";
        ctx.fillRect(cr.x, cr.y, cr.w, cr.h);
      }
      drawText("Continue", cr.x + cr.w / 2, cr.y + cr.h / 2, BLACK, F.large, "center", "middle");
    }
  }

  // Always-on HUD (Moves + Level only; pit count lives top-right)
  drawText(`Moves: ${world.move_count}`, 20, 20, RED, F.base);
  const mw = textWidth(`Moves: ${world.move_count}`, F.base);
  drawText(`Level: ${world.grid_size}x${world.grid_size}`, 20 + mw + 10, 20, BLUE, F.base);

  if (world.show_rules) draw_rules_screen(world);
}

function draw_rules_screen(world) {
  const sw = VW, sh = VH;
  ctx.fillStyle = "rgba(50,50,50,0.90)";
  ctx.fillRect(0, 0, sw, sh);

  let needed = 30;
  for (const line of RULES_TEXT) {
    if (!line) needed += 10;
    else if (line.includes("WUMPUS WORLD")) needed += 48 + 6;
    else if (line.endsWith(":")) needed += 24 + 6;
    else needed += 17 + 6;
  }
  needed += 20;

  const panelW = 720;
  const panelH = Math.min(needed, sh - 40);
  const panelX = (sw - panelW) / 2, panelY = (sh - panelH) / 2;

  ctx.fillStyle = `rgb(${PARCHMENT[0]},${PARCHMENT[1]},${PARCHMENT[2]})`;
  ctx.fillRect(panelX, panelY, panelW, panelH);
  ctx.lineWidth = 4; ctx.strokeStyle = PARCHMENT_BORDER; ctx.strokeRect(panelX, panelY, panelW, panelH);
  ctx.lineWidth = 2; ctx.strokeStyle = "rgb(100,85,70)"; ctx.strokeRect(panelX + 3, panelY + 3, panelW - 6, panelH - 6);

  let y = panelY + 20;
  for (const line of RULES_TEXT) {
    if (!line) { y += 10; continue; }
    let f, color, lh;
    if (line.includes("WUMPUS WORLD")) { f = F.title; color = "rgb(150,30,30)"; lh = 48; }
    else if (line.endsWith(":"))       { f = F.base;  color = "rgb(50,50,120)"; lh = 24; }
    else                               { f = F.tiny;  color = "rgb(40,40,40)";  lh = 17; }
    drawText(line, sw / 2, y, color, f, "center");
    y += lh + 5;
  }
}

/* ---------------------------------------------------------------- input */
let world;
const mouse = { x: -1, y: -1 };

function canvasPos(evt) {
  const rect = canvas.getBoundingClientRect();
  const scaleX = VW / rect.width;
  const scaleY = VH / rect.height;
  const cx = (evt.clientX ?? (evt.touches && evt.touches[0] && evt.touches[0].clientX)) - rect.left;
  const cy = (evt.clientY ?? (evt.touches && evt.touches[0] && evt.touches[0].clientY)) - rect.top;
  return [cx * scaleX, cy * scaleY];
}

function handlePointerDown(px, py) {
  const sw = VW, sh = VH;

  if (world.show_rules) { world.show_rules = false; return; }

  if (world.game_over) {
    if (world.show_continue) {
      const cr = { x: sw / 2 - 100, y: sh - 110, w: 200, h: 50 };
      if (rectHit(cr, px, py)) { world.reset_world(world.grid_size + 1); return; }
    }
    world.reset_world();
    return;
  }

  const rb = { x: sw - 200, y: 20, w: 80, h: 25 };
  if (rectHit(rb, px, py)) { world.show_rules = true; return; }

  const cs = world.cell_size || CELL_SIZE;
  const gw = world.grid_size * cs, gh = world.grid_size * cs;
  const gridX = world._gridX, gridY = world._gridY;
  if (px >= gridX && px < gridX + gw && py >= gridY && py < gridY + gh) {
    const col = Math.floor((px - gridX) / cs);
    const row = Math.floor((py - gridY) / cs);
    const k = key(col, row);
    if (world.marked_cells.has(k)) world.marked_cells.delete(k);
    else world.marked_cells.add(k);
  }

  const nb = { x: sw / 2 - 75, y: sh - 50, w: 150, h: 30 };
  if (rectHit(nb, px, py)) { world.reset_world(); return; }

  if (world.show_mobile_controls) {
    const rects = get_mobile_rects();
    for (const k of Object.keys(rects)) {
      if (rectHit(rects[k], px, py)) { process_game_action(world, k); return; }
    }
  }
}

const KEY_ACTION = {
  ArrowUp: "up", ArrowDown: "down", ArrowLeft: "left", ArrowRight: "right",
  " ": "shoot", Spacebar: "shoot", r: "scout", R: "scout",
};

function setupInput() {
  canvas.addEventListener("mousemove", (e) => {
    const [px, py] = canvasPos(e);
    mouse.x = px; mouse.y = py;
  });

  canvas.addEventListener("mousedown", (e) => {
    const [px, py] = canvasPos(e);
    handlePointerDown(px, py);
  });

  canvas.addEventListener("touchstart", (e) => {
    e.preventDefault();
    world.show_mobile_controls = true;
    const [px, py] = canvasPos(e);
    mouse.x = px; mouse.y = py;
    handlePointerDown(px, py);
  }, { passive: false });

  window.addEventListener("keydown", (e) => {
    if (world.show_rules) { world.show_rules = false; e.preventDefault(); return; }
    if (world.game_over) return;
    const action = KEY_ACTION[e.key];
    if (action) { process_game_action(world, action); e.preventDefault(); }
  });

  window.addEventListener("resize", resizeCanvas);
}

/* ---------------------------------------------------------------- main loop */
function frame() {
  try {
    draw_game(world);
  } catch (err) {
    ctx.fillStyle = "rgb(0,0,0)"; ctx.fillRect(0, 0, VW, VH);
    drawText("DRAW ERROR: " + err.message, 10, 10, "rgb(255,80,80)", F.small);
    console.error(err);
  }
  requestAnimationFrame(frame);
}

async function boot() {
  resizeCanvas();
  await loadAllAssets();
  const loading = document.getElementById("loading");
  if (loading) loading.style.display = "none";
  world = new GameWorld();
  setupInput();
  requestAnimationFrame(frame);
}

boot();
