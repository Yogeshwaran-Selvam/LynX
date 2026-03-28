"""
URL configuration for lynx project.
"""
from django.urls import path, include

urlpatterns = [
    path('agent/', include('agent.urls')),
]
