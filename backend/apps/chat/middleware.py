import json
import re

BAD_WORDS = {"fuck", "shit", "bitch", "asshole", "cunt", "dick", "bastard"}


class ProfanityFilterMiddleware:
    """
    ASGI middleware that intercepts incoming WebSocket messages,
    auto-censors profanity, and drops messages detected as spam.
    """

    def __init__(self, inner):
        self.inner = inner

    def filter_message(self, text):
        is_spam = False

        # Simple spam heuristic: > 100 chars and > 50% uppercase
        if len(text) > 100:
            upper_count = sum(1 for c in text if c.isupper())
            if upper_count / len(text) > 0.5:
                is_spam = True

        # Or multiple URLs
        urls = re.findall(r"https?://[^\s]+", text)
        if len(urls) >= 3:
            is_spam = True

        # Censor profanity
        filtered_text = text
        for word in BAD_WORDS:
            pattern = re.compile(re.escape(word), re.IGNORECASE)
            # Create replacement string of same length as matched word
            filtered_text = pattern.sub(lambda m: "*" * len(m.group()), filtered_text)

        return filtered_text, is_spam

    async def __call__(self, scope, receive, send):
        # Only apply to chat websocket connections
        if scope["type"] == "websocket" and "/ws/chat/" in scope.get("path", ""):

            async def filtered_receive():
                while True:
                    message = await receive()
                    if message["type"] == "websocket.receive":
                        text_data = message.get("text")
                        if text_data:
                            try:
                                data = json.loads(text_data)
                                if (
                                    data.get("action") == "send_message"
                                    and "message" in data
                                ):
                                    original = data["message"]
                                    filtered, is_spam = self.filter_message(original)
                                    if is_spam:
                                        # Drop the message and notify sender
                                        await send(
                                            {
                                                "type": "websocket.send",
                                                "text": json.dumps(
                                                    {
                                                        "type": "error",
                                                        "message": "Message blocked: spam detected.",
                                                    }
                                                ),
                                            }
                                        )
                                        continue  # wait for next message
                                    else:
                                        data["message"] = filtered
                                        message["text"] = json.dumps(data)
                            except Exception:
                                pass
                    return message

            return await self.inner(scope, filtered_receive, send)

        return await self.inner(scope, receive, send)
