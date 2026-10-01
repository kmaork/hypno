import time

SLEEP_SECONDS = 3
should_exit = False
sleep_started = time.monotonic()
time.sleep(SLEEP_SECONDS)  # A long C call that code is injected during

while not should_exit:
    time.sleep(0.05)
