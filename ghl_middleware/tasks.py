import threading
import logging
from .utils import ghl_associate_records

# Configuración de logs para ver el progreso en la consola de Railway
logger = logging.getLogger(__name__)

def sync_associations_background(access_token, origin_record_id, target_ids_list, association_type="contact"):
    """
    Función pública que lanza el proceso en segundo plano.
    Llama a esta función desde tus views.py.
    
    :param access_token: El token de GHL válido.
    :param origin_record_id: ID del objeto que disparó el evento (ej. ID de la Propiedad nueva).
    :param target_ids_list: Lista de IDs con los que hay que conectar (ej. ['contact_id_1', 'contact_id_2']).
    :param association_type: Tipo de asociación (por defecto 'contact').
    """
    
    # Esta es la función 'trabajadora' que se ejecutará en paralelo
    def _worker_process():
        total = len(target_ids_list)
        logger.info(f"🚀 [Background Task] Iniciando sincronización de {total} registros para {origin_record_id}...")
        
        exitosos = 0
        fallidos = 0

        for target_id in target_ids_list:
            # Llamamos a la función unitaria que tienes en utils.py
            resultado = ghl_associate_records(
                access_token=access_token, 
                record_id_1=origin_record_id, 
                record_id_2=target_id, 
                association_type=association_type
            )
            
            if resultado:
                exitosos += 1
            else:
                fallidos += 1
        
        logger.info(f"🏁 [Background Task] Finalizado. Éxitos: {exitosos} | Fallos: {fallidos}")

    # --- AQUÍ ESTÁ EL TRUCO ---
    # Creamos un hilo demonio (daemon=False para asegurar que termine aunque la request principal muera)
    # y le pasamos la función _worker_process para que la ejecute aparte.
    task_thread = threading.Thread(target=_worker_process)
    task_thread.start()
