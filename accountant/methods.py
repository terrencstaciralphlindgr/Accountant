from datetime import datetime, timezone
import os, environ, pytz
import structlog

log = structlog.get_logger(__name__)

datetime_directive_ISO_8601 = "%Y-%m-%dT%H:%M:%SZ"
directive_ccxt = '%Y-%m-%dT%H:%M:%S.%fZ'


def get_env():
    environ.Env.read_env()
    env = environ.Env(DEBUG=(bool, False))
    PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))  # Contains settings.py
    env_file = os.path.join(PROJECT_ROOT, ".env")
    environ.Env.read_env(env_file)
    return env


def to_datetime(obj):
    if isinstance(int, obj):
        return datetime.fromtimestamp(obj).replace(tzinfo=pytz.UTC)


def dt_aware_now(interval=None):
    """
    Get current time as an aware datetime object in Python 3.3+
    """
    dt = datetime.now(timezone.utc)
    if interval:
        intervals = list(range(0, 60, interval))
        minute = [i for i in intervals if dt.minute >= i][-1]
        dt = dt.replace(minute=minute, second=0, microsecond=0)
        return dt
    else:
        dt = dt.replace(hour=0, minute=0, second=0, microsecond=0)
        return dt
