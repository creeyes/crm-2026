from django.urls import path
from .views import PublicPropertyList

app_name = 'ghl_front'

urlpatterns = [
    # Ejemplo de uso: /api/properties/?agency_id=tu_location_id
    path('api/properties/', PublicPropertyList.as_view(), name='public_properties'),
    path('api/properties/<str:ghl_contact_id>/', PublicPropertyDetail.as_view(), name='public_property_detail'),
]
