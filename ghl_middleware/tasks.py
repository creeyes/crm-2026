# tasks.py
import threading
import logging
# AÑADIMOS LAS NUEVAS FUNCIONES DE UTILS AQUI:
from .utils import ghl_associate_records, ghl_get_property_relations, ghl_delete_association

logger = logging.getLogger(__name__)

def sync_associations_background(access_token, location_id, origin_record_id, target_ids_list, association_type="contact"):
    """
    Función en background que gestiona la sincronización completa:
    1. LIMPIA las relaciones antiguas (borra a los inquilinos previos).
    2. CREA las nuevas relaciones (si hay nuevos candidatos).
    """
    
    def _worker_process():
        total_nuevos = len(target_ids_list)
        logger.info(f"🚀 [Background Task] Sincronizando propiedad {origin_record_id}. Nuevos candidatos: {total_nuevos}")
        
        # --- FASE 1: LIMPIEZA (El Exorcismo) ---
        # Antes de añadir a nadie, miramos quién está metido ahí y lo sacamos.
        logger.info("🧹 Iniciando limpieza de relaciones antiguas...")
        
        relaciones_antiguas = ghl_get_property_relations(access_token, location_id, origin_record_id)
        
        borrados = 0
        if relaciones_antiguas:
            for rel in relaciones_antiguas:
                # GHL suele devolver el contacto en 'firstRecordId' cuando consultamos desde la propiedad
                contacto_antiguo_id = rel.get('firstRecordId')
                
                # Si por lo que sea el ID está en el otro campo (a veces pasa), lo intentamos recuperar
                if not contacto_antiguo_id:
                     contacto_antiguo_id = rel.get('id') # Fallback

                if contacto_antiguo_id:
                    ghl_delete_association(access_token, location_id, origin_record_id, contacto_antiguo_id)
                    borrados += 1
            
            logger.info(f"✨ Limpieza terminada: Se eliminaron {borrados} asociaciones antiguas.")
        else:
            logger.info("✨ La propiedad estaba vacía. No hay nada que borrar.")

        # --- FASE 2: ASIGNACIÓN (El Match) ---
        # Ahora que la propiedad está limpia, metemos a los nuevos (si los hay)
        
        if total_nuevos > 0:
            exitosos = 0
            fallidos = 0
            logger.info(f"🔗 Iniciando asociación de {total_nuevos} nuevos contactos...")

            for target_id in target_ids_list:
                resultado = ghl_associate_records(
                    access_token=access_token,
                    location_id=location_id, 
                    record_id_1=origin_record_id, 
                    record_id_2=target_id, 
                    association_type=association_type
                )
                
                if resultado:
                    exitosos += 1
                else:
                    fallidos += 1
            
            logger.info(f"🏁 [Background Task] Finalizado. Éxitos: {exitosos} | Fallos: {fallidos}")
        else:
            logger.info("🏁 [Background Task] Finalizado. No había nuevos contactos para añadir (0 habitaciones o sin coincidencia).")

    # Iniciar el hilo en segundo plano
    task_thread = threading.Thread(target=_worker_process)
    task_thread.start()
