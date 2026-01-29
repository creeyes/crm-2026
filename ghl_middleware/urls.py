from django.urls import path
# Importamos también la vista del OAuth (GHLOAuthCallbackView) y la nueva GHLLaunchView
from .views import WebhookPropiedadView, WebhookClienteView, GHLOAuthCallbackView, HomeView, DebugGHLVie

urlpatterns = [
    

    # --- 2. RUTA OBLIGATORIA PARA INSTALAR LA APP (El Cruzado) ---
    # GHL llamará aquí: https://tu-dominio.railway.app/api/oauth/callback/
    path('oauth/callback/', GHLOAuthCallbackView.as_view(), name='ghl_oauth_callback'),

    # --- 3. TUS WEBHOOKS DE NEGOCIO ---
    path('webhooks/propiedad/', WebhookPropiedadView.as_view(), name='webhook_propiedad'),
    path('webhooks/cliente/', WebhookClienteView.as_view(), name='webhook_cliente'),
    path('ghl/debug/', DebugGHLView.as_view(), name='debug_ghl'),
]




