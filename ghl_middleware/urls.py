from django.urls import path
from .views import WebhookPropiedadView, WebhookClienteView

urlpatterns = [
    path('webhooks/propiedad/', WebhookPropiedadView.as_view(), name='webhook_propiedad'),
    path('webhooks/cliente/', WebhookClienteView.as_view(), name='webhook_cliente'),
]
