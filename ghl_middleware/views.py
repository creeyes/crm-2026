# views.py
import logging
import requests
from django.conf import settings
from django.shortcuts import get_object_or_404, redirect # <--- AÑADIDO: redirect
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Q

from .models import Agencia, Propiedad, Cliente, GHLToken, Zona
from .tasks import sync_associations_background
from .utils import get_valid_token  # <--- IMPORTANTE: Importamos la función de refresco

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

def preferenciasTraductor1(value):
    mapa = {
        "si": Cliente.Preferencias1.SI,
        "no": Cliente.Preferencias1.NO,
    }
    value = (value or "").lower()
    return mapa.get(value, Cliente.Preferencias1.NO)

def preferenciasTraductor2(value):
    mapa = {
        "si": Cliente.Preferencias2.SI,
        "indiferente": Cliente.Preferencias2.IND
    }
    value = value.lower()
    return mapa.get(value, Cliente.Preferencias2.IND)

def estadoPropTrad(value):
    mapa = {
        "vendido": Propiedad.estadoPiso.VENDIDO,
        "a la venta": Propiedad.estadoPiso.ACTIVO,
        "no es oficial": Propiedad.estadoPiso.NoOficial
    }
    value = value.replace("_"," ").lower()
    return mapa.get(value, Propiedad.estadoPiso.NoOficial)

def guardadorURL(value):
    lista = []
    if value != "null":
        lista = [data.get('url') for data in value if data.get('url')]
    return lista

# -------------------------------------------------------------------------
# VISTA NUEVA: LANZADOR DESDE MENU (Custom Menu Link)
# -------------------------------------------------------------------------
class GHLLaunchView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        # Recibe el location_id desde el parámetro de la URL del Custom Menu Link
        location_id = request.query_params.get('location_id')
        
        if not location_id:
            return Response({"error": "No location_id provided. Accede desde el menú de GHL."}, status=400)

        # 1. Verificamos si ya existe la conexión (Token) para esta subcuenta
        if GHLToken.objects.filter(location_id=location_id).exists():
            return Response({
                "status": "Conectado", 
                "message": f"✅ La agencia {location_id} ya está activa y sincronizada."
            }, status=200)
        
        # 2. Si NO existe, construimos la URL de autorización y redirigimos
        base_auth_url = "https://marketplace.leadconnectorhq.com/oauth/authorize"
        client_id = settings.GHL_CLIENT_ID
        redirect_uri = settings.GHL_REDIRECT_URI
        # Asegúrate de tener GHL_SCOPES definido en settings.py como una lista de strings
        scopes = " ".join(settings.GHL_SCOPES) 
        user_type = "Location"
        
        auth_url = (
            f"{base_auth_url}?"
            f"client_id={client_id}&"
            f"redirect_uri={redirect_uri}&"
            f"scope={scopes}&"
            f"response_type=code&"
            f"user_type={user_type}"
        )
        
        # Redirección automática a la pantalla de "Allow" de GHL
        return redirect(auth_url)

# -------------------------------------------------------------------------
# VISTA 1: OAUTH CALLBACK
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
# VISTA 2: WEBHOOK PROPIEDAD (CORREGIDO Y CON REFRESH TOKEN)
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
            'estado': estadoPropTrad(custom_data.get("estado")),
            'animales': preferenciasTraductor1(custom_data.get('animales')),        
            'metros': clean_int(custom_data.get('metros')),        
            'balcon': preferenciasTraductor1(custom_data.get('balcon')),        
            'garaje': preferenciasTraductor1(custom_data.get('garaje')),
            'patioInterior': preferenciasTraductor1(custom_data.get('patioInterior')),
            'imagenesUrl':guardadorURL(custom_data.get('imagenesUrl')),
        }
        
        propiedad, created = Propiedad.objects.update_or_create(
            agencia=agencia, 
            ghl_contact_id=ghl_record_id, 
            defaults=prop_data
        )

        zona = custom_data.get("zona")
        if (zona):
            zonaLimpio = zona.replace("_"," ").lower().strip()
            zonaObj = Zona.objects.filter(nombre__iexact=zonaLimpio).first()
            if (zonaObj):
                propiedad.zona = zonaObj
                propiedad.save()

        # Añadir que solo se haga el match si es estado = activo
        if (propiedad.estado == Propiedad.estadoPiso.ACTIVO):
            # 1. BUSCAR NUEVOS MATCHES (Lógica de Negocio)
            clientes_match = Cliente.objects.filter(
                Q(animales = Cliente.Preferencias1.NO) if propiedad.animales == Propiedad.Preferencias1.NO else Q(),
                Q(balcon = Cliente.Preferencias2.IND) if propiedad.balcon == Propiedad.Preferencias1.NO else Q(),
                Q(garaje = Cliente.Preferencias2.IND) if propiedad.garaje == Propiedad.Preferencias1.NO else Q(),
                Q(patioInterior = Cliente.Preferencias2.IND) if propiedad.patioInterior == Propiedad.Preferencias1.NO else Q(),

                agencia=agencia,
                zona_interes=propiedad.zona,
                presupuesto_maximo__gte=propiedad.precio,
                habitaciones_minimas__lte=propiedad.habitaciones,
                metrosMinimo__lte=propiedad.metros
            ).distinct()

            # 2. ACTUALIZACIÓN LOCAL (DJANGO)
            propiedad.interesados.clear() 
            
            # Añadimos los matches vigentes
            for cliente in clientes_match:
                cliente.propiedades_interes.add(propiedad)

            # 3. SINCRONIZACIÓN CON GHL (DELTA SYNC)
            matches_count = clientes_match.count()
            
            # Ejecutamos siempre (incluso si count es 0) para limpiar si la propiedad dejó de ser atractiva
            if matches_count >= 0: 
                # NUEVO: Usamos get_valid_token en lugar de leer GHLToken directamente
                access_token = get_valid_token(location_id)
                
                if access_token:
                    target_ids = [c.ghl_contact_id for c in clientes_match]
                    
                    sync_associations_background(
                        access_token=access_token,
                        location_id=location_id,
                        origin_record_id=propiedad.ghl_contact_id,
                        target_ids_list=target_ids, 
                        association_type="contact"
                    )
                else:
                    logger.warning(f"⚠️ No token valid found for {location_id}")

            return Response({'status': 'success', 'matches_found': matches_count})
        return Response({'status': 'success'})

