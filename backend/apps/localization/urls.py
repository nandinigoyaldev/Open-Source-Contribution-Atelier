from django.urls import path
from .views import TranslationDictionaryView

urlpatterns = [
    path(
        "dictionary/<str:lang_code>/",
        TranslationDictionaryView.as_view(),
        name="translation-dictionary",
    ),
]
