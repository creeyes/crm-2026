import logging
import requests
from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .models import Agencia, Propiedad, Cliente, GHLToken
# Asegúrate de importar la Tarea de segundo plano
from .tasks import sync_associations_background

logger = logging.getLogger(__name__)

# -------------------------------------------------------------------------
# HELPER INTERNO: LIMPIEZA DE DATOS
# -------------------------------------------------------------------------
def clean_currency(value):
    if not value:
        return 0.0
    try:
        return float(str(value).replace('$', '').replace(',', '').strip())
    except ValueError:
        return 0.0

def clean_int(value):
    if not value:
        return 0
    try:
        return int(float(str(value)))
    except ValueError:
        return 0

# -------------------------------------------------------------------------
# VISTA 1: OAUTH CALLBACK
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

                Agencia.objects.get_or_create(
                    location_id=location_id,
                    defaults={'active': True}
                )

                return Response({"message": "App instalada.", "location_id": location_id}, status=200)
            
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
        logger.info(f"📥 Webhook Propiedad: {data}")
        
        custom_data = data.get('customData', {})
        location_data = data.get('location', {})
        location_id = location_data.get('id') or custom_data.get('location_id')
        
        if not location_id:
            return Response({'error': 'Missing location_id'}, status=status.HTTP_400_BAD_REQUEST)
            
        agencia = get_object_or_404(Agencia, location_id=location_id)
        
        ghl_record_id = custom_data.get('contact_id') or data.get('id')
        if not ghl_record_id:
             return Response({'error': 'Missing Record ID'}, status=status.HTTP_400_BAD_REQUEST)

        prop_data = {
            'agencia': agencia.pk,
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

        # MATCHING: Propiedad -> Clientes
        clientes_match = Cliente.objects.filter(
            agencia=agencia,
            zona_interes__iexact=propiedad.zona,
            presupuesto_maximo__gte=propiedad.precio,
            habitaciones_minimas__lte=propiedad.habitaciones 
        )

        matches_count = clientes_match.count()

        if matches_count > 0:
            for cliente in clientes_match:
                cliente.propiedades_interes.add(propiedad)

            try:
                token_obj = GHLToken.objects.get(location_id=location_id)
                target_ids = [c.ghl_contact_id for c in clientes_match]
                
                # Caso Propiedad -> Muchos Clientes:
                # Enviamos una sola tarea con la lista de clientes
                sync_associations_background(
                    access_token=token_obj.access_token,
                    origin_record_id=propiedad.ghl_contact_id,
                    target_ids_list=target_ids,
                    association_type="contact"
                )
                
            except GHLToken.DoesNotExist:
                logger.warning(f"⚠️ No token for {location_id}")

        return Response({
            'status': 'success', 
            'matches_found': matches_count,
            'background_sync': True
        }, status=status.HTTP_200_OK)


# -------------------------------------------------------------------------
# VISTA 3: WEBHOOK CLIENTE (Contact Created/Updated Trigger)
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
    
        if not location_id:
            return Response({'error': 'Missing location_id'}, status=status.HTTP_400_BAD_REQUEST)
            
        agencia = get_object_or_404(Agencia, location_id=location_id)
        
        # TU CORRECCIÓN AQUI:
        ghl_contact_id = data.get('id') or custom_data.get('contact_id')
        if not ghl_contact_id:
             return Response({'error': 'Missing Contact ID'}, status=status.HTTP_400_BAD_REQUEST)

        cliente_data = {
            'agencia': agencia.pk,
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
        
        if not cliente.zona_interes:
            return Response({'status': 'saved_no_zone'}, status=200)

        # MATCHING: Cliente -> Propiedades
        propiedades_match = Propiedad.objects.filter(
            agencia=agencia,
            zona__iexact=cliente.zona_interes,
            precio__lte=cliente.presupuesto_maximo,
            habitaciones__gte=cliente.habitaciones_minimas,
            estado='activo'
        )

        matches_count = propiedades_match.count()

        if matches_count > 0:
            for prop in propiedades_match:
                cliente.propiedades_interes.add(prop)
            
            try:
                token_obj = GHLToken.objects.get(location_id=location_id)
                
                # Caso Cliente -> Muchas Propiedades:
                # La API requiere que la URL sea el Custom Object (Propiedad).
                # Por eso, lanzamos una tarea POR CADA propiedad encontrada.
                for prop in propiedades_match:
                     sync_associations_background(
                        access_token=token_obj.access_token,
                        origin_record_id=prop.ghl_contact_id, # La URL será la propiedad
                        target_ids_list=[cliente.ghl_contact_id], # El target es este cliente
                        association_type="contact"
                    )

            except GHLToken.DoesNotExist:
                logger.warning(f"⚠️ No token for {location_id}")

        return Response({
            'status': 'success', 
            'matches_found': matches_count,
            'background_sync': True
        })
