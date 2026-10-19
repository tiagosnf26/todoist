"""Verificação local sem imprimir senhas, e-mails ou conteúdo das tarefas."""
import db
if __name__ == '__main__':
    if not db.DB_PATH.is_file():
        raise SystemExit('Banco ainda não criado. Execute python criar_admin.py.')
    with db.conectar() as c:
        print('Integridade:', c.execute('PRAGMA integrity_check').fetchone()[0])
        for tabela in ('usuarios','categorias','tarefas'):
            print(tabela+':', c.execute('SELECT COUNT(*) FROM '+tabela).fetchone()[0])
