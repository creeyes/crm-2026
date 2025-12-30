import logging
import requests
from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import Agencia, Propiedad, Cliente, GHLToken
from .serializers import PropiedadSerializer, ClienteSerializer

# Configuración de logs para ver errores en Railway
logger = logging.getLogger(__name__)

# -------------------------------------------------------------------------
# PARTE 1: EL CRUZADO (Instalación de la App / OAuth)
# -------------------------------------------------------------------------

class GHLOAuthCallbackView(APIView):
    """
    Endpoint CRÍTICO: Recibe el código de GHL, genera el Token y crea la Agencia.
    Sin esto, la app no se puede instalar y los webhooks darán error 404.
    """
    permission_classes = [] # Abierto para el handshake

    def get(self, request):
        code = request.query_params.get('code')
        if not code:
            return Response({"error": "No code provided"}, status=400)

        # 1. Intercambio de Código por Token (El handshake)
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
                
                # 2. Guardamos el Token (Opcional pero recomendado)
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

                # 3. CREAMOS LA AGENCIA AUTOMÁTICAMENTE
                # Esto es vital para que tus Webhooks de abajo funcionen y no den 404
                Agencia.objects.get_or_create(
                    location_id=location_id,
                    defaults={'active': True}
                )

                logger.info(f"App instalada correctamente en location: {location_id}")
                return Response({"message": "App instalada con éxito. Agencia creada.", "location_id": location_id}, status=200)
            
            logger.error(f"Error en OAuth GHL: {tokens}")
            return Response(tokens, status=400)

        except Exception as e:
            logger.error(f"Excepción critica en OAuth: {str(e)}")
            return Response({"error": str(e)}, status=500)


# -------------------------------------------------------------------------
# PARTE 2: TU LÓGICA DE NEGOCIO (Webhooks)
# -------------------------------------------------------------------------

class WebhookPropiedadView(APIView):
    """
    Endpoint para Crear/Actualizar/Borrar Propiedades desde GHL.
    """
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        data = request.data
        logger.info(f"Propiedad Webhook Data: {data}")
        
        # 1. Lógica unificada para extraer location_id
        location_data = data.get('location', {})
        custom_data = data.get('customData', {}) 
        
        location_id = location_data.get('id') or custom_data.get('location_id')
        
        if not location_id:
            return Response({'error': 'Missing location_id'}, status=status.HTTP_400_BAD_REQUEST)
            
        # IMPORTANTE: Busca la agencia creada por el OAuth de arriba
        agencia = get_object_or_404(Agencia, location_id=location_id)
        
        # Extraemos IDs
        ghl_contact_id = custom_data.get('contact_id') or data.get('contact_id') or data.get('id')
        action = data.get('type', 'update')

        if not ghl_contact_id:
            return Response({'error': 'Missing contact_id'}, status=status.HTTP_400_BAD_REQUEST)

        if action == 'delete':
            deleted, _ = Propiedad.objects.filter(agencia=agencia, ghl_contact_id=ghl_contact_id).delete()
            return Response({'status': 'deleted', 'count': deleted})

        # Preparar datos (con saneamiento básico de precio)
        try:
            precio_raw = custom_data.get('precio') or data.get('precio') or 0
            # Limpieza simple por si viene "$100,000"
            precio_clean = float(str(precio_raw).replace(',', '').replace('$', ''))
        except ValueError:
            precio_clean = 0

        prop_data = {
            'agencia': agencia.pk,
            'ghl_contact_id': ghl_contact_id,
            'precio': precio_clean,
            'zona': custom_data.get('zona') or data.get('zona'),
            'habitaciones': custom_data.get('habitaciones') or data.get('habitaciones'),
            'estado': 'activo'
        }
        
        try:
            propiedad = Propiedad.objects.get(agencia=agencia, ghl_contact_id=ghl_contact_id)
            serializer = PropiedadSerializer(propiedad, data=prop_data)
        except Propiedad.DoesNotExist:
            serializer = PropiedadSerializer(data=prop_data)

        if serializer.is_valid():
            serializer.save()
            return Response({'status': 'success', 'data': serializer.data}, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class WebhookClienteView(APIView):
    """
    Endpoint para Crear/Actualizar Clientes y disparar Matching.
    """
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        data = request.data
        logger.info(f"Cliente Webhook Data: {data}")
        
        # 1. Lógica unificada para extraer location_id
        location_data = data.get('location', {})
        custom_data = data.get('customData', {}) 
        
        location_id = location_data.get('id') or custom_data.get('location_id')
    
        if not location_id:
            return Response({'error': 'Missing location_id'}, status=status.HTTP_400_BAD_REQUEST)
            
        agencia = get_object_or_404(Agencia, location_id=location_id)
        
        # Extraemos IDs
        ghl_contact_id = custom_data.get('contact_id') or data.get('contact_id') or data.get('id')
        
        if not ghl_contact_id:
            return Response({'error': 'Missing contact_id'}, status=status.HTTP_400_BAD_REQUEST)

        # Preparar datos del cliente
        try:
            presupuesto_raw = custom_data.get('presupuesto') or 0
            presupuesto_clean = float(str(presupuesto_raw).replace(',', '').replace('$', ''))
        except ValueError:
            presupuesto_clean = 0

        cliente_data = {
            'agencia': agencia.pk,
            'ghl_contact_id': ghl_contact_id,
            'nombre': data.get('first_name') or data.get('full_name') or 'Unknown',
            'presupuesto_maximo': presupuesto_clean,
            'zona_interes': custom_data.get('zona_interes')        
        }

        try:
            cliente = Cliente.objects.get(agencia=agencia, ghl_contact_id=ghl_contact_id)
            serializer = ClienteSerializer(cliente, data=cliente_data)
        except Cliente.DoesNotExist:
            serializer = ClienteSerializer(data=cliente_data)

        if serializer.is_valid():
            cliente = serializer.save()
            
            # Disparar lógica de Matching
            coincidencias = self.encontrar_coincidencias(cliente)
            
            matches_serializer = PropiedadSerializer(coincidencias, many=True)

            return Response({
                'status': 'success',
                'cliente_id': cliente.id,
                'matches_found': len(coincidencias),
                'matches': matches_serializer.data
            })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def encontrar_coincidencias(self, cliente):
        # Nota: Asegúrate que cliente.zona_interes no sea None antes de filtrar
        if not cliente.zona_interes:
            return Propiedad.objects.none()

        budget = cliente.presupuesto_maximo if cliente.presupuesto_maximo else 999999999

        return Propiedad.objects.filter(
            agencia=cliente.agencia,
            zona__iexact=cliente.zona_interes,
            precio__lte=budget, 
            estado='activo'
        )
