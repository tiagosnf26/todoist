"""Backup consistente do banco SQLite, inclusive com o aplicativo em uso."""
import sqlite3
from datetime import datetime
import db
if __name__ == '__main__':
    if not db.DB_PATH.is_file():raise SystemExit('Banco não encontrado; nenhum arquivo foi criado.')
    destino=db.DB_PATH.with_name('todo-backup-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f')+'.db')
    with sqlite3.connect('file:'+str(db.DB_PATH)+'?mode=ro',uri=True) as origem:
        with sqlite3.connect(str(destino)) as copia:origem.backup(copia)
    print('Backup criado:',destino)
