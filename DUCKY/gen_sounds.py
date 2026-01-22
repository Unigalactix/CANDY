import wave
import math
import struct
import random
import os

SAMPLE_RATE = 44100

def save_wav(filename, data):
    with wave.open(filename, 'w') as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(SAMPLE_RATE)
        for s in data:
            f.writeframes(struct.pack('h', int(s * 32767.0)))

def gen_noise(duration):
    return [random.uniform(-1, 1) for _ in range(int(SAMPLE_RATE * duration))]

def gen_square(freq, duration):
    n_samples = int(SAMPLE_RATE * duration)
    return [1.0 if math.sin(2 * math.pi * freq * t / SAMPLE_RATE) > 0 else -1.0 for t in range(n_samples)]

def gen_sine(freq, duration):
    return [math.sin(2 * math.pi * freq * t / SAMPLE_RATE) for t in range(int(SAMPLE_RATE * duration))]

def envelope(data, attack, decay):
    n = len(data)
    att_len = int(n * attack)
    dec_len = int(n * decay)
    res = []
    for i, s in enumerate(data):
        amp = 1.0
        if i < att_len:
            amp = i / att_len
        elif i > n - dec_len:
            amp = (n - i) / dec_len
        res.append(s * amp)
    return res

# --- Sound Definitions ---

# 1. Shoot (Noise burst with decay)
def make_shoot():
    data = gen_noise(0.3)
    data = envelope(data, 0.01, 0.8)
    save_wav("assets/shoot.wav", data)

# 2. Quack (Low square wave)
def make_quack():
    data = []
    # Two tones
    data.extend(gen_square(300, 0.1))
    data.extend(gen_square(200, 0.1))
    data = envelope(data, 0.1, 0.1)
    save_wav("assets/quack.wav", data)

# 3. Flap (Low sine)
def make_flap():
    data = gen_sine(100, 0.1)
    data = envelope(data, 0.1, 0.9)
    save_wav("assets/flap.wav", data)

# 4. Start (Jingle)
def make_start():
    data = []
    melody = [523, 659, 783, 1046, 783, 659, 523, 0, 587, 739, 880] # C E G C G E C ...
    tempo = 0.1
    for freq in melody:
        if freq == 0:
            data.extend([0] * int(SAMPLE_RATE * tempo))
        else:
            tone = gen_square(freq, tempo)
            tone = envelope(tone, 0.1, 0.1)
            data.extend(tone)
    save_wav("assets/start.wav", data)

if __name__ == "__main__":
    if not os.path.exists("assets"):
        os.makedirs("assets")
    make_shoot()
    make_quack()
    make_flap()
    make_start()
    print("Sounds generated in assets/")
