import time

while True:
    time.sleep(0.1)
    (lambda: 0)()  # Let some tracing happen for tests
