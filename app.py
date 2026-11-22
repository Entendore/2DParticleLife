import sys
import math
import random
from dataclasses import dataclass
from PySide6.QtCore import Qt, QTimer, QPointF
from PySide6.QtGui import QPainter, QColor, QPen, QPolygonF, QBrush
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel

# --- Utilities ---

def toroidal_delta(x1, y1, x2, y2, width, height):
    dx = x2 - x1
    dy = y2 - y1
    if dx > width / 2: dx -= width
    elif dx < -width / 2: dx += width
    if dy > height / 2: dy -= height
    elif dy < -height / 2: dy += height
    return dx, dy

# --- 5 Thematic Palettes (5 Colors Each) ---
PALETTE_KEYFRAMES = [
    # Tier 1: Water (Levels 1-5)
    QColor(10, 10, 40), QColor(0, 50, 150), QColor(0, 150, 255), QColor(100, 200, 255), QColor(200, 240, 255),
    # Tier 2: Nature (Levels 6-10)
    QColor(20, 50, 20), QColor(34, 139, 34), QColor(50, 205, 50), QColor(154, 205, 50), QColor(240, 255, 100),
    # Tier 3: Fire (Levels 11-15)
    QColor(80, 10, 10), QColor(220, 20, 20), QColor(255, 100, 0), QColor(255, 200, 0), QColor(255, 255, 200),
    # Tier 4: Arcane (Levels 16-20)
    QColor(40, 0, 60), QColor(128, 0, 128), QColor(255, 20, 147), QColor(255, 105, 180), QColor(255, 200, 255),
    # Tier 5: Cosmic (Levels 21-25)
    QColor(20, 20, 20), QColor(70, 70, 70), QColor(100, 100, 200), QColor(200, 100, 200), QColor(255, 255, 255)
]
PALETTE_CYCLE_LENGTH = 25
PALETTE_NAMES = ["Water", "Nature", "Fire", "Arcane", "Cosmic"]

def get_level_color(level):
    """Returns the exact color for the current level based on the 5-color palettes."""
    cycle = (level - 1) % PALETTE_CYCLE_LENGTH
    base_color = PALETTE_KEYFRAMES[cycle]
    
    # Every full cycle (25 levels), increase brightness for "Transcendent" tiers
    cycle_count = (level - 1) // PALETTE_CYCLE_LENGTH
    if cycle_count > 0:
        # Lighten by 15% for every full cycle completed
        base_color = base_color.lighter(100 + cycle_count * 15)
        
    return base_color

def get_palette_name(level):
    """Returns the name of the current palette tier."""
    cycle = (level - 1) % PALETTE_CYCLE_LENGTH
    tier_index = cycle // 5
    return PALETTE_NAMES[tier_index]

def get_complementary_color(color):
    """Returns the complementary color (used for accessories)."""
    h = color.hsvHue()
    if h < 0: return color # Grayscale fallback
    comp_h = (h + 180) % 360
    return QColor.fromHsv(comp_h, color.hsvSaturation(), color.value())


# --- Data Classes ---

@dataclass
class VisualEffect:
    x: float
    y: float
    timer: int
    max_timer: int
    color: QColor
    max_size: float
    is_eat_effect: bool = False

@dataclass
class Plant:
    x: float
    y: float
    energy: float = 25.0
    size: float = 3.0

class Creature:
    def __init__(self, x, y, level=1, energy=40.0):
        self.x = x
        self.y = y
        self.vx = 0.0
        self.vy = 0.0
        self.level = level
        self.energy = energy
        self.flash_timer = 0
        self.panic_timer = 0  # Adrenaline boost when fleeing
        
    @property
    def size(self):
        return 4.0 + (self.level * 1.1)
        
    @property
    def base_speed(self):
        return max(0.8, 3.2 - (self.level * 0.04))
        
    @property
    def max_speed(self):
        return self.base_speed * (1.8 if self.panic_timer > 0 else 1.0)
        
    @property
    def perception(self):
        return 60.0 + (self.level * 12.0)
        
    @property
    def metabolism(self):
        speed_factor = math.hypot(self.vx, self.vy) / self.base_speed
        panic_cost = 0.1 if self.panic_timer > 0 else 0.0
        return 0.01 + (self.level ** 1.4) * 0.012 + (speed_factor * 0.02) + panic_cost
        
    @property
    def evolution_threshold(self):
        return 60.0 * (1.35 ** self.level)

    def update(self, width, height):
        self.x += self.vx
        self.y += self.vy
        
        if self.x < 0: self.x += width
        if self.x >= width: self.x -= width
        if self.y < 0: self.y += height
        if self.y >= height: self.y -= height
        
        self.vx *= 0.98
        self.vy *= 0.98
        
        speed = math.hypot(self.vx, self.vy)
        if speed > self.max_speed:
            self.vx = (self.vx / speed) * self.max_speed
            self.vy = (self.vy / speed) * self.max_speed
            
        self.energy -= self.metabolism
        if self.flash_timer > 0: self.flash_timer -= 1
        if self.panic_timer > 0: self.panic_timer -= 1

