import requests
import logging
import time

logger = logging.getLogger(__name__)

# ID FIJO DE ASOCIACIÓN (Propiedad <-> Contacto)
# Lo definimos como constante global para usarlo tanto en crear como en borrar.
ASSOCIATION_TYPE_ID = "695961c25fba08a4bb06272e"

def ghl_associate_records(access_token, location_id, record_id_1, record_id_2, association_type="contact"):
    """
    Crea la relación Many-to-Many usando el endpoint /relations (POST).
    
    :param record_id_1: PROPIEDAD (Custom Object)
    :param record_id_2: CONTACTO
    """
    
    # 1. PAUSA DE SEGURIDAD (Rate Limiting)
    time.sleep(2) 
    
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
        # firstRecordId -> CONTACTO (record_id_2)
        # secondRecordId -> PROPIEDAD (record_id_1)
        "firstRecordId": record_id_2,   
        "secondRecordId": record_id_1   
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


def ghl_delete_association(access_token, location_id, record_id_1, record_id_2):
    """
    ELIMINA la relación existente usando el endpoint /relations (DELETE).
    Útil para limpiar relaciones previas antes de asignar una nueva.
    
    :param record_id_1: PROPIEDAD (Custom Object)
    :param record_id_2: CONTACTO
    """
    
    # Pausa breve
    time.sleep(1)
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Version": "2021-07-28",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    # Nota: El endpoint es el mismo, pero el método es DELETE
    url = "https://services.leadconnectorhq.com/associations/relations"

    payload = {
        "locationId": location_id,
        "associationId": ASSOCIATION_TYPE_ID,
        # MANTENEMOS EL MISMO ORDEN EXACTO QUE AL CREAR
        "firstRecordId": record_id_2,   # Contacto
        "secondRecordId": record_id_1   # Propiedad
    }

    try:
        # Usamos request.delete con 'json' (body), permitido en GHL API V2
        response = requests.delete(url, json=payload, headers=headers, timeout=10)
        
        if response.status_code in [200, 204]:
            logger.info(f"🗑️ GHL Eliminación Exitosa: Contacto {record_id_2} roto de Propiedad {record_id_1}")
            return True
        else:
            # Si devuelve 404 es posible que la relación no existiera, lo cual técnicamente es "éxito"
            if response.status_code == 404:
                logger.warning(f"⚠️ Relación no encontrada para borrar (404), continuamos.")
                return True
            
            logger.error(f"❌ Error GHL ({response.status_code}) borrando RELACIÓN: {response.text}")
            return False

    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Excepción de conexión GHL (DELETE): {str(e)}")
        return False
