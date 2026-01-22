import mediapipe as mp
print("Mediapipe file:", mp.__file__)
print("Dir(mp):", dir(mp))
try:
    import mediapipe.solutions.hands
    print("Direct import of solutions.hands success")
except Exception as e:
    print("Direct import failed:", e)
