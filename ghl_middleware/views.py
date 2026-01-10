# views.py
import logging
import requests
from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .models import Agencia, Propiedad, Cliente, GHLToken
from .tasks import sync_associations_background

logger = logging.getLogger(__name__)

# --- HELPER INTERNO: PORTADA ---
class HomeView(APIView):
    permission_classes = []
    def get(self, request):
        return Response({"message": "Server is running 🚀"}, status=200)

def clean_currency(value):
    if not value: return 0.0
    try: return float(str(value).replace('$', '').replace(',', '').strip())
    except ValueError: return 0.0

def clean_int(value):
    if not value: return 0
    try: return int(float(str(value)))
    except ValueError: return 0

# -------------------------------------------------------------------------
# VISTA 1: OAUTH CALLBACK (Sin cambios mayores, solo mantener imports)
# -------------------------------------------------------------------------
class GHLOAuthCallbackView(APIView):
    permission_classes = []
    def get(self, request):
        code = request.query_params.get('code')
        if not code: return Response({"error": "No code provided"}, status=400)
        
        token_url = "https://services.leadconnectorhq.com/oauth/token"
        data = {
            'client_id': settings.GHL_CLIENT_ID,
            'client_secret': settings.GHL_CLIENT_SECRET,
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': settings.GHL_REDIRECT_URI,
        }
        try:
            response = requests.post(token_url, data=data)
            tokens = response.json()
            if response.status_code == 200:
                location_id = tokens.get('locationId')
                GHLToken.objects.update_or_create(
                    location_id=location_id,
                    defaults={
                        'access_token': tokens['access_token'],
                        'refresh_token': tokens['refresh_token'],
                        'token_type': tokens['token_type'],
                        'expires_in': tokens['expires_in'],
                        'scope': tokens['scope']
                    }
                )
                Agencia.objects.get_or_create(location_id=location_id, defaults={'active': True})
                return Response({"message": "App instalada.", "location_id": location_id}, status=200)
            logger.error(f"Error OAuth GHL: {tokens}")
            return Response(tokens, status=400)
        except Exception as e:
            logger.error(f"Excepción OAuth: {str(e)}")
            return Response({"error": str(e)}, status=500)

# -------------------------------------------------------------------------
# VISTA 2: WEBHOOK PROPIEDAD (MODIFICADO)
# -------------------------------------------------------------------------
class WebhookPropiedadView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        data = request.data
        logger.info(f"📥 Webhook Propiedad: {data}")
        
        custom_data = data.get('customData', {})
        location_data = data.get('location', {})
        location_id = location_data.get('id') or custom_data.get('location_id')
        
        if not location_id:
            return Response({'error': 'Missing location_id'}, status=400)
            
        agencia = get_object_or_404(Agencia, location_id=location_id)
        ghl_record_id = custom_data.get('contact_id') or data.get('id')
        
        if not ghl_record_id:
             return Response({'error': 'Missing Record ID'}, status=400)

        prop_data = {
            'agencia': agencia, 
            'ghl_contact_id': ghl_record_id,
            'precio': clean_currency(custom_data.get('precio') or data.get('precio')),
            'habitaciones': clean_int(custom_data.get('habitaciones') or data.get('habitaciones')),
            'zona': custom_data.get('zona') or data.get('zona'),
            'estado': 'activo'
        }
        
        propiedad, created = Propiedad.objects.update_or_create(
            agencia=agencia, 
            ghl_contact_id=ghl_record_id, 
            defaults=prop_data
        )

        # 1. BUSCAR NUEVOS MATCHES
        clientes_match = Cliente.objects.filter(
            agencia=agencia,
            zona_interes__iexact=propiedad.zona,
            presupuesto_maximo__gte=propiedad.precio,
            habitaciones_minimas__lte=propiedad.habitaciones 
        )

        # 2. ACTUALIZACIÓN LOCAL (DJANGO)
        # IMPORTANTE: Primero limpiamos las relaciones antiguas de esta propiedad
        # 'cliente_set' es el nombre por defecto si no definiste related_name en Cliente
        propiedad.cliente_set.clear() 
        
        # Ahora añadimos SOLO los matches vigentes
        for cliente in clientes_match:
            cliente.propiedades_interes.add(propiedad)

        # 3. SINCRONIZACIÓN CON GHL (DELTA SYNC)
        matches_count = clientes_match.count()
        if matches_count >= 0: # Ejecutamos siempre para limpiar si matches_count es 0
            try:
                token_obj = GHLToken.objects.get(location_id=location_id)
                target_ids = [c.ghl_contact_id for c in clientes_match]
                
                sync_associations_background(
                    access_token=token_obj.access_token,
                    location_id=location_id,
                    origin_record_id=propiedad.ghl_contact_id,
                    target_ids_list=target_ids, # Esta es la lista "Verdadera"
                    association_type="contact"
                )
            except GHLToken.DoesNotExist:
                logger.warning(f"⚠️ No token for {location_id}")

        return Response({'status': 'success', 'matches_found': matches_count})

