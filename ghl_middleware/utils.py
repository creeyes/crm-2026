import threading
import logging
# Importamos las 3 funciones clave de tu nuevo utils
from .utils import ghl_associate_records, ghl_get_property_relations, ghl_delete_association

logger = logging.getLogger(__name__)

def sync_associations_background(access_token, location_id, origin_record_id, target_ids_list, association_type="contact"):
    """
    Gestiona la sincronización en segundo plano:
    1. Revisa quién está conectado actualmente a la propiedad.
    2. BORRA todas esas conexiones antiguas (Limpieza).
    3. CREA las nuevas conexiones (si hay nuevos candidatos en target_ids_list).
    """
    
    def _worker_process():
        total_nuevos = len(target_ids_list)
        logger.info(f"🚀 [Sync Task] Procesando Propiedad {origin_record_id}. Nuevos candidatos: {total_nuevos}")
        
        # ---------------------------------------------------------
        # FASE 1: LIMPIEZA DE "ZOMBIES" (Borrar antiguos)
        # ---------------------------------------------------------
        logger.info("🧹 Fase 1: Buscando relaciones antiguas para limpiar...")
        
        # Consultamos a GHL quién está en la propiedad ahora mismo
        relaciones_actuales = ghl_get_property_relations(access_token, location_id, origin_record_id)
        
        borrados = 0
        if relaciones_actuales:
            for relacion in relaciones_actuales:
                # En tu esquema (utils): 
                # firstRecordId = CONTACTO
                # secondRecordId = PROPIEDAD
                
                id_contacto_a_borrar = relacion.get('firstRecordId')
                
                # Validación extra: Si por error el ID es el mismo que la propiedad, intentamos coger el otro
                if id_contacto_a_borrar == origin_record_id:
                    id_contacto_a_borrar = relacion.get('secondRecordId')
                
                if id_contacto_a_borrar:
                    # Ejecutamos el borrado
                    ghl_delete_association(access_token, location_id, origin_record_id, id_contacto_a_borrar)
                    borrados += 1
            
            logger.info(f"✨ Limpieza completada: Se eliminaron {borrados} asociaciones previas.")
        else:
            logger.info("✨ La propiedad estaba limpia (no tenía contactos asociados).")

        # ---------------------------------------------------------
        # FASE 2: ASIGNACIÓN DE NUEVOS (Si aplica)
        # ---------------------------------------------------------
        if total_nuevos > 0:
            logger.info(f"🔗 Fase 2: Creando {total_nuevos} nuevas asociaciones...")
            exitosos = 0
            fallidos = 0

            for target_id in target_ids_list:
                # Creamos la relación nueva
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
            
            logger.info(f"🏁 [Sync Task] Finalizado. Nuevos añadidos: {exitosos} | Fallos: {fallidos}")
        else:
            # Caso importante: Si pusiste 0 habitaciones, la lista viene vacía.
            # Como ya borramos en la Fase 1, la propiedad queda vacía correctamente.
            logger.info("🏁 [Sync Task] Finalizado. No hay nuevos candidatos para añadir. La propiedad queda vacía.")

    # Ejecutar en hilo separado para no bloquear el servidor
    task_thread = threading.Thread(target=_worker_process)
    task_thread.start()
