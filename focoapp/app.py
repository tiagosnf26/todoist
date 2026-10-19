"""Foco · gerenciador pessoal de tarefas, Flask + SQLite."""
import csv
import io
import os
import re
import secrets
import hmac
from datetime import date, timedelta
from functools import wraps
from pathlib import Path
from flask import Flask, abort, flash, g, redirect, render_template, request, session, url_for, Response
from werkzeug.security import check_password_hash, generate_password_hash
import click
import db

app = Flask(__name__)
# Persistida fora do código para que Reload não encerre as sessões.
chave = Path(__file__).resolve().parent / '.secret_key'
if not os.environ.get('SECRET_KEY'):
    try:
        fd=os.open(str(chave),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    except FileExistsError:pass
    else:
        with os.fdopen(fd,'w') as f:f.write(secrets.token_hex(32))
app.secret_key = os.environ.get('SECRET_KEY') or chave.read_text().strip()
app.config.update(MAX_CONTENT_LENGTH=1024*1024, SESSION_COOKIE_HTTPONLY=True,
                  SESSION_COOKIE_SAMESITE='Lax', SESSION_COOKIE_SECURE=os.environ.get('TODO_HTTPS')=='1',
                  PERMANENT_SESSION_LIFETIME=timedelta(hours=12))
db.init_db()
PRIORIDADES={'alta':'Alta','media':'Média','baixa':'Baixa'}
STATUS={'pendente':'A fazer','andamento':'Em andamento','concluida':'Concluída'}
VISOES={'abertas':'Minhas tarefas','hoje':'Para hoje','andamento':'Em andamento','atrasadas':'Atrasadas','concluidas':'Concluídas','todas':'Todas as tarefas'}

def login_obrigatorio(view):
    @wraps(view)
    def wrapper(*args,**kwargs):
        if not g.usuario:return redirect(url_for('login'))
        return view(*args,**kwargs)
    return wrapper

@app.before_request
def preparar():
    g.usuario=db.usuario(session['usuario_id']) if session.get('usuario_id') else None
    if 'csrf' not in session:session['csrf']=secrets.token_hex(32)
    if request.method=='POST' and not hmac.compare_digest(session['csrf'],request.form.get('csrf','')):
        abort(400,'Sua sessão expirou. Atualize a página e tente novamente.')

@app.after_request
def cabecalhos(response):
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['X-Frame-Options']='SAMEORIGIN'
    response.headers['Referrer-Policy']='same-origin'
    if request.endpoint!='static':response.headers['Cache-Control']='no-store'
    return response

@app.context_processor
def contexto():
    return dict(usuario=g.usuario,csrf=session.get('csrf'),prioridades=PRIORIDADES,status_tarefa=STATUS,
                visoes=VISOES,hoje=db.hoje(),categorias=db.categorias(g.usuario['id']) if g.usuario else [])

@app.template_filter('data_br')
def data_br(v):
    return date.fromisoformat(v[:10]).strftime('%d/%m/%Y') if v else 'Sem prazo'

@app.route('/login',methods=['GET','POST'])
def login():
    if g.usuario:return redirect(url_for('home'))
    if request.method=='POST':
        with db.conectar() as c:u=c.execute('SELECT * FROM usuarios WHERE email=?',(request.form.get('email','').strip().lower(),)).fetchone()
        if u and check_password_hash(u['senha_hash'],request.form.get('senha','')):
            session.clear();session['usuario_id']=u['id'];session['csrf']=secrets.token_hex(32);session.permanent=True
            with db.conectar() as c:
                seguranca=c.execute('SELECT versao FROM acesso_seguranca WHERE usuario_id=?',(u['id'],)).fetchone()
            session['auth_version']=seguranca['versao'] if seguranca else 0
            return redirect(url_for('home'))
        flash('E-mail ou senha incorretos.','erro')
    with db.conectar() as c:sem_conta=c.execute('SELECT COUNT(*) FROM usuarios').fetchone()[0]==0
    return render_template('login.html',sem_conta=sem_conta)

@app.post('/sair')
@login_obrigatorio
def sair():
    session.clear();return redirect(url_for('login'))

def filtros():
    f = {k:request.args.get(k,'').strip()[:200] for k in ('q','visao','categoria','prioridade','ordem')}
    if f['visao'] not in VISOES: f['visao'] = 'todas'
    if f['prioridade'] not in PRIORIDADES: f['prioridade'] = ''
    if f['ordem'] not in ('prazo','recentes','prioridade'): f['ordem'] = 'prazo'
    return f

@app.get('/')
@login_obrigatorio
def home():
    f=filtros();f['visao']=f['visao'] if f['visao'] in VISOES else 'todas'
    return render_template('home.html',tarefas=db.listar(g.usuario['id'],f),resumo=db.resumo(g.usuario['id']),filtros=f,titulo=VISOES[f['visao']])

def validar(form):
    titulo=form.get('titulo','').strip();descricao=form.get('descricao','').strip()
    if not titulo or len(titulo)>180:raise ValueError('Informe um título com até 180 caracteres.')
    if len(descricao)>5000:raise ValueError('A descrição aceita até 5.000 caracteres.')
    prioridade=form.get('prioridade','media');status=form.get('status','pendente')
    if prioridade not in PRIORIDADES or status not in STATUS:raise ValueError('Status ou prioridade inválidos.')
    prazo=form.get('prazo') or None
    if prazo:date.fromisoformat(prazo)
    categoria=form.get('categoria_id') or None
    if categoria:
        try:categoria=int(categoria)
        except ValueError:raise ValueError('Categoria inválida.')
        if categoria not in {c['id'] for c in db.categorias(g.usuario['id'])}:raise ValueError('Categoria inválida.')
    return titulo,descricao,categoria,prioridade,status,prazo

@app.route('/tarefas/nova',methods=['GET','POST'])
@login_obrigatorio
def nova_tarefa():
    if request.method=='POST':
        try:
            valores=validar(request.form);agora=db.agora()
            with db.conectar() as c:c.execute('''INSERT INTO tarefas(titulo,descricao,categoria_id,prioridade,status,prazo,usuario_id,criado_em,atualizado_em,concluido_em) VALUES (?,?,?,?,?,?,?,?,?,?)''',(*valores,g.usuario['id'],agora,agora,agora if valores[4]=='concluida' else None))
            flash('Tarefa criada. Um passo a menos para depois.','sucesso');return redirect(url_for('home'))
        except ValueError as e:flash(str(e),'erro')
    return render_template('tarefa_editar.html',tarefa=request.form if request.method=='POST' else {},nova=True)

@app.route('/tarefas/<int:tid>/editar',methods=['GET','POST'])
@login_obrigatorio
def editar_tarefa(tid):
    t=db.tarefa(tid,g.usuario['id'])
    if not t:abort(404)
    if request.method=='POST':
        try:
            v=validar(request.form);agora=db.agora()
            with db.conectar() as c:c.execute('''UPDATE tarefas SET titulo=?,descricao=?,categoria_id=?,prioridade=?,status=?,prazo=?,atualizado_em=?,concluido_em=? WHERE id=? AND usuario_id=?''',(*v,agora,(t['concluido_em'] or agora) if v[4]=='concluida' else None,tid,g.usuario['id']))
            flash('Tarefa atualizada.','sucesso');return redirect(url_for('home'))
        except ValueError as e:flash(str(e),'erro');t=request.form
    return render_template('tarefa_editar.html',tarefa=t,nova=False)

@app.post('/tarefas/<int:tid>/concluir')
@login_obrigatorio
def concluir(tid):
    t=db.tarefa(tid,g.usuario['id'])
    if not t:abort(404)
    status='pendente' if t['status']=='concluida' else 'concluida'
    with db.conectar() as c:c.execute('UPDATE tarefas SET status=?,concluido_em=?,atualizado_em=? WHERE id=? AND usuario_id=?',(status,db.agora() if status=='concluida' else None,db.agora(),tid,g.usuario['id']))
    flash('Tarefa reaberta.' if status=='pendente' else 'Tarefa concluída. Bom trabalho!','sucesso')
    # Retorna somente a filtros locais conhecidos, sem redirecionamento arbitrário.
    return redirect(url_for('home',**{k:request.form.get(k,'') for k in ('visao','q','categoria','prioridade','ordem')}))

@app.post('/tarefas/<int:tid>/excluir')
@login_obrigatorio
def excluir_tarefa(tid):
    if not db.tarefa(tid,g.usuario['id']):abort(404)
    with db.conectar() as c:c.execute('DELETE FROM tarefas WHERE id=? AND usuario_id=?',(tid,g.usuario['id']))
    flash('Tarefa excluída.','sucesso');return redirect(url_for('home'))

@app.route('/categorias',methods=['GET','POST'])
@login_obrigatorio
def categorias():
    if request.method=='POST':
        nome=request.form.get('nome','').strip();cor=request.form.get('cor','#0035A3')
        if not nome or len(nome)>60 or not re.fullmatch(r'#[0-9a-fA-F]{6}',cor):flash('Informe nome com até 60 caracteres e uma cor válida.','erro')
        else:
            with db.conectar() as c:
                c.execute('INSERT OR IGNORE INTO categorias(usuario_id,nome,cor) VALUES (?,?,?)',(g.usuario['id'],nome,cor))
            flash('Categoria salva.','sucesso');return redirect(url_for('categorias'))
    return render_template('categorias.html')

@app.post('/categorias/<int:cid>/excluir')
@login_obrigatorio
def excluir_categoria(cid):
    with db.conectar() as c:c.execute('DELETE FROM categorias WHERE id=? AND usuario_id=?',(cid,g.usuario['id']))
    flash('Categoria removida. As tarefas foram preservadas.','sucesso');return redirect(url_for('categorias'))

@app.route('/conta',methods=['GET','POST'])
@login_obrigatorio
def conta():
    if request.method=='POST':
        senha=request.form.get('senha','');nova=request.form.get('nova_senha','')
        if not check_password_hash(g.usuario['senha_hash'],senha):flash('A senha atual não confere.','erro')
        elif len(nova)<10:flash('Use uma senha com pelo menos 10 caracteres.','erro')
        elif nova!=request.form.get('confirmacao'):flash('A confirmação não confere.','erro')
        else:
            with db.conectar() as c:c.execute('UPDATE usuarios SET senha_hash=? WHERE id=?',(generate_password_hash(nova),g.usuario['id']))
            flash('Senha alterada.','sucesso');return redirect(url_for('conta'))
    return render_template('conta.html')

@app.get('/tarefas.csv')
@login_obrigatorio
def exportar():
    b=io.StringIO();w=csv.writer(b,delimiter=';');w.writerow(['Tarefa','Descrição','Categoria','Prioridade','Status','Prazo'])
    def seguro(s):return "'"+s if s.lstrip().startswith(('=','+','-','@')) else s
    for t in db.listar(g.usuario['id'],filtros()):w.writerow([seguro(t['titulo']),seguro(t['descricao']),seguro(t['categoria_nome'] or ''),PRIORIDADES[t['prioridade']],STATUS[t['status']],data_br(t['prazo'])])
    return Response(b.getvalue().encode('utf-8-sig'),mimetype='text/csv; charset=utf-8',headers={'Content-Disposition':'attachment; filename=foco-tarefas.csv'})

@app.cli.command('criar-usuario')
@click.option('--nome',prompt='Nome')
@click.option('--email',prompt='E-mail')
@click.password_option(confirmation_prompt=True)
def criar_usuario(nome,email,password):
    if len(password)<10:raise click.ClickException('Use pelo menos 10 caracteres.')
    if not nome.strip() or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email):raise click.ClickException('Nome ou e-mail inválido.')
    with db.conectar() as c:
        if c.execute('SELECT 1 FROM usuarios WHERE email=?',(email.strip().lower(),)).fetchone():raise click.ClickException('E-mail já cadastrado.')
        uid=c.execute('INSERT INTO usuarios(nome,email,senha_hash,criado_em) VALUES (?,?,?,?)',(nome.strip(),email.strip().lower(),generate_password_hash(password),db.agora())).lastrowid
        c.executemany('INSERT INTO categorias(usuario_id,nome,cor) VALUES (?,?,?)',[(uid,'Trabalho','#0035A3'),(uid,'Pessoal','#0E7C86'),(uid,'Estudos','#7A4FB5')])
    click.echo('Conta criada. Faça login com o e-mail e a senha escolhidos.')

@app.cli.command('redefinir-senha')
@click.option('--email',prompt='E-mail da conta')
@click.password_option(confirmation_prompt=True)
def redefinir_senha(email,password):
    if len(password)<10:raise click.ClickException('Use pelo menos 10 caracteres.')
    with db.conectar() as c:
        cur=c.execute('UPDATE usuarios SET senha_hash=? WHERE email=?',(generate_password_hash(password),email.strip().lower()))
        if not cur.rowcount:raise click.ClickException('Conta não encontrada.')
    click.echo('Senha redefinida.')

@app.errorhandler(400)
@app.errorhandler(404)
def erro(e):return render_template('erro.html',erro=e),e.code

from acesso import instalar
instalar(app)

if __name__=='__main__':app.run(debug=False)
