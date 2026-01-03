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

# IMPORTANTE: Usamos la tarea en segundo plano para evitar Timeouts de GHL
from .tasks import sync_associations_background

logger = logging.getLogger(__name__)

# -------------------------------------------------------------------------
# HELPER INTERNO: LIMPIEZA DE DATOS
# -------------------------------------------------------------------------
def clean_currency(value):
    """Convierte '$150,000' o '150000.00' a float puro."""
    if not value:
        return 0.0
    try:
        # Eliminamos símbolos comunes de moneda
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
    """
    Maneja el handshake de OAuth 2.0.
    Crea la Agencia y guarda el Token inicial.
    """
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
                
                # 1. Guardar o Actualizar Token
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

                # 2. Crear/Activar Agencia en tu DB
                Agencia.objects.get_or_create(
                    location_id=location_id,
                    defaults={'active': True}
                )

                return Response({"message": "App instalada correctamente. Agencia lista.", "location_id": location_id}, status=200)
            
            logger.error(f"Error OAuth GHL: {tokens}")
            return Response(tokens, status=400)

        except Exception as e:
            logger.error(f"Excepción Crítica OAuth: {str(e)}")
            return Response({"error": str(e)}, status=500)


# -------------------------------------------------------------------------
# VISTA 2: WEBHOOK PROPIEDAD (Custom Object Trigger)
# -------------------------------------------------------------------------
class WebhookPropiedadView(APIView):
    """
    Recibe una Propiedad nueva/actualizada desde GHL.
    Busca Clientes compatibles y lanza la sincronización en background.
    """
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

        # 3. Preparar Datos para Django (Limpieza)
        prop_data = {
            'agencia': agencia.pk,
            'ghl_contact_id': ghl_record_id,
            'precio': clean_currency(custom_data.get('precio') or data.get('precio')),
            'habitaciones': clean_int(custom_data.get('habitaciones') or data.get('habitaciones')),
            'zona': custom_data.get('zona') or data.get('zona'),
            'estado': 'activo'
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
        
        # Filtro:
        # - Misma agencia
        # - Cliente quiere esta zona
        # - Cliente tiene presupuesto >= precio propiedad
        # - Cliente pide <= habitaciones que las que tiene la propiedad
        clientes_match = Cliente.objects.filter(
            agencia=agencia,
            zona_interes__iexact=propiedad.zona,
            presupuesto_maximo__gte=propiedad.precio,
            habitaciones_minimas__lte=propiedad.habitaciones 
        )

        matches_count = clientes_match.count()

        if matches_count > 0:
            # A) Guardado Local (Rápido)
            for cliente in clientes_match:
                cliente.propiedades_interes.add(propiedad)

            # B) Sincronización con GHL (Segundo Plano / Threading)
            try:
                token_obj = GHLToken.objects.get(location_id=location_id)
                
                # Preparamos lista de IDs para el Worker
                target_ids = [c.ghl_contact_id for c in clientes_match]
                
                # Lanzamos el hilo. NO BLOQUEA EL RETURN.
                sync_associations_background(
                    access_token=token_obj.access_token,
                    origin_record_id=propiedad.ghl_contact_id, # ID Propiedad
                    target_ids_list=target_ids,                # IDs Clientes
                    association_type="contact"
                )
                
            except GHLToken.DoesNotExist:
                logger.warning(f"⚠️ No hay token para {location_id}. Se guardó local pero no se sincronizó.")

        # Respuesta inmediata para GHL (evita error 504 Gateway Timeout)
        return Response({
            'status': 'success', 
            'action': 'created' if created else 'updated',
            'matches_found': matches_count,
            'background_sync': True
        }, status=status.HTTP_200_OK)


# -------------------------------------------------------------------------
# VISTA 3: WEBHOOK CLIENTE (Contact Created/Updated Trigger)
# -------------------------------------------------------------------------
class WebhookClienteView(APIView):
    """
    Recibe un Contacto nuevo/actualizado desde GHL.
    Busca Propiedades compatibles y lanza la sincronización en background.
    """
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        data = request.data
        logger.info(f"📥 Webhook Cliente recibido: {data}")
        
        # 1. Identificar Location
        custom_data = data.get('customData', {}) 
        location_data = data.get('location', {})
        location_id = location_data.get('id') or custom_data.get('location_id')
    
        if not location_id:
            return Response({'error': 'Missing location_id'}, status=status.HTTP_400_BAD_REQUEST)
            
        agencia = get_object_or_404(Agencia, location_id=location_id)
        
        # 2. Identificar ID del Contacto
        ghl_contact_id = data.get('id')
        if not ghl_contact_id:
             return Response({'error': 'Missing Contact ID'}, status=status.HTTP_400_BAD_REQUEST)

        # 3. Preparar Datos Cliente (Limpieza)
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
            return Response({'status': 'saved_no_zone', 'message': 'Cliente sin zona de interes'}, status=200)

        # Filtro:
        # - Misma agencia
        # - Propiedad en la zona del cliente
        # - Precio propiedad <= Presupuesto cliente
        # - Habitaciones propiedad >= Habitaciones mínimas cliente
        propiedades_match = Propiedad.objects.filter(
            agencia=agencia,
            zona__iexact=cliente.zona_interes,
            precio__lte=cliente.presupuesto_maximo,
            habitaciones__gte=cliente.habitaciones_minimas,
            estado='activo'
        )

        matches_count = propiedades_match.count()

        if matches_count > 0:
            # A) Guardado Local
            for prop in propiedades_match:
                cliente.propiedades_interes.add(prop)
            
            # B) Sincronización GHL (Segundo Plano / Threading)
            try:
                token_obj = GHLToken.objects.get(location_id=location_id)
                
                # Preparamos lista de IDs
                target_ids = [p.ghl_contact_id for p in propiedades_match]

                # Lanzamos el hilo
                # Nota: Aquí el 'origin' es la propiedad y target el cliente para la API, 
                # pero como es N:N podemos iterar al revés.
                # Sin embargo, mi worker está diseñado para "One Origin -> Many Targets".
                # Así que llamaremos al worker diciendo: "Este Cliente (Origin) se conecta con estas Propiedades (Targets)"
                
                # *IMPORTANTE*: Debemos asegurar que el association_type sea correcto.
                # Si Propiedad es Custom Object y Cliente es Contact, la asociación desde Cliente a Propiedad 
                # requiere que association_type sea el ID del Schema de Propiedad o similar.
                # Para simplificar y usar el endpoint estándar que ya probamos (Custom Object -> Contact),
                # invertiremos la lógica del worker solo para este caso, o mejor:
                
                # Vamos a iterar usando la lógica: "Por cada propiedad encontrada, asocia este cliente".
                # Esto es más seguro con el endpoint /custom-objects/.../associations
                
                # Opción Robusta: Pasar al worker la lista de propiedades como 'origins' y el cliente como 'target' único.
                # Pero como el worker está hecho para 1 Origin -> N Targets, usaremos un truco:
                # Lanzaremos la tarea con el Cliente como "Origin" SOLO SI el endpoint de Contactos soportara asociaciones.
                # Como GHL API v2 centra las asociaciones en los Custom Objects, lo ideal es iterar sobre las propiedades.
                
                # Solución Práctica para tu caso (usando el código actual de tasks.py):
                # Llamaremos a sync_associations_background pero le daremos la vuelta en el bucle dentro de Python 
                # o modificamos ligeramente tasks.py. 
                # PERO, para no romper tu tasks.py, usaremos esto:
                
                # Vamos a reutilizar el worker iterando al revés si es necesario, 
                # PERO la API dice: POST /custom-objects/{id}/associations.
                # Así que SIEMPRE el ID de la URL debe ser el Custom Object (Propiedad).
                
                # Por tanto, para el Cliente, iteramos aquí rápidamente para lanzar múltiples hilos pequeños 
                # o modificamos el worker. Para simplificar y que funcione YA:
                # Pasaremos: Origin = Cliente ID. Targets = Propiedades IDs.
                # PERO en tasks.py el endpoint hardcodeado apunta a /custom-objects/{record_id_1}.
                # Si record_id_1 es un Cliente, fallará.
                
                # CORRECCIÓN EN VIVO PARA QUE FUNCIONE PERFECTO:
                # En este caso específico (Cliente -> Propiedades), lanzaremos un hilo manual aquí simple
                # porque el worker asume CustomObject -> Contact.
                
                from .tasks import sync_associations_background
                # Nota: Si el task.py usa el endpoint de Custom Object, el primer parámetro debe ser SIEMPRE la Propiedad.
                
                # Así que haremos un bucle manual lanzando tareas unitarias al worker 
                # O (mejor) creamos una lista inversa.
                
                # Estrategia: "Este Cliente X se debe unir a Propiedades A, B, C".
                # La API exige llamar a Propiedad A -> Unir Cliente X. Propiedad B -> Unir Cliente X.
                
                # Solución:
                # Llamaremos a sync_associations_background POR CADA PROPIEDAD encontrada.
                # No es lo más eficiente en hilos, pero reutiliza tu código.
                for prop in propiedades_match:
                     sync_associations_background(
                        access_token=token_obj.access_token,
                        origin_record_id=prop.ghl_contact_id, # Custom Object (URL)
                        target_ids_list=[cliente.ghl_contact_id], # Lista de 1 Contacto
                        association_type="contact"
                    )

            except GHLToken.DoesNotExist:
                logger.warning(f"⚠️ No hay token para {location_id}.")

        return Response({
            'status': 'success', 
            'matches_found': matches_count,
            'background_sync': True
        })
