from rest_framework import views, permissions
from rest_framework.response import Response
from .models import LocalizedContent


class TranslationDictionaryView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, lang_code):
        translations = LocalizedContent.objects.filter(language_code=lang_code)
        dictionary = {item.key: item.translation for item in translations}
        return Response(dictionary)
