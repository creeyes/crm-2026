import requests
import logging
import time

logger = logging.getLogger(__name__)

# ID FIJO DE ASOCIACIÓN
ASSOCIATION_TYPE_ID = "695961c25fba08a4bb06272e"

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
                
                # Identificamos contacto
                contact_id = r2 if r1 == property_id else r1
                
                if contact_id:
                    found_relations_map[contact_id] = rel
            
            return found_relations_map
        elif response.status_code == 404:
             return {}
        else:
            logger.error(f"⚠️ Error GHL GET Associations: {response.status_code}")
            return {}
    except Exception as e:
        logger.error(f"❌ Excepción GET Associations: {str(e)}")
        return {}

def ghl_delete_association(access_token, location_id, relation_id):
    time.sleep(0.2)
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Version": "2021-07-28",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    url = f"https://services.leadconnectorhq.com/associations/relations/{relation_id}"
    params = { "locationId": location_id }

    try:
        response = requests.delete(url, headers=headers, params=params, timeout=10)
        return response.status_code in [200, 204]
    except Exception as e:
        logger.error(f"❌ Excepción DELETE Association: {str(e)}")
        return False

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
