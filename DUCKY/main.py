import pygame
import cv2
import random
import sys
import os
import traceback

print(">>> GAME LAUNCHING...")

try:
    from processing.hand_tracker import HandTracker
except ImportError as e:
    print(f"WARNING: HandTracker import failed ({e}). Hand mode will be disabled.")
    HandTracker = None

# --- Constants ---
SCREEN_WIDTH = 1024
SCREEN_HEIGHT = 768
FPS = 60
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
SKY_BLUE = (63, 191, 255)
GREEN_GROUND = (100, 200, 50)
RED = (255, 0, 0)
FONT_SIZE = 30

# State Constants
STATE_MENU = "MENU"
STATE_INTRO = "INTRO"
STATE_ROUND_START = "ROUND_START"
STATE_HUNT = "HUNT"
STATE_DUCK_FALL = "DUCK_FALL"
STATE_DOG_CATCH = "DOG_CATCH"
STATE_DOG_LAUGH = "DOG_LAUGH"

# Asset Paths
ASSET_DIR = "assets"
DUCK_F1 = os.path.join(ASSET_DIR, "duck_f1.png")
DUCK_F2 = os.path.join(ASSET_DIR, "duck_f2.png")
DOG_SNIFF = os.path.join(ASSET_DIR, "dog_sniff.png")
DOG_JUMP = os.path.join(ASSET_DIR, "dog_jump.png")
DOG_LAUGH = os.path.join(ASSET_DIR, "dog_laugh.png")
DOG_CATCH = os.path.join(ASSET_DIR, "dog_catch.png")
BG_IMG = os.path.join(ASSET_DIR, "background.png")
CROSSHAIR = os.path.join(ASSET_DIR, "crosshair.png")
SOUND_SHOOT = os.path.join(ASSET_DIR, "shoot.wav")
SOUND_QUACK = os.path.join(ASSET_DIR, "quack.wav")
SOUND_FLAP = os.path.join(ASSET_DIR, "flap.wav")
SOUND_START = os.path.join(ASSET_DIR, "start.wav")

class SoundManager:
    def __init__(self):
        try:
            pygame.mixer.init()
            print("Audio initialized.")
        except Exception as e:
            print(f"Audio init failed: {e}")
            return
            
        self.sounds = {}
        def load(name, path):
            if os.path.exists(path):
                try: self.sounds[name] = pygame.mixer.Sound(path)
                except Exception as e: print(f"Failed to load sound {name}: {e}")
            else:
                print(f"Sound file missing: {path}")
        
        load('shoot', SOUND_SHOOT)
        load('quack', SOUND_QUACK)
        load('flap', SOUND_FLAP)
        load('start', SOUND_START)
        
    def play(self, name):
        if name in self.sounds: 
            try: self.sounds[name].play()
            except: pass

class Dog(pygame.sprite.Sprite):
    def __init__(self):
        super().__init__()
        self.images = {}
        def load_scale(path, w, h):
            if not os.path.exists(path):
                s = pygame.Surface((w,h))
                s.fill(RED)
                return s
            try:
                img = pygame.image.load(path).convert()
                img.set_colorkey(WHITE)
                return pygame.transform.scale(img, (w, h))
            except Exception as e:
                print(f"Failed to load {path}: {e}")
                s = pygame.Surface((w,h))
                s.fill(RED)
                return s

        self.images['SNIFF'] = load_scale(DOG_SNIFF, 120, 100)
        self.images['JUMP'] = load_scale(DOG_JUMP, 120, 130)
        self.images['LAUGH'] = load_scale(DOG_LAUGH, 100, 120)
        self.images['CATCH'] = load_scale(DOG_CATCH, 110, 140)
        
        self.image = self.images['SNIFF']
        self.rect = self.image.get_rect()
        self.rect.bottom = SCREEN_HEIGHT - 120 
        self.rect.x = 0
        self.state = "SNIFF"
        self.timer = 0

    def reset_intro(self):
        self.state = "SNIFF"
        self.rect.x = 0
        self.rect.bottom = SCREEN_HEIGHT - 120
        self.image = self.images['SNIFF']
        self.visible = True

    def update_intro(self):
        if self.state == "SNIFF":
            self.rect.x += 3
            if self.rect.centerx > SCREEN_WIDTH // 3:
                self.state = "JUMP"
                self.image = self.images['JUMP']
                self.rect.y -= 30
        elif self.state == "JUMP":
            self.rect.y -= 5
            self.rect.x += 2
            if self.rect.y < SCREEN_HEIGHT - 350:
                 self.kill() 
                 return True
        return False

    def show_catch(self):
        self.state = "CATCH"
        self.image = self.images['CATCH']
        self.rect.centerx = SCREEN_WIDTH // 2
        self.rect.bottom = SCREEN_HEIGHT - 100
        self.timer = pygame.time.get_ticks()
    
    def show_laugh(self):
        self.state = "LAUGH"
        self.image = self.images['LAUGH']
        self.rect.centerx = SCREEN_WIDTH // 2
        self.rect.bottom = SCREEN_HEIGHT - 100
        self.timer = pygame.time.get_ticks()

    def update_popup(self):
        elapsed = pygame.time.get_ticks() - self.timer
        if elapsed < 500: self.rect.y -= 2
        elif elapsed > 1500 and elapsed < 2000: self.rect.y += 2
        elif elapsed > 2000:
            self.kill()
            return True
        return False