# -------------------------------------------------------------------------
# VISTA 3: WEBHOOK CLIENTE (CORREGIDO Y CON REFRESH TOKEN)
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
            'nombre': custom_data.get('full_name'),
            'presupuesto_maximo': clean_currency(custom_data.get('presupuesto') or data.get('presupuesto')),
            'habitaciones_minimas': clean_int(custom_data.get('habitaciones') or data.get('habitaciones_min')),
            'animales': preferenciasTraductor1(custom_data.get('animales')),        
            'metrosMinimo': clean_int(custom_data.get('metros')),        
            'balcon': preferenciasTraductor2(custom_data.get('balcon')),        
            'garaje': preferenciasTraductor2(custom_data.get('garaje')),
            'patioInterior': preferenciasTraductor2(custom_data.get('patioInterior')), 
        }

        cliente, created = Cliente.objects.update_or_create(
            agencia=agencia, 
            ghl_contact_id=ghl_contact_id, 
            defaults=cliente_data
        )

        zona_nombre = custom_data.get("zona_interes")
        if (zona_nombre):
            zona_lista = [z.strip() for z in zona_nombre.split(",")]
            zonas = Zona.objects.filter(nombre__in = zona_lista)
            cliente.zona_interes.set(zonas)
            cliente.save()

        # 1. BUSCAR MATCHES
        propiedades_match = Propiedad.objects.filter(
            Q(animales = Propiedad.Preferencias1.SI) if cliente.animales == Cliente.Preferencias1.SI else Q(),
            Q(balcon = Propiedad.Preferencias1.SI) if cliente.balcon == Cliente.Preferencias2.SI else Q(),
            Q(garaje = Propiedad.Preferencias1.SI) if cliente.garaje == Cliente.Preferencias2.SI else Q(),
            Q(patioInterior = Propiedad.Preferencias1.SI) if cliente.garaje == Cliente.Preferencias2.SI else Q(),

            agencia=agencia,
            # zona__iexact=cliente.zona_interes,
            precio__lte=cliente.presupuesto_maximo,
            habitaciones__gte=cliente.habitaciones_minimas,
            metros__gte = cliente.metrosMinimo,
            estado='activo',
            zona__in = cliente.zona_interes.all()
        ).distinct()

        # 2. ACTUALIZACIÓN LOCAL
        cliente.propiedades_interes.clear()
        
        for prop in propiedades_match:
            cliente.propiedades_interes.add(prop)
            
        # 3. SINCRONIZACIÓN CON GHL (DELTA SYNC)
        matches_count = propiedades_match.count()
        if matches_count > 0:
            # NUEVO: Usamos get_valid_token
            access_token = get_valid_token(location_id)

            if access_token:
                # Para cada propiedad que coincida, actualizamos sus inquilinos en GHL
                for prop in propiedades_match:
                    todos_los_interesados = prop.interesados.all()
                    target_ids = [c.ghl_contact_id for c in todos_los_interesados]

                    sync_associations_background(
                        access_token=access_token,
                        location_id=location_id,
                        origin_record_id=prop.ghl_contact_id, 
                        target_ids_list=target_ids,
                        association_type="contact"
                    )
            else:
                logger.warning(f"⚠️ No token valid found for {location_id}")

        return Response({'status': 'success', 'matches_found': matches_count})

