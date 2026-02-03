"""
URL configuration for GHL_Front app.
"""
from django.urls import path
from . import views
from .views import PublicPropertyList

app_name = 'ghl_front'

urlpatterns = [
    # Endpoint público: /api/front/properties/?agency_id=XXX
    path('api/properties/', PublicPropertyList.as_view(), name='public_properties'),
]
