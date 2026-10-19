"""Exemplo para o arquivo WSGI indicado na aba Web do PythonAnywhere."""
import os
import sys
pasta = '/home/SEU_USUARIO/focoapp'
if pasta not in sys.path:
    sys.path.insert(0, pasta)
os.environ['TODO_HTTPS'] = '1'
from app import app as application
