from channels.middleware import BaseMiddleware
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth import get_user_model
import jwt
from django.conf import settings

User = get_user_model()

class WebSocketAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        # Extract token from subprotocol
        subprotocols = scope.get('subprotocols', [])
        token = None
        
        # Check subprotocol (new method)
        if len(subprotocols) >= 2 and subprotocols[0] == 'token':
            token = subprotocols[1]
        
        # Fallback: Check query string (old method - for migration)
        if not token:
            query_string = scope.get('query_string', b'').decode()
            params = dict(q.split('=') for q in query_string.split('&') if '=' in q)
            token = params.get('token')
        
        # Validate token
        if token:
            try:
                payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
                user = await database_sync_to_async(User.objects.get)(id=payload['user_id'])
                scope['user'] = user
            except:
                scope['user'] = AnonymousUser()
        else:
            scope['user'] = AnonymousUser()
        
        return await super().__call__(scope, receive, send)


JWTAuthMiddleware = WebSocketAuthMiddleware

