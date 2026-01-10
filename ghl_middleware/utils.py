import requests
import logging
import time

logger = logging.getLogger(__name__)

# ID FIJO DE ASOCIACIÓN
ASSOCIATION_TYPE_ID = "695961c25fba08a4bb06272e"

# ---------------------------------------------------------
# 1. OBTENER MAPA (CON LOGS DE DEBUG)
# ---------------------------------------------------------
def ghl_get_current_associations(access_token, location_id, property_id):
    time.sleep(0.5)
    headers = { "Authorization": f"Bearer {access_token}", "Version": "2021-07-28", "Accept": "application/json" }
    
    # URL GANADORA
    url = f"https://services.leadconnectorhq.com/associations/relations/{property_id}"
    params = { "locationId": location_id }
    found_relations_map = {}

    try:
        logger.info(f"🕵️ [GET] Consultando relaciones en: {url}")
        response = requests.get(url, headers=headers, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            relations_list = data.get('relations', [])
            
            # LOG PARA VER QUÉ NOS DEVUELVE EXACTAMENTE GHL
            logger.info(f"📦 [GET] JSON RAW recibido ({len(relations_list)} items): {str(relations_list)[:200]}...") 

            for rel in relations_list:
                r1 = rel.get('firstRecordId')
                r2 = rel.get('secondRecordId')
                
                # Identificamos al contacto
                if r1 == property_id:
                    contact_id = r2
                else:
                    contact_id = r1
                
                if contact_id:
                    found_relations_map[contact_id] = rel
            
            return found_relations_map
        elif response.status_code == 404:
             logger.warning(f"⚠️ [GET] 404 - No se encontraron relaciones (Propiedad limpia).")
             return {}
        else:
            logger.error(f"❌ [GET] Error GHL ({response.status_code}): {response.text}")
            return {}
    except Exception as e:
        logger.error(f"❌ [GET] Excepción crítica: {str(e)}")
        return {}

# ---------------------------------------------------------
# 2. BORRAR RELACIÓN (MODO FORENSE)
# ---------------------------------------------------------
def ghl_delete_association(access_token, location_id, first_id, second_id):
    time.sleep(0.5) # Pausa un poco mayor para ver logs claros
    
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
        "firstRecordId": first_id,   
        "secondRecordId": second_id  
    }

    # LOG CRÍTICO: ¿QUÉ ESTAMOS ENVIANDO?
    logger.warning(f"💣 [DELETE] Enviando Payload: {payload}")

    try:
        response = requests.delete(url, json=payload, headers=headers, timeout=10)
        
        if response.status_code in [200, 204]:
            logger.info(f"✅ [DELETE] Éxito (Status {response.status_code})")
            return True
        else:
            # LOG CRÍTICO: ¿POR QUÉ FALLÓ?
            logger.error(f"❌ [DELETE] FALLÓ CON STATUS {response.status_code}")
            logger.error(f"❌ [DELETE] RESPUESTA GHL: {response.text}") # <--- AQUÍ SALDRÁ LA VERDAD
            return False

    except Exception as e:
        logger.error(f"❌ [DELETE] Excepción Python: {str(e)}")
        return False

# ---------------------------------------------------------
# 3. CREAR RELACIÓN (POST)
# ---------------------------------------------------------
def ghl_associate_records(access_token, location_id, property_id, contact_id):
    # Sin cambios mayores, solo silenciamos un poco para no ensuciar el log del delete
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
        if response.status_code in [200, 201]:
            return True
        logger.error(f"⚠️ [POST] Error Match: {response.text}")
        return False
    except:
        return False
