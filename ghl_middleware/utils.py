# utils.py
import requests
import logging
import time

logger = logging.getLogger(__name__)

def ghl_associate_records(access_token, location_id, record_id_1, record_id_2, association_type="contact"):
    """
    Crea la relación Many-to-Many usando el endpoint /relations.
    Mantiene compatibilidad con la llamada antigua de tasks.py.
    
    :param record_id_1: PROPIEDAD (Según tu código original)
    :param record_id_2: CONTACTO (Según tu código original)
    :param association_type: Se recibe por compatibilidad, pero usamos el ID fijo interno.
    """
    
    # 1. PAUSA DE SEGURIDAD
    time.sleep(2) 
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Version": "2021-07-28",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    # URL CORRECTA (Validada en Postman)
    url = "https://services.leadconnectorhq.com/associations/relations"
    
    # ID FIJO DE ASOCIACIÓN (Propiedad <-> Contacto)
    # Lo obtuvimos de tu JSON anterior: "695961c25fba08a4bb06272e"
    ASSOCIATION_ID = "695961c25fba08a4bb06272e"

    payload = {
        "locationId": location_id,
        "associationId": ASSOCIATION_ID,
        # OJO AL ORDEN (Según tu definición de GHL):
        # firstRecordId debe ser CONTACTO -> record_id_2
        # secondRecordId debe ser PROPIEDAD -> record_id_1
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
        logger.error(f"❌ Excepción de conexión GHL: {str(e)}")
        return False
