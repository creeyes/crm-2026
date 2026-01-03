# views.py
import logging
import requests
from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .models import Agencia, Propiedad, Cliente, GHLToken
from .serializers import PropiedadSerializer, ClienteSerializer
# Importamos la función de ayuda que creamos arriba
from .utils import ghl_associate_records 

logger = logging.getLogger(__name__)

# -------------------------------------------------------------------------
# HELPER INTERNO: LIMPIEZA DE DATOS
# -------------------------------------------------------------------------
def clean_currency(value):
    """Convierte '$150,000' o '150000.00' a float puro."""
    if not value:
        return 0.0
    try:
        return float(str(value).replace('$', '').replace(',', '').strip())
    except ValueError:
        return 0.0

def clean_int(value):
    """Asegura que devolvemos un entero, default 0."""
    if not value:
        return 0
    try:
        return int(float(str(value))) # float primero por si viene "2.0"
    except ValueError:
        return 0

# -------------------------------------------------------------------------
# VISTA 1: OAUTH CALLBACK (Instalación)
# -------------------------------------------------------------------------
class GHLOAuthCallbackView(APIView):
    permission_classes = []

    def get(self, request):
        code = request.query_params.get('code')
        if not code:
            return Response({"error": "No code provided"}, status=400)

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
                
                # Guardar Token
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

                # Crear/Activar Agencia
                Agencia.objects.get_or_create(
                    location_id=location_id,
                    defaults={'active': True}
                )

                return Response({"message": "App instalada. Agencia lista.", "location_id": location_id}, status=200)
            
            logger.error(f"Error OAuth GHL: {tokens}")
            return Response(tokens, status=400)

        except Exception as e:
            logger.error(f"Excepción OAuth: {str(e)}")
            return Response({"error": str(e)}, status=500)


# -------------------------------------------------------------------------
# VISTA 2: WEBHOOK PROPIEDAD (Custom Object Trigger)
# -------------------------------------------------------------------------
class WebhookPropiedadView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        data = request.data
        logger.info(f"📥 Webhook Propiedad recibido: {data}")
        
        # 1. Identificar Location
        custom_data = data.get('customData', {})
        location_data = data.get('location', {})
        location_id = location_data.get('id') or custom_data.get('location_id')
        
        if not location_id:
            return Response({'error': 'Missing location_id'}, status=status.HTTP_400_BAD_REQUEST)
            
        agencia = get_object_or_404(Agencia, location_id=location_id)
        
        # 2. Identificar ID del Objeto Propiedad
        ghl_record_id = custom_data.get('contact_id') or data.get('id')
        if not ghl_record_id:
             return Response({'error': 'Missing Record ID'}, status=status.HTTP_400_BAD_REQUEST)

        # 3. Preparar Datos para Django
        prop_data = {
            'agencia': agencia.pk,
            'ghl_contact_id': ghl_record_id,
            'precio': clean_currency(custom_data.get('precio') or data.get('precio')),
            'habitaciones': clean_int(custom_data.get('habitaciones') or data.get('habitaciones')),
            'zona': custom_data.get('zona') or data.get('zona'),
            'estado': 'activo' # Asumimos activo al crearse/actualizarse
        }
        
        # 4. Guardar/Actualizar Propiedad Localmente
        propiedad, created = Propiedad.objects.update_or_create(
            agencia=agencia, 
            ghl_contact_id=ghl_record_id, 
            defaults=prop_data
        )

        # -------------------------------------------------------
        # LOGICA DE MATCHING: Propiedad Nueva -> Busca Clientes
        # -------------------------------------------------------
        
        # Buscamos clientes que:
        # a) Sean de la misma agencia
        # b) Quieran la misma zona
        # c) Tengan presupuesto suficiente (>= precio propiedad)
        # d) Busquen <= habitaciones que las que tiene esta propiedad
        clientes_match = Cliente.objects.filter(
            agencia=agencia,
            zona_interes__iexact=propiedad.zona,
            presupuesto_maximo__gte=propiedad.precio,
            habitaciones_minimas__lte=propiedad.habitaciones 
        )

        matches_synced = 0
        
        if clientes_match.exists():
            # Obtener token para sincronizar con GHL
            try:
                token_obj = GHLToken.objects.get(location_id=location_id)
                access_token = token_obj.access_token
                # TODO: Aquí deberías verificar si el token expiró y refrescarlo si es necesario
            except GHLToken.DoesNotExist:
                logger.warning(f"⚠️ No hay token para {location_id}. Se guardó local pero no se sincronizó.")
                return Response({'status': 'saved_local', 'matches': 0}, status=200)

            for cliente in clientes_match:
                # 1. Guardar relación en Django (Historial Many-to-Many)
                cliente.propiedades_interes.add(propiedad)
                
                # 2. Llamada API a GHL
                success = ghl_associate_records(
                    access_token=access_token,
                    record_id_1=propiedad.ghl_contact_id, # Custom Object ID
                    record_id_2=cliente.ghl_contact_id,   # Contact ID
                    association_type="contact"
                )
                if success:
                    matches_synced += 1

        return Response({
            'status': 'success', 
            'action': 'created' if created else 'updated',
            'matches_found_and_synced': matches_synced
        }, status=status.HTTP_200_OK)


