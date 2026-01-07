# utils.py
import requests
import logging
import time

logger = logging.getLogger(__name__)

def ghl_associate_records(access_token, location_id, propiedad_id, contacto_id):
    """
    Crea la relación Many-to-Many entre Propiedad y Contacto usando el endpoint /relations.
    """
    
    # 1. PAUSA DE SEGURIDAD (Necesaria para dar tiempo a GHL a indexar el registro creado)
    time.sleep(2) 
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Version": "2021-07-28",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    # URL CORRECTA (La que funcionó en Postman)
    url = "https://services.leadconnectorhq.com/associations/relations"
    
    # ID de la Asociación (Propiedad <-> Contacto) extraído de tus logs
    # Esto define QUE tipo de unión estamos creando.
    ASSOCIATION_ID = "695961c25fba08a4bb06272e"

    payload = {
        "locationId": location_id,
        "associationId": ASSOCIATION_ID,
        "firstRecordId": contacto_id,   # IMPORTANTE: Según tus logs, el 1º es el Contacto
        "secondRecordId": propiedad_id  # IMPORTANTE: Según tus logs, el 2º es la Propiedad
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        
        if response.status_code in [200, 201]:
            logger.info(f"✅ GHL Match Exitoso: Contacto {contacto_id} <-> Propiedad {propiedad_id}")
            return True
        else:
            logger.error(f"❌ Error GHL ({response.status_code}) creando RELACIÓN: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Excepción de conexión GHL: {str(e)}")
        return False
