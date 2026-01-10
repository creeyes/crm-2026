import requests
import logging
import time

logger = logging.getLogger(__name__)

# ID FIJO DE ASOCIACIÓN
ASSOCIATION_TYPE_ID = "695961c25fba08a4bb06272e"

# ---------------------------------------------------------
# 1. OBTENER MAPA (Igual que antes, funciona perfecto)
# ---------------------------------------------------------
def ghl_get_current_associations(access_token, location_id, property_id):
    time.sleep(0.5)
    headers = { "Authorization": f"Bearer {access_token}", "Version": "2021-07-28", "Accept": "application/json" }
    
    url = f"https://services.leadconnectorhq.com/associations/relations/{property_id}"
    params = { "locationId": location_id }
    found_relations_map = {}

    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            relations_list = data.get('relations', [])
            
            for rel in relations_list:
                r1 = rel.get('firstRecordId')
                r2 = rel.get('secondRecordId')
                
                # Identificamos al contacto
                if r1 == property_id:
                    contact_id = r2
                else:
                    contact_id = r1
                
                if contact_id:
                    # GUARDAMOS EL OBJETO ENTERO (Incluye el 'id' único de la relación)
                    found_relations_map[contact_id] = rel
            
            return found_relations_map
        elif response.status_code == 404:
             return {}
        else:
            logger.error(f"⚠️ [GET] Error GHL ({response.status_code}): {response.text}")
            return {}
    except Exception as e:
        logger.error(f"❌ [GET] Excepción: {str(e)}")
        return {}

# ---------------------------------------------------------
# 2. BORRAR RELACIÓN (POR ID ÚNICO - EL FRANCOTIRADOR)
# ---------------------------------------------------------
def ghl_delete_association(access_token, location_id, relation_id):
    """
    Borra usando el ID ÚNICO de la relación (ej: 6962a035...).
    Esto evita cualquier error de dirección o pares.
    """
    time.sleep(0.2)
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Version": "2021-07-28",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    # ATACAMOS DIRECTAMENTE AL RECURSO POR SU ID
    url = f"https://services.leadconnectorhq.com/associations/relations/{relation_id}"

    # Para DELETE por ID, a veces solo se requiere el locationId en query params o body
    # Probamos mandando solo locationId, que es lo estándar para delete by ID
    params = { "locationId": location_id }

    logger.warning(f"🎯 [DELETE] Ejecutando Francotirador en ID: {relation_id}")

    try:
        response = requests.delete(url, headers=headers, params=params, timeout=10)
        
        if response.status_code in [200, 204]:
            logger.info(f"✅ [DELETE] Eliminado con éxito.")
            return True
        else:
            logger.error(f"❌ [DELETE] Falló ({response.status_code}): {response.text}")
            return False

    except Exception as e:
        logger.error(f"❌ [DELETE] Excepción: {str(e)}")
        return False

# ---------------------------------------------------------
# 3. CREAR RELACIÓN (POST)
# ---------------------------------------------------------
def ghl_associate_records(access_token, location_id, property_id, contact_id):
    time.sleep(0.2)
    headers = { "Authorization": f"Bearer {access_token}", "Version": "2021-07-28", "Content-Type": "application/json", "Accept": "application/json" }
    url = "https://services.leadconnectorhq.com/associations/relations"
    
    payload = {
        "locationId": location_id,
        "associationId": ASSOCIATION_TYPE_ID,
        "firstRecordId": contact_id,  
        "secondRecordId": property_id 
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        return response.status_code in [200, 201]
    except:
        return False