# -------------------------------------------------------------------------
# VISTA 3: WEBHOOK CLIENTE (Contact Created/Updated Trigger)
# -------------------------------------------------------------------------
class WebhookClienteView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        data = request.data
        logger.info(f"📥 Webhook Cliente recibido: {data}")
        
        # 1. Identificar Location
        custom_data = data.get('customData', {}) # Campos custom están aquí
        location_data = data.get('location', {})
        location_id = location_data.get('id') or custom_data.get('location_id')
    
        if not location_id:
            return Response({'error': 'Missing location_id'}, status=status.HTTP_400_BAD_REQUEST)
            
        agencia = get_object_or_404(Agencia, location_id=location_id)
        
        # 2. Identificar ID del Contacto
        ghl_contact_id = data.get('id') # En contact update, el ID suele venir en la raíz
        if not ghl_contact_id:
             return Response({'error': 'Missing Contact ID'}, status=status.HTTP_400_BAD_REQUEST)

        # 3. Preparar Datos Cliente
        # Nota: Asegúrate que los keys coincidan con como GHL envía tus Custom Fields (ej. 'presupuesto_maximo')
        cliente_data = {
            'agencia': agencia.pk,
            'ghl_contact_id': ghl_contact_id,
            'nombre': f"{data.get('first_name', '')} {data.get('last_name', '')}".strip(),
            'presupuesto_maximo': clean_currency(custom_data.get('presupuesto') or data.get('presupuesto')),
            'habitaciones_minimas': clean_int(custom_data.get('habitaciones') or data.get('habitaciones_min')),
            'zona_interes': custom_data.get('zona_interes')        
        }

        # 4. Guardar/Actualizar Cliente Localmente
        cliente, created = Cliente.objects.update_or_create(
            agencia=agencia, 
            ghl_contact_id=ghl_contact_id, 
            defaults=cliente_data
        )

        # -------------------------------------------------------
        # LOGICA DE MATCHING: Cliente Nuevo -> Busca Propiedades
        # -------------------------------------------------------
        
        if not cliente.zona_interes:
            # Si no ha definido zona, difícilmente hacemos match. Retornamos early.
            return Response({'status': 'saved_no_zone'}, status=200)

        # Buscamos propiedades que:
        # a) Sean de la misma agencia
        # b) Estén en la zona de interés
        # c) Tengan precio <= presupuesto del cliente
        # d) Tengan >= habitaciones que las que pide el cliente
        propiedades_match = Propiedad.objects.filter(
            agencia=agencia,
            zona__iexact=cliente.zona_interes,
            precio__lte=cliente.presupuesto_maximo,
            habitaciones__gte=cliente.habitaciones_minimas,
            estado='activo'
        )

        matches_synced = 0

        if propiedades_match.exists():
            try:
                token_obj = GHLToken.objects.get(location_id=location_id)
                access_token = token_obj.access_token
            except GHLToken.DoesNotExist:
                logger.warning(f"⚠️ No hay token para {location_id}.")
                return Response({'status': 'saved_local', 'matches': 0}, status=200)

            for prop in propiedades_match:
                # 1. Guardar relación en Django (Historial)
                cliente.propiedades_interes.add(prop)
                
                # 2. Llamada API a GHL (Espejo)
                success = ghl_associate_records(
                    access_token=access_token,
                    record_id_1=prop.ghl_contact_id, # Custom Object
                    record_id_2=cliente.ghl_contact_id, # Contact
                    association_type="contact"
                )
                if success:
                    matches_synced += 1
            
            return Response({
                'status': 'success', 
                'matches_found_and_synced': matches_synced,
                'data_preview': [p.zona for p in propiedades_match]
            })

        return Response({'status': 'success', 'matches_synced': 0})
