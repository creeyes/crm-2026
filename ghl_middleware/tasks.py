import threading
import logging
# AQUÍ SÍ: Importamos las funciones desde el otro archivo (utils.py)
from .utils import ghl_associate_records, ghl_get_property_relations, ghl_delete_association

logger = logging.getLogger(__name__)

def sync_associations_background(access_token, location_id, origin_record_id, target_ids_list, association_type="contact"):
    """
    Sincronización completa:
    1. LIMPIA (Borra inquilinos antiguos).
    2. LLENA (Añade nuevos inquilinos).
    """
    
    def _worker_process():
        total_nuevos = len(target_ids_list)
        logger.info(f"🚀 [Sync] Procesando Propiedad {origin_record_id}. Nuevos candidatos: {total_nuevos}")
        
        # ---------------------------------------------------------
        # FASE 1: LIMPIEZA
        # ---------------------------------------------------------
        logger.info("🧹 Fase 1: Limpiando relaciones antiguas...")
        
        relaciones_actuales = ghl_get_property_relations(access_token, location_id, origin_record_id)
        
        borrados = 0
        if relaciones_actuales:
            for relacion in relaciones_actuales:
                # GHL suele devolver: first=Contacto, second=Propiedad
                id_contacto = relacion.get('firstRecordId')
                
                # CORRECCIÓN DE SEGURIDAD:
                if id_contacto == origin_record_id:
                    id_contacto = relacion.get('secondRecordId')

                if id_contacto:
                    ghl_delete_association(access_token, location_id, origin_record_id, id_contacto)
                    borrados += 1
            
            logger.info(f"✨ Limpieza: Se eliminaron {borrados} asociaciones.")
        else:
            logger.info("✨ Propiedad limpia (sin contactos previos).")

        # ---------------------------------------------------------
        # FASE 2: ASIGNACIÓN
        # ---------------------------------------------------------
        if total_nuevos > 0:
            logger.info(f"🔗 Fase 2: Creando {total_nuevos} asociaciones...")
            exitosos = 0
            fallidos = 0

            for target_id in target_ids_list:
                resultado = ghl_associate_records(
                    access_token=access_token,
                    location_id=location_id,
                    record_id_1=origin_record_id, # Propiedad
                    record_id_2=target_id,        # Contacto
                    association_type=association_type
                )
                
                if resultado:
                    exitosos += 1
                else:
                    fallidos += 1
            
            logger.info(f"🏁 [Sync] Finalizado. Éxitos: {exitosos} | Fallos: {fallidos}")
        else:
            logger.info("🏁 [Sync] Finalizado. Sin nuevos candidatos. La propiedad queda vacía.")

    # Ejecutar en segundo plano
    task_thread = threading.Thread(target=_worker_process)
    task_thread.start()
