"""
URL configuration for lynx project.
"""
from django.urls import path, include
from django.http import HttpResponse

urlpatterns = [
    path('', lambda r: HttpResponse("LynX Webhook Server is running!")),
    path('agent/', include('agent.urls')),
]
