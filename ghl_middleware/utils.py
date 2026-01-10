import requests
import logging
import time

logger = logging.getLogger(__name__)

# ID FIJO DE ASOCIACIÓN (Propiedad <-> Contacto)
# Asegúrate de que este ID sea correcto en tu subcuenta de GHL
ASSOCIATION_TYPE_ID = "695961c25fba08a4bb06272e"

# ---------------------------------------------------------
# 1. OBTENER MAPA DE RELACIONES ACTUALES (BARRIDO DOBLE)
# ---------------------------------------------------------
def ghl_get_current_associations(access_token, location_id, property_id):
    """
    Busca todas las conexiones existentes para una propiedad.
    Devuelve un Diccionario: { contact_id: relation_object }
    Esto nos permite saber exactamente quién está conectado y cómo.
    """
    time.sleep(0.5)

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Version": "2021-07-28",
        "Accept": "application/json"
    }
    url = "https://services.leadconnectorhq.com/associations/relations"
    
    found_relations_map = {}

    # Definimos las dos direcciones de búsqueda posibles
    search_params = [
        {"secondRecordId": property_id}, # Caso A: Propiedad es el Segundo (Estándar)
        {"firstRecordId": property_id}   # Caso B: Propiedad es el Primero (Raro pero posible)
    ]

    for params in search_params:
        params["locationId"] = location_id
        params["associationId"] = ASSOCIATION_TYPE_ID
        params["limit"] = 100

        try:
            response = requests.get(url, headers=headers, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                relations = data.get('relations', []) or data.get('data', [])
                
                for rel in relations:
                    # Lógica para identificar quién es el CONTACTO en esta relación
                    r1 = rel.get('firstRecordId')
                    r2 = rel.get('secondRecordId')
                    
                    # El contacto es el ID que NO es la propiedad
                    contact_id = r1 if r2 == property_id else r2
                    
                    if contact_id:
                        found_relations_map[contact_id] = rel

            elif response.status_code == 400:
                # 400 en GHL búsqueda significa "No se encontraron resultados", no es error crítico
                continue 

        except Exception as e:
            logger.error(f"❌ Error buscando relaciones GHL: {str(e)}")

    logger.info(f"🔍 Mapa Actual: Propiedad {property_id} tiene {len(found_relations_map)} inquilinos.")
    return found_relations_map

# ---------------------------------------------------------
# 2. BORRAR RELACIÓN (DELETE)
# ---------------------------------------------------------
def ghl_delete_association(access_token, location_id, id_1, id_2):
    """
    Borra la asociación entre dos IDs.
    Intentamos borrar en el orden estándar, si falla, probamos inverso.
    """
    time.sleep(0.2) # Pequeña pausa para no saturar
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Version": "2021-07-28",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    url = "https://services.leadconnectorhq.com/associations/relations"

    # Intento 1: Orden Estándar
    payload = {
        "locationId": location_id,
        "associationId": ASSOCIATION_TYPE_ID,
        "firstRecordId": id_1, 
        "secondRecordId": id_2 
    }

    try:
        response = requests.delete(url, json=payload, headers=headers, timeout=10)
        
        # Si funciona (200 OK o 204 No Content)
        if response.status_code in [200, 204]:
            return True
            
        # Si falla, intentamos invertir los IDs (por si se guardó al revés)
        payload["firstRecordId"] = id_2
        payload["secondRecordId"] = id_1
        response_inv = requests.delete(url, json=payload, headers=headers, timeout=10)
        
        return response_inv.status_code in [200, 204]

    except Exception as e:
        logger.error(f"❌ Excepción borrando asociación: {str(e)}")
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
        if response.status_code in [200, 201]:
            return True
        else:
            logger.error(f"⚠️ Error creando match ({response.status_code}): {response.text}")
            return False
    except Exception as e:
        logger.error(f"❌ Excepción creando match: {str(e)}")
        return False
