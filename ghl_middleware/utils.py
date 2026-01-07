def ghl_delete_relation_search_and_destroy(access_token, location_id, propiedad_id, contacto_id):
    """
    Estrategia 'Search & Destroy':
    1. Busca todas las relaciones del contacto.
    2. Encuentra la que apunta a la propiedad específica.
    3. Elimina esa relación usando su ID único.
    """
    
    # --- PASO 1: BUSCAR LA RELACIÓN (GET) ---
    search_url = "https://services.leadconnectorhq.com/associations/relations"
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Version": "2021-07-28",
        "Accept": "application/json"
    }
    
    # Filtramos por el Contacto (First Record) para no traer toda la base de datos
    params = {
        "locationId": location_id,
        "firstRecordId": contacto_id 
    }

    relation_id_to_delete = None

    try:
        # Petición GET para listar
        response = requests.get(search_url, headers=headers, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            relations = data.get('relations', []) # A veces devuelve lista directa o dentro de clave
            
            # Buscamos el Match en memoria
            for relation in relations:
                # Verificamos que el "secondRecordId" sea nuestra Propiedad
                if relation.get('secondRecordId') == propiedad_id:
                    relation_id_to_delete = relation.get('id')
                    logger.info(f"🔎 Relación encontrada: {relation_id_to_delete}")
                    break
        else:
            logger.error(f"⚠️ No se pudieron listar relaciones: {response.text}")
            return False

    except Exception as e:
        logger.error(f"❌ Error buscando relación GHL: {str(e)}")
        return False

    # --- PASO 2: DESTRUIR LA RELACIÓN (DELETE) ---
    if relation_id_to_delete:
        delete_url = f"https://services.leadconnectorhq.com/associations/relations/{relation_id_to_delete}"
        
        try:
            del_response = requests.delete(delete_url, headers=headers, timeout=10)
            
            if del_response.status_code in [200, 204]:
                logger.info(f"🗑️ GHL Relación Eliminada: {contacto_id} -x- {propiedad_id}")
                return True
            else:
                logger.error(f"❌ Error al borrar relación ({del_response.status_code}): {del_response.text}")
                return False
        except Exception as e:
            logger.error(f"❌ Excepción borrando GHL: {str(e)}")
            return False
            
    else:
        logger.warning(f"⚠️ No se encontró ninguna relación activa entre Contacto {contacto_id} y Propiedad {propiedad_id}")
        return False
            
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Excepción de conexión GHL: {str(e)}")
        return False
