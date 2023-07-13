import time
import sys

should_exit = False

while not should_exit:
    time.sleep(0.01)
    sys.stderr.write(sys.argv[1])
