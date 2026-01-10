import threading
import logging
from .utils import ghl_associate_records, ghl_get_current_associations, ghl_delete_association

logger = logging.getLogger(__name__)

def sync_associations_background(access_token, location_id, origin_record_id, target_ids_list, association_type="contact"):
    
    def _worker_process():
        logger.info(f"🚀 [Sync] Iniciando para Propiedad {origin_record_id}")
        
        # 1. Obtener estado actual (Ahora usando el endpoint específico de Custom Objects)
        current_map = ghl_get_current_associations(access_token, location_id, origin_record_id)
        current_ids = set(current_map.keys()) # IDs de los contactos actuales
        
        # 2. Definir estado deseado
        target_ids = set(target_ids_list)
        
        # 3. Calcular diferencias
        ids_to_add = target_ids - current_ids
        ids_to_remove = current_ids - target_ids
        ids_to_keep = current_ids & target_ids

        logger.info(f"📊 Análisis: {len(ids_to_keep)} correctos | {len(ids_to_add)} a añadir | {len(ids_to_remove)} a borrar")

        # 4. Ejecutar BORRADOS
        removidos = 0
        for contact_id in ids_to_remove:
            # IMPORTANTE: Ahora pasamos (Propiedad, Contacto) explícitamente.
            # La función ghl_delete_association probará ambos sentidos (A->B y B->A) automáticamente.
            if ghl_delete_association(access_token, location_id, origin_record_id, contact_id):
                removidos += 1
                logger.info(f"🗑️ [Sync] Eliminado Contacto: {contact_id}")

        # 5. Ejecutar CREACIONES
        agregados = 0
        for contact_id in ids_to_add:
            if ghl_associate_records(access_token, location_id, origin_record_id, contact_id):
                agregados += 1
                logger.info(f"✅ [Sync] Añadido Contacto: {contact_id}")

        logger.info(f"🏁 [Sync] Finalizado. (+{agregados} / -{removidos})")

    task_thread = threading.Thread(target=_worker_process)
    task_thread.start()
