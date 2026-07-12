import time
from asgiref.sync import sync_to_async
from django.core.cache import cache

class WebSocketRateLimitMiddleware:
    """
    ASGI middleware that rate-limits WebSocket handshakes.
    Uses Django's cache framework (which is backed by Redis in production).
    Limits clients to 60 connections per minute by IP.
    """

    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        if scope["type"] == "websocket":
            client_ip = self.get_client_ip(scope)
            if client_ip:
                is_allowed = await self.check_rate_limit(client_ip)
                if not is_allowed:
                    # Reject connection with a custom close code for rate limiting
                    await send({"type": "websocket.close", "code": 4429})
                    return

        return await self.inner(scope, receive, send)

    def get_client_ip(self, scope):
        headers = dict(scope.get("headers", []))
        if b"x-forwarded-for" in headers:
            return headers[b"x-forwarded-for"].decode().split(",")[0].strip()
        client = scope.get("client")
        if client:
            return client[0]
        return None

    @sync_to_async
    def check_rate_limit(self, client_ip):
        # 60 handshake attempts per 60 seconds
        RATE_LIMIT = 60
        WINDOW = 60
        
        cache_key = f"ws_ratelimit_{client_ip}"
        
        try:
            current = cache.get(cache_key, 0)
            
            if current >= RATE_LIMIT:
                return False
                
            if current == 0:
                cache.set(cache_key, 1, WINDOW)
            else:
                try:
                    cache.incr(cache_key)
                except ValueError:
                    # In case the key expired between get and incr, or is not an integer
                    cache.set(cache_key, 1, WINDOW)
                    
            return True
        except Exception:
            # Fail open if cache is unreachable
            return True
