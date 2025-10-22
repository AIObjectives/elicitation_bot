import time
from config.config import db, logger

# In-memory cache for phone lookups
_cache = {}
_DEFAULT_TTL = 60  # fallback if Firestore config missing
_last_ttl_fetch = 0
_ttl_value = _DEFAULT_TTL
_TTL_REFRESH_INTERVAL = 60  # how often (seconds) to re-check Firestore for new TTL


def _get_cache_ttl() -> int:
    """
    Fetch the TTL configuration from Firestore system_settings/blacklist_config.
    Cached locally to avoid frequent reads.
    """
    global _last_ttl_fetch, _ttl_value

    now = time.time()
    # only fetch TTL value once per _TTL_REFRESH_INTERVAL
    if now - _last_ttl_fetch < _TTL_REFRESH_INTERVAL:
        return _ttl_value

    try:
        doc = db.collection("system_settings").document("blacklist_config").get()
        if doc.exists:
            val = doc.to_dict().get("cache_ttl_seconds", _DEFAULT_TTL)
            _ttl_value = int(val)
            logger.info(f"[Blacklist] TTL updated from Firestore: {_ttl_value}s")
        else:
            _ttl_value = _DEFAULT_TTL
    except Exception as e:
        logger.error(f"[Blacklist] Failed to load TTL config: {e}")
        _ttl_value = _DEFAULT_TTL

    _last_ttl_fetch = now
    return _ttl_value


def is_blocked_number(phone: str) -> bool:
    """
    Return True if the normalized phone is in Firestore blocked_numbers collection.
    Uses a dynamically configurable TTL for caching results.
    """
    now = time.time()
    ttl = _get_cache_ttl()

    cached = _cache.get(phone)
    if cached and now - cached['time'] < ttl:
        return cached['value']

    try:
        ref = db.collection('blocked_numbers').document(phone)
        doc = ref.get()
        blocked = doc.exists
        _cache[phone] = {'value': blocked, 'time': now}
        if blocked:
            logger.info(f"[Blacklist] Blocked number detected: {phone}")
        return blocked
    except Exception as e:
        logger.error(f"[Blacklist] Error checking {phone}: {e}")
        return False