class Duck(pygame.sprite.Sprite):
    def __init__(self, speed):
        super().__init__()
        self.frames = []
        try:
            if os.path.exists(DUCK_F1):
                f1 = pygame.image.load(DUCK_F1).convert()
                f1.set_colorkey(WHITE)
                f1 = pygame.transform.scale(f1, (70, 70))
                self.frames.append(f1)
            
            if os.path.exists(DUCK_F2):
                f2 = pygame.image.load(DUCK_F2).convert()
                f2.set_colorkey(WHITE)
                f2 = pygame.transform.scale(f2, (70, 70))
                self.frames.append(f2)
        except Exception as e:
            print(f"Duck load error: {e}")

        if not self.frames:
            s = pygame.Surface((70,70))
            s.fill((0,255,0))
            self.frames = [s]

        self.image = self.frames[0]
        self.rect = self.image.get_rect()
        self.speed = speed
        self.reset(speed)

    def reset(self, speed):
        self.rect.bottom = SCREEN_HEIGHT - 150
        self.rect.centerx = random.randint(100, SCREEN_WIDTH-100)
        self.speed_x = random.choice([-1, 1]) * speed
        self.speed_y = -speed
        self.alive = True
        self.falling = False
        self.fly_away = False
    
    def update(self):
        if self.alive and not self.fly_away:
            self.rect.x += self.speed_x
            self.rect.y += self.speed_y
            
            if self.rect.left < 0 or self.rect.right > SCREEN_WIDTH:
                self.speed_x *= -1
            if self.rect.top < 0:
                self.speed_y *= -1
            
            if len(self.frames) > 1:
                idx = (pygame.time.get_ticks() // 150) % len(self.frames)
                img = self.frames[idx]
                if self.speed_x > 0:
                    img = pygame.transform.flip(img, True, False)
                self.image = img
            
        elif self.falling:
            self.rect.y += 10
            if len(self.frames) > 1:
                self.image = pygame.transform.flip(self.frames[1], False, True)
            if self.rect.top > SCREEN_HEIGHT:
                self.kill()
                return "CAUGHT" 
        
        elif self.fly_away:
            self.rect.y -= 10
            if self.rect.bottom < 0:
                self.kill()
                return "ESCAPED"
        return None

    def hit(self):
        self.alive = False
        self.falling = True
    
    def escape(self):
        self.alive = False
        self.falling = False
        self.fly_away = True


def main():
    print("Initializing Pygame...")
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("DUCKY HUNT - Debug Mode")
    clock = pygame.time.Clock()
    font = pygame.font.Font(None, 40)
    
    print("Loading Sounds...")
    sounds = SoundManager()
    
    print("Loading Assets...")
    try:
        if os.path.exists(BG_IMG):
            bg = pygame.image.load(BG_IMG).convert()
            bg = pygame.transform.scale(bg, (SCREEN_WIDTH, SCREEN_HEIGHT))
        else:
            bg = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
            bg.fill(SKY_BLUE)
    except Exception as e:
        print(f"BG Load Error: {e}")
        bg = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        bg.fill(SKY_BLUE)

    cursor_img = pygame.Surface((10,10))
    try:
        if os.path.exists(CROSSHAIR):
            cursor_img = pygame.image.load(CROSSHAIR).convert()
            cursor_img.set_colorkey(WHITE)
            cursor_img = pygame.transform.scale(cursor_img, (50,50))
    except Exception as e: print(f"Cursor load error: {e}")

    # Hand Tracker Lazy Load
    tracker = None
    cap = None

    control_mode = "MOUSE"
    state = STATE_MENU
    
    round_num = 1
    ammo = 3
    score = 0
    hits_in_round = []
    
    duck_group = pygame.sprite.GroupSingle()
    dog_group = pygame.sprite.GroupSingle()
    
    hud_rect = pygame.Rect(0, SCREEN_HEIGHT-80, SCREEN_WIDTH, 80)
    
    running = True
    cursor_pos = (0,0)
    is_shooting_prev = False

    print("Main Loop Started.")
    while running:
        click_trigger = False
        is_shooting_now = False
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT: running = False
            if control_mode == "MOUSE" and event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                click_trigger = True
                is_shooting_now = True
            if event.type == pygame.KEYDOWN and event.key == pygame.K_m:
                 control_mode = "MOUSE" if control_mode == "HAND" else "HAND"
                 print(f"Switched to {control_mode}")
                 if control_mode == "HAND" and tracker is None:
                     if HandTracker:
                         try:
                             print("Init Camera...")
                             cap = cv2.VideoCapture(0)
                             print("Init Tracker...")
                             tracker = HandTracker()
                         except Exception as e:
                             print(f"Tracker init failed: {e}")
                             tracker = None

        # Vision
        if control_mode == "HAND" and tracker and cap:
            ret, frame = cap.read()
            if ret:
                frame = cv2.flip(frame, 1)
                frame = tracker.find_hands(frame)
                info = tracker.get_aim_info(frame, SCREEN_WIDTH, SCREEN_HEIGHT)
                if info:
                    cx, cy, shooting = info
                    cursor_pos = (cx, cy)
                    is_shooting_now = shooting
                    if is_shooting_now and not is_shooting_prev:
                        click_trigger = True
                    is_shooting_prev = is_shooting_now
        elif control_mode == "MOUSE":
            cursor_pos = pygame.mouse.get_pos()
            if pygame.mouse.get_pressed()[0]: is_shooting_now = True

        # Render
        screen.blit(bg, (0,0))
        
        if state == STATE_MENU:
            msg = font.render(f"CLICK TO START - MODE: {control_mode} (Press M)", True, BLACK)
            screen.blit(msg, (SCREEN_WIDTH//2 - 200, SCREEN_HEIGHT//2))
            if click_trigger:
                state = STATE_INTRO
                dog = Dog()
                dog_group.add(dog)
                sounds.play('start')

        elif state == STATE_INTRO:
            dog_group.draw(screen)
            if dog_group.sprite.update_intro():
                state = STATE_ROUND_START
                round_num = 1
                score = 0
                
        elif state == STATE_ROUND_START:
            hits_in_round = []
            state = STATE_HUNT
            ammo = 3
            d = Duck(speed=5 + round_num)
            duck_group.add(d)

        elif state == STATE_HUNT:
            duck_group.draw(screen)
            status = duck_group.sprite.update() 
            
            if click_trigger and ammo > 0:
                ammo -= 1
                sounds.play('shoot')
                if duck_group.sprite.rect.collidepoint(cursor_pos):
                    duck_group.sprite.hit()
                    score += 500
                    state = STATE_DUCK_FALL
            
            if duck_group.sprite and ammo == 0 and not duck_group.sprite.falling:
                 duck_group.sprite.escape()
            
            if status == "ESCAPED":
                 state = STATE_DOG_LAUGH
                 hits_in_round.append(False)
                 dog = Dog()
                 dog.show_laugh()
                 dog_group.add(dog)
        
        elif state == STATE_DUCK_FALL:
             duck_group.draw(screen)
             status = duck_group.sprite.update()
             if status == "CAUGHT":
                 state = STATE_DOG_CATCH
                 hits_in_round.append(True)
                 dog = Dog()
                 dog.show_catch()
                 dog_group.add(dog)
        
        elif state == STATE_DOG_CATCH or state == STATE_DOG_LAUGH:
            dog_group.draw(screen)
            if dog_group.sprite.update_popup():
                if len(hits_in_round) < 10:
                    ammo = 3
                    d = Duck(speed=5 + round_num)
                    duck_group.add(d)
                    state = STATE_HUNT
                else:
                    state = STATE_ROUND_START
                    round_num += 1

        # HUD
        pygame.draw.rect(screen, GREEN_GROUND, hud_rect)
        for i in range(ammo):
            pygame.draw.rect(screen, RED, (50 + i*20, SCREEN_HEIGHT-60, 10, 20))
        
        for i, hit in enumerate(hits_in_round):
            color = RED if hit else BLACK
            pygame.draw.circle(screen, color, (300 + i*30, SCREEN_HEIGHT-40), 10)
        
        score_txt = font.render(f"SCORE: {score:05}", True, WHITE)
        screen.blit(score_txt, (SCREEN_WIDTH - 250, SCREEN_HEIGHT-50))

        pygame.mouse.set_visible(False)
        c_rect = cursor_img.get_rect(center=cursor_pos)
        screen.blit(cursor_img, c_rect)

        pygame.display.flip()
        clock.tick(FPS)

    if cap: cap.release()
    cv2.destroyAllWindows()
    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("CRITICAL EXCEPTION:")
        traceback.print_exc()
        input("Press Enter...")
