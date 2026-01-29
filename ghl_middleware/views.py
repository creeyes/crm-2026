import logging
import requests
from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Q

from .models import Agencia, Propiedad, Cliente, GHLToken, Zona
from .tasks import sync_associations_background
# IMPORTANTE: AÑADIDA LA NUEVA FUNCIÓN A LOS IMPORTS
from .utils import get_valid_token, get_association_type_id 

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
    value = str(value or "").replace("_"," ").lower()
    return mapa.get(value, Propiedad.estadoPiso.NoOficial)

def guardadorURL(value):
    lista = []
    if value and value != "null":
        if isinstance(value, list):
            lista = [data.get('url') for data in value if isinstance(data, dict) and data.get('url')]
    return lista

# -------------------------------------------------------------------------
# VISTA 1: OAUTH CALLBACK (MODIFICADA PARA AUTO-DETECTAR ID)
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
                access_token = tokens['access_token']

                # 1. Guardar/Actualizar Token
                GHLToken.objects.update_or_create(
                    location_id=location_id,
                    defaults={
                        'access_token': access_token,
                        'refresh_token': tokens['refresh_token'],
                        'token_type': tokens['token_type'],
                        'expires_in': tokens['expires_in'],
                        'scope': tokens['scope']
                    }
                )
                
                # 2. Crear Agencia si no existe
                agencia, created = Agencia.objects.get_or_create(location_id=location_id, defaults={'active': True})
                
                # 3. --- AUTO-DETECCIÓN INTELIGENTE DEL ID DE ASOCIACIÓN ---
                # Consultamos a GHL para obtener el ID que une Contactos <-> Propiedades
                # Nota: 'propiedad' es la KEY de tu Custom Object. Ajustalo si es diferente.
                logger.info(f"🕵️ Buscando ID de asociación para {location_id}...")
                found_id = get_association_type_id(access_token, location_id, object_key="propiedad")
                
                if found_id:
                    agencia.association_type_id = found_id
                    agencia.save()
                    logger.info(f"✅ ID de asociación detectado y guardado: {found_id}")
                else:
                    logger.warning(f"⚠️ No se pudo detectar el ID automáticamente. Deberás ponerlo manual.")
                # ----------------------------------------------------------

                return Response({"message": "App instalada y configurada.", "location_id": location_id}, status=200)
            
            logger.error(f"Error OAuth GHL: {tokens}")
            return Response(tokens, status=400)
        except Exception as e:
            logger.error(f"Excepción OAuth: {str(e)}")
            return Response({"error": str(e)}, status=500)

# -------------------------------------------------------------------------
# VISTA 2: WEBHOOK PROPIEDAD
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
            # 1. BUSCAR NUEVOS MATCHES
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

            # 2. ACTUALIZACIÓN LOCAL
            propiedad.interesados.clear() 
            for cliente in clientes_match:
                cliente.propiedades_interes.add(propiedad)

            # 3. SINCRONIZACIÓN CON GHL
            matches_count = clientes_match.count()
            
            if matches_count >= 0: 
                # VALIDAR ID DE ASOCIACIÓN
                if not agencia.association_type_id:
                    logger.warning(f"⚠️ Agencia {location_id} no tiene 'association_type_id'. Cruzado saltado.")
                    return Response({'status': 'warning', 'msg': 'Falta Association ID', 'matches_found': matches_count})

                access_token = get_valid_token(location_id)
                
                if access_token:
                    target_ids = [c.ghl_contact_id for c in clientes_match]
                    
                    sync_associations_background(
                        access_token=access_token,
                        location_id=location_id,
                        origin_record_id=propiedad.ghl_contact_id,
                        target_ids_list=target_ids, 
                        association_id_val=agencia.association_type_id 
                    )
                else:
                    logger.warning(f"⚠️ No token valid found for {location_id}")

            return Response({'status': 'success', 'matches_found': matches_count})
        return Response({'status': 'success'})

# -------------------------------------------------------------------------
# VISTA 3: WEBHOOK CLIENTE
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
            zona_lista = [z.strip() for z in str(zona_nombre).split(",")]
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
            
        # 3. SINCRONIZACIÓN CON GHL
        matches_count = propiedades_match.count()
        if matches_count > 0:
            
            # VALIDAR ID DE ASOCIACIÓN
            if not agencia.association_type_id:
                logger.warning(f"⚠️ Agencia {location_id} no tiene 'association_type_id'. Cruzado saltado.")
                return Response({'status': 'warning', 'msg': 'Falta Association ID', 'matches_found': matches_count})

            access_token = get_valid_token(location_id)

            if access_token:
                for prop in propiedades_match:
                    todos_los_interesados = prop.interesados.all()
                    target_ids = [c.ghl_contact_id for c in todos_los_interesados]

                    sync_associations_background(
                        access_token=access_token,
                        location_id=location_id,
                        origin_record_id=prop.ghl_contact_id, 
                        target_ids_list=target_ids,
                        association_id_val=agencia.association_type_id
                    )
            else:
                logger.warning(f"⚠️ No token valid found for {location_id}")

        return Response({'status': 'success', 'matches_found': matches_count})

class DebugGHLView(APIView):
    """
    HERRAMIENTA DE DIAGNÓSTICO: Muestra qué asociaciones ve GHL realmente.
    """
    permission_classes = [] # Abierto para que puedas entrar fácil

    def get(self, request):
        # Pon aquí el ID de la cuenta que falla
        target_location = "A6JzWxltUNrmkOmGlEhH" 
        
        reporte = {"estado": "Iniciando", "location_id": target_location}
        
        try:
            token_obj = GHLToken.objects.filter(location_id=target_location).first()
            if not token_obj:
                return Response({"error": "No hay token para esta agencia. Reinstala la App primero."}, status=400)

            # 1. Consultar a GHL
            url = "https://services.leadconnectorhq.com/associations/types"
            headers = {
                "Authorization": f"Bearer {token_obj.access_token}", 
                "Version": "2021-07-28",
                "Accept": "application/json"
            }
            
            resp = requests.get(url, headers=headers, params={"locationId": target_location})
            
            if resp.status_code == 200:
                data = resp.json()
                types = data.get('associationTypes', [])
                
                # 2. Filtrar lo interesante
                lista_limpia = []
                for t in types:
                    info = f"ID: {t['id']} | DE: {t['sourceKey']} <--> A: {t['targetKey']}"
                    lista_limpia.append(info)
                    
                reporte["asociaciones_encontradas_en_ghl"] = lista_limpia
                reporte["mensaje"] = "Mira la lista de arriba. ¿Ves 'propiedad' o 'propiedades'? Copia el ID."
                
                # INTENTO DE REPARACIÓN AUTOMÁTICA EN VIVO
                # Busca cualquier cosa que contenga 'prop'
                found_id = None
                for t in types:
                    keys = [t['sourceKey'], t['targetKey']]
                    if 'contact' in keys and any('prop' in k for k in keys):
                        found_id = t['id']
                        break
                
                if found_id:
                    agencia = Agencia.objects.get(location_id=target_location)
                    agencia.association_type_id = found_id
                    agencia.save()
                    reporte["reparacion"] = f"✅ ¡ARREGLADO! Se ha guardado el ID {found_id} automáticamente."
                else:
                    reporte["reparacion"] = "❌ No se encontró nada parecido a 'propiedad' en la lista."

            else:
                reporte["error_ghl"] = resp.text

        except Exception as e:
            reporte["error_interno"] = str(e)

        return Response(reporte)
