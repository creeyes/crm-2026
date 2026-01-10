import requests
import logging
import time

logger = logging.getLogger(__name__)

# ID FIJO DE ASOCIACIÓN (Propiedad <-> Contacto)
ASSOCIATION_TYPE_ID = "695961c25fba08a4bb06272e"

# ---------------------------------------------------------
# 1. BUSCAR RELACIONES (GET)
# ---------------------------------------------------------
def ghl_get_property_relations(access_token, location_id, property_id):
    """
    Obtiene todos los CONTACTOS asociados actualmente a una PROPIEDAD específica.
    """
    time.sleep(0.5)

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Version": "2021-07-28",
        "Accept": "application/json"
    }

    url = "https://services.leadconnectorhq.com/associations/relations"
    
    params = {
        "locationId": location_id,
        "associationId": ASSOCIATION_TYPE_ID,
        "secondRecordId": property_id, 
        "limit": 100 
    }

    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            relations = data.get('relations', [])
            if not relations and 'data' in data:
                 relations = data.get('data', [])
                 
            logger.info(f"🔍 Consulta GHL: Encontrados {len(relations)} contactos en Propiedad {property_id}")
            return relations
        else:
            logger.error(f"❌ Error buscando relaciones ({response.status_code}): {response.text}")
            return []
            
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Excepción buscando relaciones: {str(e)}")
        return []

# ---------------------------------------------------------
# 2. BORRAR RELACIÓN (DELETE)
# ---------------------------------------------------------
def ghl_delete_association(access_token, location_id, record_id_1, record_id_2):
    """
    ELIMINA la relación entre Propiedad (id_1) y Contacto (id_2).
    """
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
        "firstRecordId": record_id_2,   # Contacto
        "secondRecordId": record_id_1   # Propiedad
    }

    try:
        response = requests.delete(url, json=payload, headers=headers, timeout=10)
        
        if response.status_code in [200, 204]:
            logger.info(f"🗑️ Eliminado: Contacto {record_id_2} fuera de Propiedad {record_id_1}")
            return True
        elif response.status_code == 404:
            logger.warning(f"⚠️ Relación no encontrada (ya borrada), continuamos.")
            return True
        else:
            logger.error(f"❌ Error borrando ({response.status_code}): {response.text}")
            return False

    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Excepción borrando: {str(e)}")
        return False

# ---------------------------------------------------------
# 3. CREAR RELACIÓN (POST)
# ---------------------------------------------------------
def ghl_associate_records(access_token, location_id, record_id_1, record_id_2, association_type="contact"):
    """
    CREA la relación entre Propiedad (id_1) y Contacto (id_2).
    """
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
        "firstRecordId": record_id_2,   # Contacto
        "secondRecordId": record_id_1   # Propiedad
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        
        if response.status_code in [200, 201]:
            logger.info(f"✅ Match Exitoso: Contacto {record_id_2} <-> Propiedad {record_id_1}")
            return True
        else:
            logger.error(f"❌ Error Match ({response.status_code}): {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Excepción Match: {str(e)}")
        return False
