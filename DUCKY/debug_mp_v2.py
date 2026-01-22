try:
    import mediapipe.python.solutions
    print("SUCCESS: mediapipe.python.solutions found")
except Exception as e:
    print("FAIL: mediapipe.python.solutions:", e)

try:
    from mediapipe.tasks import python
    from mediapipe.tasks.python import vision
    print("SUCCESS: mediapipe.tasks found")
except Exception as e:
    print("FAIL: mediapipe.tasks:", e)
