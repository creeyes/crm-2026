import threading
import logging
from .utils import ghl_associate_records, ghl_get_current_associations, ghl_delete_association

logger = logging.getLogger(__name__)

def sync_associations_background(access_token, location_id, origin_record_id, target_ids_list, association_type="contact"):
    """
    Sincronización Inteligente (Delta Sync):
    1. Obtiene lo que hay en GHL.
    2. Compara con lo que debería haber (target_ids_list).
    3. Solo BORRA lo que sobra y AÑADE lo que falta.
    """
    
    def _worker_process():
        logger.info(f"🚀 [Sync] Iniciando para Propiedad {origin_record_id}")
        
        # 1. Obtener estado actual en GHL (Mapa: ID_Contacto -> Info_Relacion)
        current_map = ghl_get_current_associations(access_token, location_id, origin_record_id)
        current_ids = set(current_map.keys()) # Convertimos a Conjunto (Set)
        
        # 2. Definir estado deseado (Lo que viene de Django)
        target_ids = set(target_ids_list)
        
        # 3. Calcular diferencias (Matemática de Conjuntos)
        ids_to_add = target_ids - current_ids      # Faltan en GHL
        ids_to_remove = current_ids - target_ids   # Sobran en GHL
        ids_to_keep = current_ids & target_ids     # Ya están bien (Intersección)

        logger.info(f"📊 Análisis: {len(ids_to_keep)} correctos | {len(ids_to_add)} a añadir | {len(ids_to_remove)} a borrar")

        # 4. Ejecutar BORRADOS (Limpieza)
        removidos = 0
        for contact_id in ids_to_remove:
            # Usamos los IDs exactos que recuperamos de GHL para asegurar el tiro
            rel_info = current_map.get(contact_id, {})
            r1 = rel_info.get('firstRecordId') or contact_id
            r2 = rel_info.get('secondRecordId') or origin_record_id
            
            if ghl_delete_association(access_token, location_id, r1, r2):
                removidos += 1
                logger.info(f"🗑️ [Sync] Eliminado: {contact_id}")

        # 5. Ejecutar CREACIONES (Nuevos Matches)
        agregados = 0
        for contact_id in ids_to_add:
            if ghl_associate_records(access_token, location_id, origin_record_id, contact_id):
                agregados += 1
                logger.info(f"✅ [Sync] Añadido: {contact_id}")

        logger.info(f"🏁 [Sync] Finalizado. (+{agregados} / -{removidos})")

    # Ejecutar en segundo plano
    task_thread = threading.Thread(target=_worker_process)
    task_thread.start()
