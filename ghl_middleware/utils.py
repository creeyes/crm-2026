# utils.py
import requests
import logging

# Configuración de logs
logger = logging.getLogger(__name__)

def ghl_associate_records(access_token, record_id_1, record_id_2, association_type="contact"):
    """
    Realiza la llamada API para conectar dos entidades en GHL (Many-to-Many).
    Esta función es utilizada por tasks.py para ejecutarse en segundo plano.
    
    :param record_id_1: ID del Custom Object Origen (Ej. La Propiedad)
    :param record_id_2: ID del Contacto Destino o del otro objeto (Ej. El Cliente)
    :param association_type: 'contact' si vinculamos a un contacto, o el ID del schema si es otro objeto.
    """
    
    # Endpoint oficial de LeadConnector v2 para asociaciones
    # Siempre atacamos al Custom Object (record_id_1) para asociarle algo (record_id_2)
    url = f"https://services.leadconnectorhq.com/custom-objects/records/{record_id_1}/associations"
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Version": "2021-07-28",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    payload = {
        "recordId": record_id_2,
        "associationType": association_type
    }

    try:
        # IMPORTANTE: Added timeout=10 para evitar que el hilo se quede colgado eternamente
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        
        # 201 Created y 200 OK son respuestas exitosas en GHL
        if response.status_code in [200, 201]:
            logger.info(f"✅ GHL Match Exitoso: Propiedad {record_id_1} <-> Cliente {record_id_2}")
            return True
        else:
            # Logueamos el error pero no rompemos la ejecución, retornamos False
            logger.error(f"❌ Error GHL ({response.status_code}): {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        logger.error(f"⏳ Timeout: GHL tardó demasiado en responder para {record_id_1} -> {record_id_2}")
        return False
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Excepción de conexión GHL: {str(e)}")
        return False
