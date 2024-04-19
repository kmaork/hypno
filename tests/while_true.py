import time
import sys

should_exit = False

while not should_exit:
    sys.stderr.write(sys.argv[1])
    sys.stderr.flush()
    time.sleep(0.01)

sys.stderr.write(sys.argv[2])
sys.stderr.flush()
