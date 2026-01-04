# utils.py
import requests
import logging
import time # Importamos time para la pausa de seguridad

logger = logging.getLogger(__name__)

def ghl_associate_records(access_token, location_id, record_id_1, record_id_2, association_type="contact"):
    """
    Intenta asociar registros con diagnósticos avanzados y pausa de seguridad.
    """
    
    # 1. PAUSA DE SEGURIDAD (Race Condition)
    # A veces GHL tarda 1-2 segundos en indexar el nuevo objeto. Esperamos un poco.
    time.sleep(2) 
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Version": "2021-07-28",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Location-Id": location_id 
    }

    # ------------------------------------------------------------------
    # PASO 1: VERIFICAR SI EL OBJETO EXISTE (Diagnóstico)
    # ------------------------------------------------------------------
    # Intentamos LEER la propiedad antes de asociarla.
    check_url = f"https://services.leadconnectorhq.com/custom-objects/records/{record_id_1}"
    
    try:
        check_response = requests.get(check_url, headers=headers, timeout=5)
        if check_response.status_code == 200:
            logger.info(f"✅ GHL Diagnóstico: La propiedad {record_id_1} EXISTE y es accesible.")
        else:
            # Si esto falla, el problema es 100% PERMISOS o TOKEN
            logger.error(f"❌ GHL Diagnóstico: No puedo LEER la propiedad. Código: {check_response.status_code}. Respuesta: {check_response.text}")
            return False
    except Exception as e:
        logger.error(f"❌ Error en Diagnóstico GET: {e}")

    # ------------------------------------------------------------------
    # PASO 2: INTENTAR LA ASOCIACIÓN
    # ------------------------------------------------------------------
    url = f"https://services.leadconnectorhq.com/custom-objects/records/{record_id_1}/associations"
    
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
            logger.error(f"❌ Error GHL en ASOCIACIÓN ({response.status_code}): {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        logger.error(f"⏳ Timeout: GHL tardó demasiado en responder.")
        return False
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Excepción de conexión GHL: {str(e)}")
        return False
