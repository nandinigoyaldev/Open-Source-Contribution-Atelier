from django.utils import translation

class LocaleMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        language = request.headers.get('Accept-Language', 'en-us')
        translation.activate(language)
        request.LANGUAGE_CODE = translation.get_language()
        
        try:
            response = self.get_response(request)
            return response
        finally:
            translation.deactivate()
