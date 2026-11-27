"""Independent process: log unusual scheduling gaps on the same clock."""
import json
import time

previous = time.perf_counter()
while True:
    time.sleep(.01)
    now = time.perf_counter()
    if now - previous >= .025:
        print(json.dumps({'start': previous, 'end': now, 'ms': (now-previous)*1000}), flush=True)
    previous = now
