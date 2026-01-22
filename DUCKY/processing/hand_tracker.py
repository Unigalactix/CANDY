import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
import math
import numpy as np

class HandTracker:
    def __init__(self, model_path='assets/hand_landmarker.task'):
        # Create an HandLandmarker object.
        try:
            base_options = python.BaseOptions(model_asset_path=model_path)
            options = vision.HandLandmarkerOptions(
                base_options=base_options,
                num_hands=1,
                min_hand_detection_confidence=0.5,
                min_hand_presence_confidence=0.5,
                min_tracking_confidence=0.5)
            self.detector = vision.HandLandmarker.create_from_options(options)
            self.results = None
            print(f"HandTracker initialized with model: {model_path}")
        except Exception as e:
            print(f"Failed to init HandTracker: {e}")
            self.detector = None

    def find_hands(self, img, draw=True):
        if not self.detector:
            return img

        # Convert the image to RGB
        rgb_image = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_image)

        # Detect
        self.results = self.detector.detect(mp_image)
        
        # Simple Draw
        if draw and self.results.hand_landmarks:
            for hand_landmarks in self.results.hand_landmarks:
                h, w, _ = img.shape
                # Draw connections could be complex manually, lets just draw points
                for lm in hand_landmarks:
                    cx, cy = int(lm.x * w), int(lm.y * h)
                    cv2.circle(img, (cx, cy), 5, (255, 0, 255), cv2.FILLED)
        return img

    def get_aim_info(self, img, screen_w, screen_h):
        if not self.detector or not self.results or not self.results.hand_landmarks:
            return None

        # Get first hand (list of lists)
        hand_lms = self.results.hand_landmarks[0]
        
        # Indices: Index Tip = 8, Thumb Tip = 4, Thumb IP = 3, Index MCP = 5, Wrist = 0, Middle MCP = 9
        index_tip = hand_lms[8]
        thumb_tip = hand_lms[4]
        index_mcp = hand_lms[5]
        wrist = hand_lms[0]
        middle_mcp = hand_lms[9]
        
        # Mirror X for aim?
        # If camera is flipped (Mirror mode), x increases Left->Right.
        # So we should just use x directly.
        aim_x = int(index_tip.x * screen_w)
        aim_y = int(index_tip.y * screen_h)

        # Calculate Distances
        # 1. Thumb Tip to Index MCP (Hammer/Curl)
        dist_curl = math.hypot(thumb_tip.x - index_mcp.x, thumb_tip.y - index_mcp.y)
        # 2. Thumb Tip to Index Tip (Pinch)
        dist_pinch = math.hypot(thumb_tip.x - index_tip.x, thumb_tip.y - index_tip.y)

        hand_size = math.hypot(wrist.x - middle_mcp.x, wrist.y - middle_mcp.y)
        
        is_shooting = False
        if hand_size > 0:
            # Check Curl (Hammer down)
            if (dist_curl / hand_size) < 0.55:
                is_shooting = True
            # Check Pinch (Thumb touches Index Tip)
            elif (dist_pinch / hand_size) < 0.2:
                is_shooting = True

        return (aim_x, aim_y, is_shooting)