# -------------------------------------------------------------------------
# VISTA 3: WEBHOOK CLIENTE (MODIFICADO)
# -------------------------------------------------------------------------
class WebhookClienteView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        data = request.data
        logger.info(f"📥 Webhook Cliente: {data}")
        
        custom_data = data.get('customData', {}) 
        location_data = data.get('location', {})
        location_id = location_data.get('id') or custom_data.get('location_id')
    
        if not location_id: return Response({'error': 'Missing location_id'}, status=400)
            
        agencia = get_object_or_404(Agencia, location_id=location_id)
        ghl_contact_id = data.get('id') or custom_data.get('contact_id')
        
        if not ghl_contact_id: return Response({'error': 'Missing Contact ID'}, status=400)

        cliente_data = {
            'agencia': agencia, 
            'ghl_contact_id': ghl_contact_id,
            'nombre': f"{data.get('first_name', '')} {data.get('last_name', '')}".strip(),
            'presupuesto_maximo': clean_currency(custom_data.get('presupuesto') or data.get('presupuesto')),
            'habitaciones_minimas': clean_int(custom_data.get('habitaciones') or data.get('habitaciones_min')),
            'zona_interes': custom_data.get('zona_interes')        
        }

        cliente, created = Cliente.objects.update_or_create(
            agencia=agencia, 
            ghl_contact_id=ghl_contact_id, 
            defaults=cliente_data
        )
        
        # 1. BUSCAR MATCHES
        propiedades_match = Propiedad.objects.filter(
            agencia=agencia,
            zona__iexact=cliente.zona_interes,
            precio__lte=cliente.presupuesto_maximo,
            habitaciones__gte=cliente.habitaciones_minimas,
            estado='activo'
        )

        # 2. ACTUALIZACIÓN LOCAL
        # Borramos las propiedades anteriores del cliente para actualizar su lista
        cliente.propiedades_interes.clear()
        
        for prop in propiedades_match:
            cliente.propiedades_interes.add(prop)
            
        # 3. SINCRONIZACIÓN CON GHL (DELTA SYNC)
        # OJO: Aquí es más complejo porque el SYNC está diseñado "1 Propiedad -> N Clientes".
        # Si entra un CLIENTE, tenemos que iterar por CADA propiedad que hizo match
        # y actualizarla a ella.
        
        matches_count = propiedades_match.count()
        if matches_count > 0:
            try:
                token_obj = GHLToken.objects.get(location_id=location_id)
                
                # Para cada propiedad que coincida, necesitamos recalcular sus inquilinos.
                # Esto es un poco intensivo pero necesario para la consistencia.
                for prop in propiedades_match:
                    # Obtenemos TODOS los clientes interesados en ESTA propiedad específica
                    # (incluyendo el nuevo cliente que acaba de entrar)
                    todos_los_interesados = prop.cliente_set.all()
                    target_ids = [c.ghl_contact_id for c in todos_los_interesados]

                    sync_associations_background(
                        access_token=token_obj.access_token,
                        location_id=location_id,
                        origin_record_id=prop.ghl_contact_id, 
                        target_ids_list=target_ids,
                        association_type="contact"
                    )

            except GHLToken.DoesNotExist:
                logger.warning(f"⚠️ No token for {location_id}")

        return Response({'status': 'success', 'matches_found': matches_count})
