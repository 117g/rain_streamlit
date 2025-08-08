import os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class Config:
    KEY_FILE = os.path.join(BASE_DIR, "secrets.txt")
    CACHE_DIR = "cache"
    STATION_CODE = "400"
    TIME_START = "1000"
    TIME_END = "1600"
    MAX_THREADS = 20
    TIME_START_OBJ = datetime.strptime(TIME_START, "%H%M").time()
    TIME_END_OBJ = datetime.strptime(TIME_END, "%H%M").time()
