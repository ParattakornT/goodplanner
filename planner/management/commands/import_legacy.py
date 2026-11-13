"""Copy the old SQLite data once, leaving its original database untouched."""
import re
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from planner.models import LegacyImport, Task, User
from planner.views import task_data


def timestamp(value):
    parsed = datetime.fromisoformat(value)
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed


class Command(BaseCommand):
    help = 'Back up and import accounts/plans from the original Node SQLite database once.'

    def add_arguments(self, parser):
        parser.add_argument('--source', type=Path, default=settings.DATA_DIR / 'goodplanner.sqlite')
        parser.add_argument('--backup-dir', type=Path, default=settings.DATA_DIR / 'backups')

    def handle(self, *args, **options):
        if LegacyImport.objects.filter(source='node-v1').exists():
            self.stdout.write('Legacy data already imported; no changes made.')
            return
        source = options['source'].resolve()
        if not source.is_file():
            self.stdout.write('No legacy database found; starting with a new Django database.')
            return
        if str(source) == str(Path(settings.DATABASES['default']['NAME']).resolve()):
            raise CommandError('Source must be separate from the Django database.')
        if User.objects.exists() or Task.objects.exists():
            raise CommandError('Django already contains data. Import stopped to avoid overwriting accounts/plans.')
        backup_dir = options['backup_dir'].resolve()
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup = backup_dir / ('node-before-django-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.sqlite')
        # SQLite backup includes committed WAL data and creates a consistent snapshot.
        try:
            with closing(sqlite3.connect(source.as_uri() + '?mode=ro', uri=True)) as original, closing(sqlite3.connect(backup)) as snapshot:
                original.backup(snapshot)
            with closing(sqlite3.connect(backup.as_uri() + '?mode=ro', uri=True)) as snapshot:
                snapshot.row_factory = sqlite3.Row
                users = snapshot.execute('SELECT * FROM users ORDER BY id').fetchall()
                tasks = snapshot.execute('SELECT * FROM tasks ORDER BY id').fetchall()
            with transaction.atomic():
                for row in users:
                    stored = row['password_hash']
                    if not re.fullmatch(r'scrypt\$32768\$8\$3\$[0-9a-f]{32}\$[0-9a-f]{128}', stored):
                        raise ValueError('Unsupported legacy password encoding')
                    User.objects.create(id=row['id'], email=row['email'].strip().lower(), display_name=row['display_name'],
                                        password='legacy_' + stored, created_at=timestamp(row['created_at']))
                for row in tasks:
                    data = task_data({'title': row['title'], 'notes': row['notes'], 'date': row['task_date'],
                                      'time': row['task_time'], 'priority': row['priority'], 'completed': bool(row['completed'])})
                    Task.objects.create(id=row['id'], user_id=row['user_id'], **data,
                                        created_at=timestamp(row['created_at']), updated_at=timestamp(row['updated_at']))
                LegacyImport.objects.create(source='node-v1', user_count=len(users), task_count=len(tasks))
        except Exception as exc:
            # Do not include row contents or hashes in terminal errors.
            raise CommandError(f'Import stopped ({type(exc).__name__}); database rows were not partially imported. Backup: {backup}') from exc
        self.stdout.write(self.style.SUCCESS(f'Imported {len(users)} accounts and {len(tasks)} plans. Backup: {backup}'))
