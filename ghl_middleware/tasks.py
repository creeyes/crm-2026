# tasks.py
import threading
import logging
from .utils import ghl_associate_records

logger = logging.getLogger(__name__)

def sync_associations_background(access_token, location_id, origin_record_id, target_ids_list, association_type="contact"):
    """
    Función en background que recibe location_id y lo pasa al utils.
    """
    
    def _worker_process():
        total = len(target_ids_list)
        logger.info(f"🚀 [Background Task] Iniciando sync de {total} registros para {origin_record_id}...")
        
        exitosos = 0
        fallidos = 0

        for target_id in target_ids_list:
            # Pasamos location_id a la función final
            resultado = ghl_associate_records(
                access_token=access_token,
                location_id=location_id, # <--- NUEVO PARAMETRO
                record_id_1=origin_record_id, 
                record_id_2=target_id, 
                association_type=association_type
            )
            
            if resultado:
                exitosos += 1
            else:
                fallidos += 1
        
        logger.info(f"🏁 [Background Task] Finalizado. Éxitos: {exitosos} | Fallos: {fallidos}")

    task_thread = threading.Thread(target=_worker_process)
    task_thread.start()
