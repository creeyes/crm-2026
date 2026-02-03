"""
URL configuration for GHL_Front app.
"""
from django.urls import path
from . import views

app_name = 'ghl_front'

urlpatterns = [
    path('api/public/properties/', PublicPropertyList.as_view(), name='public_properties'),
]
