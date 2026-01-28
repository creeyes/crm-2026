import threading
import logging
from .utils import ghl_associate_records, ghl_get_current_associations, ghl_delete_association

logger = logging.getLogger(__name__)

# NUEVO: Añadido parámetro 'association_id'
def sync_associations_background(access_token, location_id, origin_record_id, target_ids_list, association_id, association_type="contact"):
    
    def _worker_process():
        # 1. Obtener estado actual
        current_map = ghl_get_current_associations(access_token, location_id, origin_record_id)
        current_ids = set(current_map.keys()) 
        target_ids = set(target_ids_list)
        
        # 2. Calcular diferencias
        ids_to_add = target_ids - current_ids
        ids_to_remove = current_ids - target_ids

        logger.info(f"🔄 Sync Propiedad {origin_record_id}: +{len(ids_to_add)} | -{len(ids_to_remove)}")

        # 3. Borrar excedentes
        for contact_id in ids_to_remove:
            rel_info = current_map.get(contact_id)
            if rel_info and rel_info.get('id'):
                ghl_delete_association(access_token, location_id, rel_info.get('id'))

        # 4. Añadir faltantes
        for contact_id in ids_to_add:
            # NUEVO: Pasamos el association_id dinámico
            ghl_associate_records(access_token, location_id, origin_record_id, contact_id, association_id)

    task_thread = threading.Thread(target=_worker_process)
    task_thread.start()

