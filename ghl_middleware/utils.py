# utils.py
import requests
import logging
import time

logger = logging.getLogger(__name__)

def ghl_associate_records(access_token, location_id, record_id_1, record_id_2, association_type="contact"):
    """
    Asocia registros usando el endpoint ESPECÍFICO DEL SCHEMA (Object Scoped) validado en Postman.
    """
    
    # 1. PAUSA DE SEGURIDAD (Race Condition)
    time.sleep(2) 
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Version": "2021-07-28",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Location-Id": location_id 
    }

    # ------------------------------------------------------------------
    # CAMBIO CRÍTICO: URL SCOPEADA (Schema ID: 6956b58d47f4c57f79cbe223)
    # ------------------------------------------------------------------
    # Usamos tu URL base validada y le añadimos /associations al final
    schema_id = "6956b58d47f4c57f79cbe223"
    url = f"https://services.leadconnectorhq.com/objects/{schema_id}/records/{record_id_1}/associations"
    
    payload = {
        "recordId": record_id_2,
        "associationType": association_type
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        
        if response.status_code in [200, 201]:
            logger.info(f"✅ GHL Match Exitoso: Propiedad {record_id_1} <-> Cliente {record_id_2}")
            return True
        else:
            # Agregamos logging del URL para debug si vuelve a fallar
            logger.error(f"❌ Error GHL ({response.status_code}) en URL: {url}")
            logger.error(f"Respuesta: {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        logger.error(f"⏳ Timeout: GHL tardó demasiado en responder.")
        return False
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Excepción de conexión GHL: {str(e)}")
        return False
