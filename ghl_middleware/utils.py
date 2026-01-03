# utils.py
import requests
import logging

logger = logging.getLogger(__name__)

def ghl_associate_records(access_token, record_id_1, record_id_2, association_type="contact"):
    """
    Realiza la llamada API para conectar dos entidades en GHL (Many-to-Many).
    
    :param record_id_1: ID del Custom Object (Ej. La Propiedad)
    :param record_id_2: ID del Contacto o del otro objeto (Ej. El Cliente)
    :param association_type: 'contact' si vinculamos a un contacto, o el ID del schema si es otro objeto.
    """
    # Endpoint oficial de LeadConnector v2 para asociaciones
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
        response = requests.post(url, json=payload, headers=headers)
        
        # 201 Created o 200 OK son respuestas exitosas
        if response.status_code in [200, 201]:
            logger.info(f"✅ GHL Match Exitoso: {record_id_1} <-> {record_id_2}")
            return True
        else:
            logger.error(f"❌ Error GHL ({response.status_code}): {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Excepción de conexión GHL: {str(e)}")
        return False
