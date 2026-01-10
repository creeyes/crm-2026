import threading
import logging
from .utils import ghl_associate_records, ghl_get_current_associations, ghl_delete_association

logger = logging.getLogger(__name__)

def sync_associations_background(access_token, location_id, origin_record_id, target_ids_list, association_type="contact"):
    
    def _worker_process():
        logger.info(f"🚀 [Sync] PROCESANDO Propiedad {origin_record_id}")
        
        # 1. Obtener estado actual
        current_map = ghl_get_current_associations(access_token, location_id, origin_record_id)
        current_ids = set(current_map.keys()) 
        
        # 2. Definir estado deseado
        target_ids = set(target_ids_list)
        
        # 3. Calcular diferencias
        ids_to_add = target_ids - current_ids
        ids_to_remove = current_ids - target_ids
        ids_to_keep = current_ids & target_ids

        logger.info(f"📊 [Sync] Mantener: {len(ids_to_keep)} | Añadir: {len(ids_to_add)} | Borrar: {len(ids_to_remove)}")

        # 4. EJECUTAR BORRADOS (POR ID ÚNICO)
        removidos = 0
        for contact_id in ids_to_remove:
            
            # RECUPERAMOS EL OBJETO DEL MAPA
            rel_info = current_map.get(contact_id)
            
            if rel_info:
                # ¡AQUÍ ESTÁ LA CLAVE! Extraemos el ID único de la relación
                relation_unique_id = rel_info.get('id')
                
                if relation_unique_id:
                    logger.info(f"👉 [Sync] Borrando relación {relation_unique_id} (Contacto {contact_id})")
                    
                    if ghl_delete_association(access_token, location_id, relation_unique_id):
                        removidos += 1
                    else:
                        logger.error(f"💀 [Sync] Falló borrado de ID {relation_unique_id}")
                else:
                    logger.error(f"⚠️ [Sync] El objeto no tenía campo 'id'. JSON: {rel_info}")
            else:
                logger.error(f"⚠️ [Sync] No hay info para {contact_id}")

        # 5. Ejecutar CREACIONES
        agregados = 0
        for contact_id in ids_to_add:
            if ghl_associate_records(access_token, location_id, origin_record_id, contact_id):
                agregados += 1

        logger.info(f"🏁 [Sync] Finalizado. (+{agregados} / -{removidos})")

    task_thread = threading.Thread(target=_worker_process)
    task_thread.start()
