import logging
import os
import sys
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
from django.apps import AppConfig

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
        # Scheduler nur starten wenn nicht in Tests oder Migrations
        if any(arg in sys.argv for arg in ['test', 'migrate', 'makemigrations', 'collectstatic']):
            return

        def scheduled_heating_info_task():
            """Wrapper für den Heating Info Task mit Logging."""
            logger.info("Scheduled heating_info_task started")
            result = run_heating_info_task()
            processed_count = len(result.get('processed', []))
            pending_count = len(result.get('pending', []))
            logger.info(f"Scheduled heating_info_task completed: {processed_count} processed, {pending_count} pending")

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

        scheduler.start()
        logger.info("APScheduler started - heating_info_task scheduled every 12 hours, initial run in 30 seconds")
