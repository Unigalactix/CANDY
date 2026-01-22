# DUCKY - The AI Duck Hunt

DUCKY is a modern Python-based tribute to the classic Duck Hunt game. It features a complete gameplay loop with sound effects, animations, and dual control modes: **AI Hand Tracking** or **Classic Mouse Control**.

## Features
- **Story Mode**: Classic "Dog Sniiffing & Jumping" intro sequence.
- **Dual Controls**: 
    - **Mouse Mode (Default)**: Play instantly with your mouse.
    - **Hand Mode**: Use your webcam and specific hand gestures to aim and shoot!
- **Sound Effects**: Retro 8-bit style generated sounds (Shoot, Quack, Game Start).
- **Animations**: Flying ducks with flapping wings and dynamic dog sprites.

## Requirements
- Python 3.9+
- Webcam (Optional, only for Hand Mode)

## Installation

1. Create a virtual environment (Recommended):
   ```bash
   python -m venv venv
   # Windows:
   .\venv\Scripts\activate
   # Linux/Mac:
   source venv/bin/activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. **Assets**: The game requires assets in the `assets/` directory (included).

## How to Play

1. Run the game:
   ```bash
   python main.py
   ```

2. **Menu**:
   - Select **Difficulty** (Easy, Medium, Hard).
   - Toggle **Mode**: Defaults to "MOUSE". Click to switch to "HAND".

3. **Controls**:
   - **Mouse Mode**: Move mouse to aim, Left Click to shoot.
   - **Hand Mode**: 
     - Aim: Point index finger.
     - Shoot: Pinch (Index touches Thumb) or Curl Thumb "Hammer" motion.

4. **Objective**: Shoot the ducks before they fly away!

## Credits
Built with **Pygame-CE**, **OpenCV**, and **Mediapipe**.
