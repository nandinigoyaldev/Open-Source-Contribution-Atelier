import inspect
import logging

logger = logging.getLogger(__name__)

class TimezoneSafetyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        for frame_info in inspect.stack():
            code_context = frame_info.code_context
            if code_context and "datetime.now(" in "".join(code_context):
                logger.warning(
                    "Detected datetime.now() usage during request processing in %s.",
                    frame_info.filename
                )
                break

        return self.get_response(request)
