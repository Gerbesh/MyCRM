import os
import sys

import redis
from dotenv import load_dotenv

print("-> loading .env")
load_dotenv()

print("SECRET_KEY set:", bool(os.getenv("SECRET_KEY")))
print("DB:", os.getenv("DB_TYPE"), os.getenv("DB_HOST"), os.getenv("DB_NAME"))

rl = os.getenv("RATELIMIT_STORAGE_URL")
print("RATELIMIT_STORAGE_URL:", rl)

try:
    if rl:
        r = redis.StrictRedis.from_url(rl, socket_timeout=2)
        r.ping()
        print("Redis (limiter): OK")
    else:
        print("Redis (limiter): not configured")
except Exception as e:
    print("Redis (limiter) FAIL:", e)
    sys.exit(1)

print("OK")
