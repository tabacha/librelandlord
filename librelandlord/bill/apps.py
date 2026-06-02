import logging
import os
import sys
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
from django.apps import AppConfig
from django.db import close_old_connections

logger = logging.getLogger(__name__)


class BillConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'bill'

    def ready(self):
        from django.contrib import admin
        from .views import run_heating_info_task

        # Admin Site Konfiguration
        admin.site.site_header = 'LibreLandlord'
        admin.site.site_title = 'LibreLandlord'
        admin.site.index_title = 'Dashboard'

        # Scheduler nur einmal starten
        # Bei runserver: RUN_MAIN='true' nur im Child-Prozess (nach Reloader-Start)
        # Bei gunicorn/production: RUN_MAIN existiert nicht, 'runserver' nicht in argv
        is_runserver = 'runserver' in sys.argv
        run_main = os.environ.get('RUN_MAIN')
        if (is_runserver and run_main == 'true') or (not is_runserver):
            self._start_scheduler(run_heating_info_task)

    def _start_scheduler(self, run_heating_info_task):
        """Startet den APScheduler für periodische Tasks."""
        # Scheduler nur starten wenn Server läuft (runserver oder gunicorn)
        # Nicht bei Management-Commands wie check, migrate, makemigrations, etc.
        is_runserver = 'runserver' in sys.argv
        is_gunicorn = 'gunicorn' in sys.argv[0] if sys.argv else False
        if not is_runserver and not is_gunicorn:
            return

        def scheduled_heating_info_task():
            """Wrapper für den Heating Info Task mit Logging."""
            logger.info("Scheduled heating_info_task started")
            close_old_connections()
            try:
                result = run_heating_info_task()
                processed_count = len(result.get('processed', []))
                pending_count = len(result.get('pending', []))
                logger.info(f"Scheduled heating_info_task completed: {processed_count} processed, {pending_count} pending")
            except Exception:
                logger.exception("Scheduled heating_info_task failed")
                raise
            finally:
                close_old_connections()

        def scheduled_blocklist_cleanup():
            """Entfernt abgelaufene Einträge aus DB und In-Memory-Blocklist."""
            close_old_connections()
            try:
                from django.utils import timezone
                from bill.models import BlockedNetwork
                from bill.middleware import BLOCK_EXPIRY, _blocklist, _lock
                expiry_cutoff = timezone.now() - BLOCK_EXPIRY
                deleted, _ = BlockedNetwork.objects.filter(last_seen__lt=expiry_cutoff).delete()
                # Auch aus In-Memory-Dict entfernen (für Einträge die nie wieder anfragen)
                with _lock:
                    expired_keys = [k for k, ts in _blocklist.items() if timezone.now() - ts > BLOCK_EXPIRY]
                    for k in expired_keys:
                        del _blocklist[k]
                if deleted or expired_keys:
                    logger.info("Blocklist-Cleanup: %d DB-Einträge, %d RAM-Einträge entfernt", deleted, len(expired_keys))
            except Exception:
                logger.exception("Blocklist-Cleanup fehlgeschlagen")
            finally:
                close_old_connections()

        scheduler = BackgroundScheduler()

        # Job alle 12 Stunden ausführen
        scheduler.add_job(
            scheduled_heating_info_task,
            trigger=IntervalTrigger(hours=12),
            id='heating_info_task',
            name='Calculate heating info for all apartments',
            replace_existing=True,
        )

        # Erster Lauf nach 30 Sekunden (Zeit für DB-Initialisierung)
        scheduler.add_job(
            scheduled_heating_info_task,
            trigger=DateTrigger(run_date=datetime.now() + timedelta(seconds=30)),
            id='heating_info_task_initial',
            name='Initial heating info calculation',
            replace_existing=True,
        )

        scheduler.add_job(
            scheduled_blocklist_cleanup,
            trigger=IntervalTrigger(hours=24),
            id='blocklist_cleanup',
            name='Cleanup expired blocked networks',
            replace_existing=True,
        )

        scheduler.start()
        logger.info("APScheduler started - heating_info_task scheduled every 12 hours, initial run in 30 seconds")
