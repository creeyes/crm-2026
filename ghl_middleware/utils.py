import requests
import logging
import time

logger = logging.getLogger(__name__)

# ID FIJO DE ASOCIACIÓN (Propiedad <-> Contacto)
# Lo definimos como constante global para usarlo en todas las funciones.
ASSOCIATION_TYPE_ID = "695961c25fba08a4bb06272e"

# ---------------------------------------------------------
# 1. BUSCAR RELACIONES EXISTENTES (¡Nuevo! Necesario para limpiar)
# ---------------------------------------------------------
def ghl_get_property_relations(access_token, location_id, property_id):
    """
    Obtiene todos los CONTACTOS asociados actualmente a una PROPIEDAD específica.
    Devuelve una lista de diccionarios con la info de la relación para poder borrarla.
    """
    # Pausa de seguridad
    time.sleep(0.5)

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Version": "2021-07-28",
        "Accept": "application/json"
    }

    # Endpoint para listar relaciones filtrando por el ID de la propiedad (secondRecordId)
    url = "https://services.leadconnectorhq.com/associations/relations"
    
    params = {
        "locationId": location_id,
        "associationId": ASSOCIATION_TYPE_ID,
        "secondRecordId": property_id, # Buscamos todo lo conectado a ESTA propiedad
        "limit": 100 # Traemos hasta 100 contactos asociados para asegurar limpieza total
    }

    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            # La API devuelve la lista dentro de la clave 'relations'
            relations = data.get('relations', [])
            logger.info(f"🔍 Consulta GHL: Encontrados {len(relations)} contactos asociados a la propiedad {property_id}")
            return relations
        else:
            logger.error(f"❌ Error buscando relaciones ({response.status_code}): {response.text}")
            return []
            
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Excepción buscando relaciones: {str(e)}")
        return []

# ---------------------------------------------------------
# 2. BORRAR RELACIÓN (Delete)
# ---------------------------------------------------------
def ghl_delete_association(access_token, location_id, record_id_1, record_id_2):
    """
    ELIMINA la relación existente entre Propiedad y Contacto.
    
    :param record_id_1: PROPIEDAD
    :param record_id_2: CONTACTO
    """
    
    # Pausa breve
    time.sleep(0.5)
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Version": "2021-07-28",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    url = "https://services.leadconnectorhq.com/associations/relations"

    payload = {
        "locationId": location_id,
        "associationId": ASSOCIATION_TYPE_ID,
        # ORDEN CRÍTICO (Igual que al crear):
        "firstRecordId": record_id_2,   # Contacto
        "secondRecordId": record_id_1   # Propiedad
    }

    try:
        # Usamos DELETE con body (json)
        response = requests.delete(url, json=payload, headers=headers, timeout=10)
        
        # 200 = OK, 204 = No Content (Éxito)
        if response.status_code in [200, 204]:
            logger.info(f"🗑️ GHL Eliminación Exitosa: Contacto {record_id_2} desligado de Propiedad {record_id_1}")
            return True
        elif response.status_code == 404:
             # Si no existe, cuenta como borrado
            logger.warning(f"⚠️ Relación no encontrada para borrar (404), continuamos.")
            return True
        else:
            logger.error(f"❌ Error GHL ({response.status_code}) borrando RELACIÓN: {response.text}")
            return False

    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Excepción de conexión GHL (DELETE): {str(e)}")
        return False

# ---------------------------------------------------------
# 3. CREAR RELACIÓN (Create / Match)
# ---------------------------------------------------------
def ghl_associate_records(access_token, location_id, record_id_1, record_id_2, association_type="contact"):
    """
    Crea la relación Many-to-Many.
    
    :param record_id_1: PROPIEDAD
    :param record_id_2: CONTACTO
    """
    
    # Pausa de seguridad
    time.sleep(1) 
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Version": "2021-07-28",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    url = "https://services.leadconnectorhq.com/associations/relations"
    
    payload = {
        "locationId": location_id,
        "associationId": ASSOCIATION_TYPE_ID,
        # ORDEN CRÍTICO:
        "firstRecordId": record_id_2,   # Contacto
        "secondRecordId": record_id_1   # Propiedad
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        
        if response.status_code in [200, 201]:
            logger.info(f"✅ GHL Match Exitoso: Contacto {record_id_2} <-> Propiedad {record_id_1}")
            return True
        else:
            logger.error(f"❌ Error GHL ({response.status_code}) creando RELACIÓN: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Excepción de conexión GHL (CREATE): {str(e)}")
        return False
