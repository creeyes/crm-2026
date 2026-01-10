import requests
import logging
import time

logger = logging.getLogger(__name__)

# ID FIJO DE ASOCIACIÓN
ASSOCIATION_TYPE_ID = "695961c25fba08a4bb06272e"

# ---------------------------------------------------------
# 1. OBTENER MAPA DE RELACIONES (MÉTODO TUYO - DIRECT ID)
# ---------------------------------------------------------
def ghl_get_current_associations(access_token, location_id, property_id):
    """
    Busca relaciones usando el endpoint directo por ID de registro.
    URL descubierta: /associations/relations/{RecordId}?locationId=...
    """
    time.sleep(0.5)

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Version": "2021-07-28",
        "Accept": "application/json"
    }
    
    # USAMOS TU URL GANADORA:
    url = f"https://services.leadconnectorhq.com/associations/relations/{property_id}"
    
    params = {
        "locationId": location_id
    }

    found_relations_map = {}

    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            # Tu JSON muestra que la lista está bajo la clave "relations"
            relations_list = data.get('relations', [])
            
            for rel in relations_list:
                # Extraemos los IDs tal cual vienen en tu JSON
                r1 = rel.get('firstRecordId')
                r2 = rel.get('secondRecordId')
                
                # Lógica para saber cuál es el contacto:
                # Si la propiedad es el r1, el contacto es r2. Y viceversa.
                if r1 == property_id:
                    contact_id = r2
                else:
                    contact_id = r1
                
                if contact_id:
                    # Guardamos todo el objeto relación para usarlo al borrar
                    found_relations_map[contact_id] = rel
            
            logger.info(f"🔍 Mapa Actual: Propiedad {property_id} tiene {len(found_relations_map)} conexiones.")
            return found_relations_map
            
        elif response.status_code == 404:
             logger.info(f"🔍 Propiedad {property_id} limpia (GHL devolvió 404 en búsqueda).")
             return {}
        else:
            logger.error(f"⚠️ Error API GHL ({response.status_code}): {response.text}")
            return {}

    except Exception as e:
        logger.error(f"❌ Excepción buscando relaciones: {str(e)}")
        return {}

# ---------------------------------------------------------
# 2. BORRAR RELACIÓN (DELETE)
# ---------------------------------------------------------
def ghl_delete_association(access_token, location_id, id_1, id_2):
    """
    Borra la asociación usando los IDs.
    """
    time.sleep(0.2)
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Version": "2021-07-28",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    url = "https://services.leadconnectorhq.com/associations/relations"

    # INTENTO 1: Usamos el orden que nos funcionó en Postman/Creación
    payload = {
        "locationId": location_id,
        "associationId": ASSOCIATION_TYPE_ID,
        "firstRecordId": id_1, 
        "secondRecordId": id_2 
    }

    try:
        response = requests.delete(url, json=payload, headers=headers, timeout=10)
        
        if response.status_code in [200, 204]:
            return True
            
        # INTENTO 2: Inverso (Por seguridad)
        payload["firstRecordId"] = id_2
        payload["secondRecordId"] = id_1
        response_inv = requests.delete(url, json=payload, headers=headers, timeout=10)
        
        return response_inv.status_code in [200, 204]

    except Exception as e:
        logger.error(f"❌ Excepción borrando: {str(e)}")
        return False

# ---------------------------------------------------------
# 3. CREAR RELACIÓN (POST)
# ---------------------------------------------------------
def ghl_associate_records(access_token, location_id, property_id, contact_id):
    time.sleep(0.2)
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Version": "2021-07-28",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    url = "https://services.leadconnectorhq.com/associations/relations"
    
    # Estandarizamos: Cliente (Primero) <-> Propiedad (Segundo)
    payload = {
        "locationId": location_id,
        "associationId": ASSOCIATION_TYPE_ID,
        "firstRecordId": contact_id,  
        "secondRecordId": property_id 
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        return response.status_code in [200, 201]
    except Exception as e:
        logger.error(f"❌ Excepción creando: {str(e)}")
        return False
