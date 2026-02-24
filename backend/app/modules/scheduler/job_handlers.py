import logging
from app.modules.email_processor.email_processor import MultiEmailProcessor, EmailConfig, EmailProcessor
from app.models.models import MultiEmailConfig
from app.config.settings import settings

logger = logging.getLogger(__name__)

def handle_full_sync_job(payload: dict):
    """
    Handler para el job 'full_sync'.
    Procesa todos los correos históricos de un usuario (o todos).
    Payload: {"owner_email": "user@example.com"}
    """
    owner_email = payload.get("owner_email")
    logger.info(f"JOB START: Full Sync para owner_email={owner_email or 'ALL'}")
    
    # Usar MultiEmailProcessor para cargar configs
    processor = MultiEmailProcessor(owner_email=owner_email)
    
    # Filtrar configs si es específico
    target_configs = processor.email_configs
    if owner_email:
        target_configs = [c for c in processor.email_configs if c.owner_email == owner_email]
        
    if not target_configs:
        logger.warning("No se encontraron configuraciones de correo para el job.")
        return

    fanout_per_account_cap = int(getattr(settings, "FANOUT_MAX_UIDS_PER_ACCOUNT_PER_RUN", 200) or 0)

    # Procesar cada cuenta con ignore_date_filter=True y prioridad fan-out
    for cfg in target_configs:
        try:
            logger.info(f"Syncing account {cfg.username}...")
            single = EmailProcessor(EmailConfig(
                host=cfg.host, port=cfg.port, username=cfg.username, password=cfg.password,
                search_criteria=cfg.search_criteria,
                search_terms=cfg.search_terms or [],
                search_synonyms=cfg.search_synonyms or {},
                fallback_sender_match=bool(getattr(cfg, "fallback_sender_match", False)),
                fallback_attachment_match=bool(getattr(cfg, "fallback_attachment_match", False)),
            ), owner_email=cfg.owner_email)
            
            # Ejecutar con flag de histórico + fan-out para encolado rápido
            result = single.process_emails(
                ignore_date_filter=True,
                fan_out=True,
                max_discovery_emails=fanout_per_account_cap if fanout_per_account_cap > 0 else None
            )
            
            logger.info(f"Sync result for {cfg.username}: {result.message}")
            single.disconnect()
            
        except Exception as e:
            logger.error(f"Error syncing {cfg.username}: {e}")

    logger.info("JOB END: Full Sync completed.")

def handle_retry_skipped_job(payload: dict):
    """
    Handler para reintentar correos que fueron omitidos por límite de IA.
    Payload: {"owner_email": "user@example.com"} (opcional)
    """
    owner_email = payload.get("owner_email")
    logger.info(f"JOB START: Retry Skipped for owner_email={owner_email or 'ALL'}")
    
    from app.modules.email_processor.processed_registry import _repo
    coll = _repo._get_collection()
    
    query = {"status": "skipped_ai_limit"}
    if owner_email:
        query["owner_email"] = owner_email
        
    # Obtener UIDs únicos agrupados por owner
    # db.processed_emails.aggregate(...)
    pipeline = [
        {"$match": query},
        {"$group": {"_id": "$owner_email", "emails": {"$push": "$$ROOT"}}}
    ]
    
    results = list(coll.aggregate(pipeline))
    
    if not results:
        logger.info("No hay correos en estado skipped_ai_limit.")
        return

    logger.info(f"Encontrados correos para reintentar en {len(results)} usuarios.")

    for group in results:
        user_email = group["_id"]
        emails = group["emails"]
        logger.info(f"Procesando reintentos para {user_email} (Total: {len(emails)})")
        
        # 1. Verificar si tiene acceso a IA ahora (User + Plan)
        try:
            from app.repositories.user_repository import UserRepository
            user_repo = UserRepository()
            trial_info = user_repo.get_trial_info(user_email)
            if not trial_info.get('trial_expired', True) and not trial_info.get('ai_limit_reached', True):
                # Tiene acceso! Procesar estos correos.
                
                # Agrupar por cuenta de correo (account_email)
                accounts = {}
                for e in emails:
                    acc = e.get("account_email")
                    if acc not in accounts:
                        accounts[acc] = []
                    accounts[acc].append(e)
                
                # Procesar cada cuenta
                processor = MultiEmailProcessor(owner_email=user_email)
                for username, items in accounts.items():
                    # Buscar la configuración correcta
                    cfg = next((c for c in processor.email_configs if c.username == username), None)
                    if not cfg:
                        logger.warning(f"Configuración no encontrada para {username} en {user_email}")
                        continue
                        
                    # Procesar items
                    single = EmailProcessor(EmailConfig(
                        host=cfg.host, port=cfg.port, username=cfg.username, password=cfg.password,
                        search_criteria=cfg.search_criteria,
                        search_terms=cfg.search_terms or [],
                        search_synonyms=cfg.search_synonyms or {},
                        fallback_sender_match=bool(getattr(cfg, "fallback_sender_match", False)),
                        fallback_attachment_match=bool(getattr(cfg, "fallback_attachment_match", False)),
                    ), owner_email=user_email)
                    
                    if single.connect():
                        for item in items:
                            email_uid = item.get("email_uid")
                            if not email_uid: continue
                            
                            # Intentar procesar individualmente
                            # Usamos _process_single_email pero necesitamos lógica de descarga...
                            # MEJOR OPCIÓN: Llamar a search_emails NO es suficiente porque queremos UIDs específicos.
                            # Llamamos directamente a _process_single_email pasando el ID.
                            try:
                                inv = single._process_single_email(email_uid)
                                if inv:
                                    logger.info(f"✅ Reintento exitoso para correo {email_uid}")
                                    # store invoice...
                                    single._store_invoice_v2(inv)
                                else:
                                    logger.warning(f"Reintento fallido (sin factura) para {email_uid}")
                            except Exception as ex:
                                logger.error(f"Error reintentando {email_uid}: {ex}")
                        single.disconnect()
            else:
                logger.info(f"Usuario {user_email} aún sin cuota/acceso. Se mantienen skipped.")
                
        except Exception as e:
            logger.error(f"Error en retry job para {user_email}: {e}")

    logger.info("JOB END: Retry Skipped completed.")
