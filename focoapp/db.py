"""SQLite local. Inicialização aditiva e caminhos independentes do diretório atual."""
import os
import sqlite3
from pathlib import Path
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get('TODO_DB_PATH', str(BASE_DIR / 'todo.db')))
FUSO = timezone(timedelta(hours=-4))

def agora():
    return datetime.now(FUSO).isoformat(timespec='seconds')

def hoje():
    return datetime.now(FUSO).date().isoformat()

@contextmanager
def conectar():
    c = sqlite3.connect(str(DB_PATH), timeout=20)
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA foreign_keys=ON')
    c.execute('PRAGMA busy_timeout=20000')
    try:
        yield c
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()

def init_db():
    with conectar() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS usuarios (
          id INTEGER PRIMARY KEY, nome TEXT NOT NULL, email TEXT NOT NULL UNIQUE,
          senha_hash TEXT NOT NULL, criado_em TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS categorias (
          id INTEGER PRIMARY KEY, usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
          nome TEXT NOT NULL, cor TEXT NOT NULL DEFAULT '#0035A3', UNIQUE(usuario_id,nome));
        CREATE TABLE IF NOT EXISTS tarefas (
          id INTEGER PRIMARY KEY, usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
          titulo TEXT NOT NULL, descricao TEXT NOT NULL DEFAULT '',
          categoria_id INTEGER REFERENCES categorias(id) ON DELETE SET NULL,
          prioridade TEXT NOT NULL DEFAULT 'media' CHECK(prioridade IN ('alta','media','baixa')),
          status TEXT NOT NULL DEFAULT 'pendente' CHECK(status IN ('pendente','andamento','concluida')),
          prazo TEXT, criado_em TEXT NOT NULL, atualizado_em TEXT NOT NULL, concluido_em TEXT);
        CREATE INDEX IF NOT EXISTS idx_tarefas_usuario ON tarefas(usuario_id,status,prazo);
        ''')

def usuario(uid):
    with conectar() as c:
        return c.execute('SELECT * FROM usuarios WHERE id=?', (uid,)).fetchone()

def tarefa(tid, uid):
    with conectar() as c:
        return c.execute('SELECT * FROM tarefas WHERE id=? AND usuario_id=?', (tid,uid)).fetchone()

def categorias(uid):
    with conectar() as c:
        return c.execute('SELECT * FROM categorias WHERE usuario_id=? ORDER BY nome COLLATE NOCASE',(uid,)).fetchall()

def listar(uid, filtros):
    sql='''SELECT t.*, c.nome AS categoria_nome,c.cor AS categoria_cor FROM tarefas t
           LEFT JOIN categorias c ON c.id=t.categoria_id WHERE t.usuario_id=?'''
    params=[uid]
    if filtros.get('q'):
        sql+=' AND (t.titulo LIKE ? OR t.descricao LIKE ?)';params.extend(['%'+filtros['q']+'%']*2)
    if filtros.get('categoria'):
        sql+=' AND t.categoria_id=?';params.append(filtros['categoria'])
    if filtros.get('prioridade'):
        sql+=' AND t.prioridade=?';params.append(filtros['prioridade'])
    visao=filtros.get('visao','todas')
    if visao=='hoje':
        sql+=" AND t.prazo=? AND t.status!='concluida'";params.append(hoje())
    elif visao=='atrasadas':
        sql+=" AND t.prazo<? AND t.status!='concluida'";params.append(hoje())
    elif visao=='concluidas':sql+=" AND t.status='concluida'"
    elif visao=='andamento':sql+=" AND t.status='andamento'"
    elif visao!='todas':sql+=" AND t.status!='concluida'"
    ordens={
      'prazo':"CASE WHEN t.status='concluida' THEN 1 ELSE 0 END, COALESCE(t.prazo,'9999-12-31'), t.id DESC",
      'recentes':'t.id DESC',
      'prioridade':"CASE t.prioridade WHEN 'alta' THEN 0 WHEN 'media' THEN 1 ELSE 2 END, COALESCE(t.prazo,'9999-12-31'),t.id DESC"}
    sql+=" ORDER BY CASE WHEN t.status='concluida' THEN 1 ELSE 0 END, "+ordens.get(filtros.get('ordem'),ordens['prazo'])
    with conectar() as c:return c.execute(sql,params).fetchall()

def resumo(uid):
    with conectar() as c:
        return dict(c.execute('''SELECT COUNT(*) total,
        COALESCE(SUM(status='concluida'),0) concluidas,
        COALESCE(SUM(status!='concluida'),0) abertas,
        COALESCE(SUM(status!='concluida' AND prazo=?),0) hoje,
        COALESCE(SUM(status!='concluida' AND prazo<?),0) atrasadas,
        COALESCE(SUM(status='andamento'),0) andamento FROM tarefas WHERE usuario_id=?''',(hoje(),hoje(),uid)).fetchone())
