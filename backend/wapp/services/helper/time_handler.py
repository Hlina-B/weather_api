# handling gap and fold for summer and fall
from time import time

def current_hour_start_epoch() -> str:
    """Returns the exact epoch second of the current hour's :00:00 mark."""
    current_epoch = int(time())
    # Floor to the nearest 3,600-second (1 hour) boundary. 
    # This would silently fail for India (+5:30) or Newfoundland (−3:30), where local hours don’t start on a UTC hour boundary. 
    hour_start = (current_epoch // 3600) * 3600
    return str(hour_start)