"""Cria a conta inicial (sem senha padrão). Pode criar outras contas isoladas."""
from app import app
if __name__ == '__main__':
    app.cli.main(args=['criar-usuario'], prog_name='criar_admin.py')
