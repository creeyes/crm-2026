import threading
import logging
# Importamos las 3 funciones del utils nuevo
from .utils import ghl_associate_records, ghl_get_property_relations, ghl_delete_association

logger = logging.getLogger(__name__)

def sync_associations_background(access_token, location_id, origin_record_id, target_ids_list, association_type="contact"):
    """
    Sincronización Inteligente:
    1. Mira quién hay (utils.get)
    2. Borra a los viejos (utils.delete)
    3. Pone a los nuevos (utils.associate)
    """
    
    def _worker_process():
        total_nuevos = len(target_ids_list)
        logger.info(f"🚀 [Sync] Procesando Propiedad {origin_record_id}. Nuevos candidatos: {total_nuevos}")
        
        # ---------------- FASE 1: LIMPIEZA ----------------
        logger.info("🧹 Fase 1: Buscando contactos antiguos para eliminar...")
        
        # Paso 1: Obtener la lista actual de GHL
        relaciones_actuales = ghl_get_property_relations(access_token, location_id, origin_record_id)
        
        borrados = 0
        if relaciones_actuales:
            for relacion in relaciones_actuales:
                # La API devuelve firstRecordId (Contacto) y secondRecordId (Propiedad)
                id_a_borrar = relacion.get('firstRecordId')
                
                # SEGURIDAD: Si por error nos da el ID de la propiedad, cogemos el otro
                if id_a_borrar == origin_record_id:
                    id_a_borrar = relacion.get('secondRecordId')
                
                if id_a_borrar:
                    # Paso 2: Borrar uno a uno
                    ghl_delete_association(access_token, location_id, origin_record_id, id_a_borrar)
                    borrados += 1
            
            logger.info(f"✨ Limpieza completada. Borrados: {borrados}")
        else:
            logger.info("✨ Nada que borrar. La propiedad estaba vacía.")

        # ---------------- FASE 2: ASIGNACIÓN ----------------
        if total_nuevos > 0:
            logger.info(f"🔗 Fase 2: Añadiendo {total_nuevos} nuevos contactos...")
            exitosos = 0
            
            for target_id in target_ids_list:
                # Paso 3: Crear relación
                res = ghl_associate_records(
                    access_token=access_token,
                    location_id=location_id,
                    record_id_1=origin_record_id, # Propiedad
                    record_id_2=target_id,        # Contacto
                    association_type=association_type
                )
                if res: exitosos += 1
            
            logger.info(f"🏁 [Sync] Finalizado. Añadidos: {exitosos}")
        else:
            # Si target_ids_list es [] (0 habitaciones), llegamos aquí con la propiedad ya limpia.
            logger.info("🏁 [Sync] Finalizado. No hay nuevos candidatos. Propiedad queda vacía.")

    # Ejecutar en segundo plano
    t = threading.Thread(target=_worker_process)
    t.start()
