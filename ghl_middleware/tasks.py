import threading
import logging
from .utils import ghl_associate_records, ghl_get_current_associations, ghl_delete_association

logger = logging.getLogger(__name__)

def sync_associations_background(access_token, location_id, origin_record_id, target_ids_list, association_type="contact"):
    
    def _worker_process():
        logger.info(f"🚀 [Sync] INICIO PROCESO para Propiedad {origin_record_id}")
        
        # 1. Obtener estado actual
        current_map = ghl_get_current_associations(access_token, location_id, origin_record_id)
        current_ids = set(current_map.keys()) 
        
        # 2. Definir estado deseado
        target_ids = set(target_ids_list)
        
        # 3. Calcular diferencias
        ids_to_add = target_ids - current_ids
        ids_to_remove = current_ids - target_ids
        ids_to_keep = current_ids & target_ids

        logger.info(f"📊 [Sync] Resumen: {len(ids_to_keep)} OK | {len(ids_to_add)} NUEVOS | {len(ids_to_remove)} A BORRAR")

        # 4. EJECUTAR BORRADOS
        removidos = 0
        for contact_id in ids_to_remove:
            logger.info(f"👉 [Sync] Intentando borrar contacto: {contact_id}")
            
            # RECUPERAMOS EL OBJETO EXACTO
            rel_info = current_map.get(contact_id)
            
            if rel_info:
                exact_first_id = rel_info.get('firstRecordId')
                exact_second_id = rel_info.get('secondRecordId')
                
                logger.warning(f"🔍 [Sync] Datos recuperados del mapa para {contact_id}: First={exact_first_id} | Second={exact_second_id}")
                
                if ghl_delete_association(access_token, location_id, exact_first_id, exact_second_id):
                    removidos += 1
                    logger.info(f"🗑️ [Sync] BORRADO EXITOSO: {contact_id}")
                else:
                    logger.error(f"💀 [Sync] FALLÓ EL BORRADO de {contact_id}")
            else:
                logger.error(f"⚠️ [Sync] No se encontró info en el mapa para {contact_id}. ¿Cómo llegó aquí?")

        # 5. Ejecutar CREACIONES
        agregados = 0
        for contact_id in ids_to_add:
            if ghl_associate_records(access_token, location_id, origin_record_id, contact_id):
                agregados += 1

        logger.info(f"🏁 [Sync] Finalizado. (+{agregados} / -{removidos})")

    task_thread = threading.Thread(target=_worker_process)
    task_thread.start()