# --- Simulation Logic ---

class Simulation:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.plants = []
        self.creatures = []
        self.effects = []
        self.tick = 0
        self.max_level_ever = 1
        
        for _ in range(120):
            self.spawn_plant()
        for _ in range(30):
            self.creatures.append(Creature(random.uniform(0, width), random.uniform(0, height)))
            
    def spawn_plant(self):
        if random.random() < 0.1:
            self.plants.append(Plant(random.uniform(0, self.width), random.uniform(0, self.height), energy=80.0, size=6.0))
        else:
            self.plants.append(Plant(random.uniform(0, self.width), random.uniform(0, self.height)))

    def update(self):
        self.tick += 1
        
        if len(self.plants) < 250 and random.random() < 0.6:
            self.spawn_plant()
            
        new_creatures = []
        items_to_remove = set()
        
        def find_nearest(creature, targets, max_dist):
            closest = None
            min_dist_sq = max_dist ** 2
            for t in targets:
                dx, dy = toroidal_delta(creature.x, creature.y, t.x, t.y, self.width, self.height)
                dist_sq = dx**2 + dy**2
                if dist_sq < min_dist_sq:
                    min_dist_sq = dist_sq
                    closest = t
            return closest, math.sqrt(min_dist_sq) if closest else None
        
        for c in self.creatures:
            food = None
            dist = None
            
            # 1. Threat Detection (Fleeing)
            predator, p_dist = find_nearest(c, [o for o in self.creatures if o.level > c.level], c.perception * 1.2)
            
            if predator and p_dist:
                c.panic_timer = 15
                dx, dy = toroidal_delta(c.x, c.y, predator.x, predator.y, self.width, self.height)
                dvx = -(dx / p_dist) * c.max_speed
                dvy = -(dy / p_dist) * c.max_speed
                steering_x = (dvx - c.vx) * 0.2
                steering_y = (dvy - c.vy) * 0.2
            else:
                # 2. Foraging (Seeking food)
                valid_food = self.plants + [o for o in self.creatures if o.level < c.level and id(o) not in items_to_remove]
                food, dist = find_nearest(c, valid_food, c.perception)
                
                if food and dist:
                    dx, dy = toroidal_delta(c.x, c.y, food.x, food.y, self.width, self.height)
                    dvx = (dx / dist) * c.max_speed
                    dvy = (dy / dist) * c.max_speed
                    steering_x = (dvx - c.vx) * 0.15
                    steering_y = (dvy - c.vy) * 0.15
                else:
                    # Wander
                    steering_x = random.uniform(-0.1, 0.1)
                    steering_y = random.uniform(-0.1, 0.1)
                
            c.vx += steering_x
            c.vy += steering_y
            c.update(self.width, self.height)
            
            # 3. Eating
            if food:
                dx, dy = toroidal_delta(c.x, c.y, food.x, food.y, self.width, self.height)
                if math.hypot(dx, dy) < (c.size + getattr(food, 'size', 0)):
                    c.energy += food.energy
                    if isinstance(food, Creature):
                        c.energy += food.level * 15
                        self.effects.append(VisualEffect(food.x, food.y, 20, 20, QColor(255, 50, 50), 20.0, True))
                    items_to_remove.add(id(food))
            
            # 4. Evolution Check
            if c.energy >= c.evolution_threshold:
                c.level += 1
                c.energy = 50.0 
                c.flash_timer = 20 
                if c.level > self.max_level_ever:
                    self.max_level_ever = c.level
                # Use the creature's new color for the shockwave
                shockwave_color = get_level_color(c.level)
                self.effects.append(VisualEffect(c.x, c.y, 30, 30, shockwave_color, c.size * 4.0, False))
                
            # 5. Reproduction
            if c.energy > c.evolution_threshold * 0.8:
                c.energy -= 60.0
                new_creatures.append(Creature(c.x, c.y, level=1, energy=40.0))
                
        self.plants = [p for p in self.plants if id(p) not in items_to_remove]
        self.creatures = [c for c in self.creatures if id(c) not in items_to_remove and c.energy > 0]
        self.creatures.extend(new_creatures)
        
        for e in self.effects:
            e.timer -= 1
        self.effects = [e for e in self.effects if e.timer > 0]


