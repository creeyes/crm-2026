# ghl_service.py
import requests
import logging

logger = logging.getLogger(__name__)

def ghl_associate_records(access_token, custom_object_id, contact_id):
    """
    Asocia un Custom Object (Propiedad) con un Contacto (Cliente).
    """
    # Endpoint para asociar algo a un Custom Object Record
    url = f"https://services.leadconnectorhq.com/custom-objects/records/{custom_object_id}/associations"
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Version": "2021-07-28", # API v2
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    payload = {
        "recordId": contact_id,     # El ID del Contacto
        "associationType": "contact" # Especificamos que lo unimos a un contacto
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code in [200, 201]:
            logger.info(f"GHL Asociación Éxito: Propiedad {custom_object_id} <-> Cliente {contact_id}")
            return True
        else:
            logger.error(f"GHL Asociación Error {response.status_code}: {response.text}")
            return False
    except Exception as e:
        logger.error(f"GHL Asociación Excepción: {str(e)}")
        return False
