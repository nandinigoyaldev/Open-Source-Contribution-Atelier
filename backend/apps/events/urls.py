"""
URL configuration for events app.
"""

from django.urls import path
from . import views

app_name = 'events'

urlpatterns = [
    # Event management
    path('events/', views.EventListView.as_view(), name='event_list'),
    path('events/<uuid:pk>/', views.EventDetailView.as_view(), name='event_detail'),
    path('events/<uuid:pk>/retry/', views.EventRetryView.as_view(), name='event_retry'),
    
    # Handler management
    path('handlers/', views.HandlerListView.as_view(), name='handler_list'),
    path('handlers/<int:pk>/toggle/', views.HandlerToggleView.as_view(), name='handler_toggle'),
]