# --- PySide6 GUI ---

class SimulationCanvas(QWidget):
    def __init__(self, sim):
        super().__init__()
        self.sim = sim
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(self.backgroundRole(), QColor(12, 12, 20))
        self.setPalette(palette)
        self.tick_count = 0

    def draw_creature(self, painter, c):
        s = c.size
        angle = math.atan2(c.vy, c.vx)
        self.tick_count += 1
        
        # Get calculated palette colors
        base_color = get_level_color(c.level)
        dark_color = base_color.darker(250)
        comp_color = get_complementary_color(base_color)
        
        painter.save()
        painter.translate(c.x, c.y)
        painter.rotate(math.degrees(angle))
        
        # --- ACCESSORIES: Draw Behind Body ---
        if c.level >= 4:
            flap = math.sin(self.tick_count * 0.5) * 0.5
            wing_color = QColor(base_color.red(), base_color.green(), base_color.blue(), 100)
            painter.setBrush(wing_color)
            painter.setPen(Qt.NoPen)
            wing_poly = QPolygonF([
                QPointF(0, 0), QPointF(-s*0.5, -s*2.0 - flap*s), 
                QPointF(-s*1.5, -s*0.5), QPointF(-s*0.5, -s*0.2)
            ])
            painter.drawPolygon(wing_poly)
            painter.drawPolygon(QPolygonF([QPointF(p.x(), -p.y()) for p in wing_poly]))
            
        # --- DRAW MAIN BODY ---
        sides = min(3 + c.level, 8)
        poly = QPolygonF()
        for i in range(sides):
            ang = (i * 2 * math.pi) / sides
            r_x = s * 1.5 if math.cos(ang) > 0 else s * 1.0
            r_y = s * 1.0
            poly.append(QPointF(math.cos(ang) * r_x, math.sin(ang) * r_y))
            
        painter.setPen(QPen(dark_color, 2))
        painter.setBrush(QBrush(base_color))
        painter.drawPolygon(poly)
        
        # --- ACCESSORIES: Draw On Top of Body ---
        if c.level >= 3:
            painter.setBrush(dark_color)
            painter.setPen(Qt.NoPen)
            for i in range(sides):
                ang = (i * 2 * math.pi) / sides
                spike = QPolygonF([
                    QPointF(math.cos(ang) * s * 1.2, math.sin(ang) * s * 1.2),
                    QPointF(math.cos(ang) * s * 2.0, math.sin(ang) * s * 2.0),
                    QPointF(math.cos(ang + 0.3) * s * 1.0, math.sin(ang + 0.3) * s * 1.0)
                ])
                painter.drawPolygon(spike)
                
        if c.level >= 5:
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(QColor(255, 255, 255, 80), 2, Qt.DashLine))
            painter.drawEllipse(QPointF(0, 0), s * 2.5, s * 2.5)
            
        if c.level >= 6:
            painter.setBrush(QColor(255, 215, 0)) # Gold crown stands out against all colors
            painter.setPen(QPen(QColor(0,0,0), 1))
            crown_poly = QPolygonF()
            for i in range(5):
                cx = (i - 2) * s * 0.5
                crown_poly.append(QPointF(cx, -s * 1.2))
                crown_poly.append(QPointF(cx + s * 0.25, -s * 1.8))
            painter.drawPolygon(crown_poly)
            
        if c.level >= 8:
            painter.setBrush(comp_color.lighter(120))
            painter.setPen(QPen(comp_color.darker(200), 1))
            for i in range(3):
                orbit_ang = (self.tick_count * 0.1) + (i * 2 * math.pi / 3)
                ox = math.cos(orbit_ang) * s * 3.0
                oy = math.sin(orbit_ang) * s * 3.0
                painter.drawEllipse(QPointF(ox, oy), s*0.3, s*0.3)

        painter.restore()

    def draw_plant(self, painter, p):
        color = QColor(50, 200, 50) if p.energy < 50 else QColor(150, 255, 150)
        painter.setPen(QPen(color.darker(200), 1))
        painter.setBrush(QBrush(color))
        poly = QPolygonF([
            QPointF(p.x, p.y - p.size * 1.5), QPointF(p.x + p.size * 0.5, p.y - p.size * 0.5),
            QPointF(p.x + p.size * 1.5, p.y), QPointF(p.x + p.size * 0.5, p.y + p.size * 0.5),
            QPointF(p.x, p.y + p.size * 1.5), QPointF(p.x - p.size * 0.5, p.y + p.size * 0.5),
            QPointF(p.x - p.size * 1.5, p.y), QPointF(p.x - p.size * 0.5, p.y - p.size * 0.5),
        ])
        painter.drawPolygon(poly)

    def draw_effects(self, painter):
        for e in self.sim.effects:
            progress = 1.0 - (e.timer / e.max_timer)
            alpha = int(255 * (1.0 - progress))
            
            if e.is_eat_effect:
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor(e.color.red(), e.color.green(), e.color.blue(), alpha))
                for _ in range(5):
                    ang = random.uniform(0, 2 * math.pi)
                    dist = e.max_size * progress * random.uniform(0.5, 1.0)
                    px = e.x + math.cos(ang) * dist
                    py = e.y + math.sin(ang) * dist
                    painter.drawEllipse(QPointF(px, py), 2.0, 2.0)
            else:
                size = e.max_size * progress
                painter.setPen(QPen(QColor(e.color.red(), e.color.green(), e.color.blue(), alpha), 3))
                painter.setBrush(Qt.NoBrush)
                painter.drawEllipse(QPointF(e.x, e.y), size, size)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Subtle grid
        painter.setPen(QPen(QColor(20, 20, 30), 1))
        grid_size = 50
        for x in range(0, self.width(), grid_size):
            painter.drawLine(x, 0, x, self.height())
        for y in range(0, self.height(), grid_size):
            painter.drawLine(0, y, self.width(), y)
        
        for p in self.sim.plants:
            self.draw_plant(painter, p)
            
        sorted_creatures = sorted(self.sim.creatures, key=lambda c: c.level)
        
        for c in sorted_creatures:
            self.draw_creature(painter, c)
            if c.flash_timer > 0:
                painter.setPen(QPen(QColor(255, 255, 255, c.flash_timer * 12), 3))
                painter.setBrush(Qt.NoBrush)
                flash_size = c.size + (20 - c.flash_timer) * 4
                painter.drawEllipse(QPointF(c.x, c.y), flash_size, flash_size)
                
        self.draw_effects(painter)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Infinite Evolution - 5 Thematic Palettes")
        self.resize(1000, 750)
        
        self.sim = Simulation(self.width(), self.height() - 80)
        
        central_widget = QWidget()
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        self.canvas = SimulationCanvas(self.sim)
        layout.addWidget(self.canvas)
        
        self.stats_label = QLabel("Initializing...")
        self.stats_label.setStyleSheet("color: #DDD; background-color: #1A1A1A; padding: 10px; font-family: monospace;")
        layout.addWidget(self.stats_label)
        
        self.setCentralWidget(central_widget)
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_sim)
        self.timer.start(33) 
        
    def update_sim(self):
        if self.sim.width != self.canvas.width() or self.sim.height != self.canvas.height():
            self.sim.width = self.canvas.width()
            self.sim.height = self.canvas.height()
            
        self.sim.update()
        self.canvas.update()
        self.update_stats()
        
    def update_stats(self):
        if not self.sim.creatures:
            self.stats_label.setText("Extinction event. All creatures died.")
            return
            
        max_lvl = max(c.level for c in self.sim.creatures)
        avg_lvl = sum(c.level for c in self.sim.creatures) / len(self.sim.creatures)
        
        # Get palette name for the current max level creature
        palette_name = get_palette_name(max_lvl)
        
        stats_text = (
            f"Tick: {self.sim.tick} | Plants: {len(self.sim.plants)} | "
            f"Creatures: {len(self.sim.creatures)}\n"
            f"Current Max Level: {max_lvl} ({palette_name} Palette)  |  Average Level: {avg_lvl:.2f}  |  "
            f"Apotheosis (Highest Ever): {self.sim.max_level_ever}"
        )
        self.stats_label.setText(stats_text)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()
        elif event.key() == Qt.Key_Space:
            if self.timer.isActive(): self.timer.stop()
            else: self.timer.start()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())