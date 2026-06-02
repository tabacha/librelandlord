import ipaddress
import logging
import threading
from datetime import timedelta

from django.http import HttpResponseForbidden
from django.utils import timezone

logger = logging.getLogger(__name__)

SUSPICIOUS_PATTERNS = [
    '.php',
    '/wp-',
    '/.git/',
    '/.env',
    '/xmlrpc',
    '/phpmyadmin',
    '/cgi-bin/',
    '/shell',
    '/console',
]

BLOCK_EXPIRY = timedelta(hours=24)
# Minimum interval between DB last_seen updates for already-blocked IPs (reduces write load).
DB_SYNC_INTERVAL = timedelta(minutes=30)

# Maps normalized network → last_seen (timezone-aware).
_blocklist: dict[str, object] = {}
# Tracks when we last wrote last_seen to DB per entry.
_db_synced: dict[str, object] = {}
_lock = threading.Lock()
_initialized = False


def _load_from_db() -> None:
    global _initialized
    if _initialized:
        return
    with _lock:
        if _initialized:
            return
        try:
            from bill.models import BlockedNetwork
            expiry_cutoff = timezone.now() - BLOCK_EXPIRY
            # Remove entries that have already expired
            deleted, _ = BlockedNetwork.objects.filter(last_seen__lt=expiry_cutoff).delete()
            if deleted:
                logger.info("Blocklist: %d abgelaufene Einträge aus DB entfernt", deleted)
            for entry in BlockedNetwork.objects.all():
                _blocklist[entry.network] = entry.last_seen
                _db_synced[entry.network] = entry.last_seen
            logger.info("Blocklist geladen: %d aktive Einträge aus DB", len(_blocklist))
        except Exception:
            logger.exception("Blocklist konnte nicht aus DB geladen werden")
        _initialized = True


def _normalize_ip(ip: str) -> str:
    """IPv4: collapse to /26 network. IPv6: collapse to /48 network."""
    try:
        addr = ipaddress.ip_address(ip)
        if isinstance(addr, ipaddress.IPv6Address):
            return str(ipaddress.IPv6Network(f"{ip}/48", strict=False))
        return str(ipaddress.IPv4Network(f"{ip}/26", strict=False))
    except ValueError:
        return ip


def _is_suspicious(path: str) -> bool:
    p = path.lower()
    return any(pat in p for pat in SUSPICIOUS_PATTERNS)


def _db_save(key: str, last_seen, reason: str = '') -> None:
    try:
        from bill.models import BlockedNetwork
        BlockedNetwork.objects.update_or_create(
            network=key,
            defaults={'last_seen': last_seen, 'reason': reason},
        )
        _db_synced[key] = last_seen
    except Exception:
        logger.exception("Konnte Block nicht in DB speichern: %s", key)


def _db_delete(key: str) -> None:
    try:
        from bill.models import BlockedNetwork
        BlockedNetwork.objects.filter(network=key).delete()
        _db_synced.pop(key, None)
    except Exception:
        logger.exception("Konnte Block nicht aus DB löschen: %s", key)


class AttackBlocklistMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        _load_from_db()

        ip = self._get_ip(request)
        key = _normalize_ip(ip)
        now = timezone.now()

        with _lock:
            last_seen = _blocklist.get(key)
            if last_seen is not None:
                if now - last_seen > BLOCK_EXPIRY:
                    del _blocklist[key]
                    logger.info("Blockade aufgehoben (24h Inaktivität): %s", key)
                    _db_delete(key)
                else:
                    _blocklist[key] = now
                    # Persist last_seen to DB at most every DB_SYNC_INTERVAL
                    db_due = key not in _db_synced or now - _db_synced[key] > DB_SYNC_INTERVAL
                    logger.debug("Geblockte IP %s: %s", key, request.path)
                    if db_due:
                        _db_save(key, now)
                    return HttpResponseForbidden()

        response = self.get_response(request)

        if response.status_code == 404 and _is_suspicious(request.path):
            with _lock:
                is_new = key not in _blocklist
                _blocklist[key] = now
            if is_new:
                logger.warning("IP geblockt nach Angriffspfad: %s → %s", key, request.path)
                _db_save(key, now, reason=request.path[:255])

        return response

    @staticmethod
    def _get_ip(request) -> str:
        # X-Real-IP is set by Nginx to $remote_addr — always the true client IP, not spoofable.
        real_ip = request.META.get('HTTP_X_REAL_IP')
        if real_ip:
            return real_ip.strip()
        xff = request.META.get('HTTP_X_FORWARDED_FOR')
        if xff:
            # Nginx appends the real client IP as the last entry
            return xff.split(',')[-1].strip()
        return request.META.get('REMOTE_ADDR', '')
