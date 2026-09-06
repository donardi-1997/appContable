#!/bin/bash
# La Patrona VIP - Daily Backup Script
BACKUP_DIR="/opt/la-patrona/backups"
DB_PATH="/opt/la-patrona/data/gato_contable.db"
UPLOADS_PATH="/opt/la-patrona/uploads"
DATE=$(date +%Y%m%d-%H%M%S)
KEEP_DAYS=7

mkdir -p "$BACKUP_DIR"

# Backup SQLite safely
if [ -f "$DB_PATH" ]; then
    sqlite3 "$DB_PATH" ".backup '$BACKUP_DIR/db-$DATE.db'"
    echo "DB backed up: db-$DATE.db"
fi

# Backup uploads
if [ -d "$UPLOADS_PATH" ] && [ "$(ls -A $UPLOADS_PATH 2>/dev/null)" ]; then
    tar czf "$BACKUP_DIR/uploads-$DATE.tar.gz" -C "$UPLOADS_PATH" .
    echo "Uploads backed up: uploads-$DATE.tar.gz"
fi

# Rotate old backups
find "$BACKUP_DIR" -name "db-*.db" -mtime +$KEEP_DAYS -delete
find "$BACKUP_DIR" -name "uploads-*.tar.gz" -mtime +$KEEP_DAYS -delete

echo "Backup completed: $DATE"
