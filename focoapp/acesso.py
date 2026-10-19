"""Cadastro e recuperação. Apenas biblioteca padrão e dependências já existentes."""
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import time
import urllib.request
from pathlib import Path
from flask import request, session, g, redirect, url_for, render_template, flash, abort
from werkzeug.security import generate_password_hash, check_password_hash
import db


def instalar(app):
    with db.conectar() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS acesso_seguranca (
            usuario_id INTEGER PRIMARY KEY REFERENCES usuarios(id) ON DELETE CASCADE,
            versao INTEGER NOT NULL DEFAULT 0, codigo_hash TEXT);
        CREATE TABLE IF NOT EXISTS recuperacoes (
            token_hash TEXT PRIMARY KEY, usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
            expira INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS acesso_limites (chave TEXT PRIMARY KEY, janela INTEGER NOT NULL, total INTEGER NOT NULL);
        ''')

    def digest(texto):
        return hmac.new(app.secret_key.encode() if isinstance(app.secret_key,str) else app.secret_key,texto.encode(),hashlib.sha256).hexdigest()

    def email():
        return request.form.get('email','').strip().lower()[:254]

    def senha_valida():
        s=request.form.get('senha','')
        return 10<=len(s)<=256 and s==request.form.get('confirmacao','')

    def configurar_email():
        path=Path(__file__).resolve().parent/'email_config.json'
        try:
            config=json.loads(path.read_text()) if path.exists() else {}
        except (ValueError,OSError):config={}
        return {'api_key':os.environ.get('FOCO_SENDGRID_API_KEY') or config.get('api_key'),
                'remetente':os.environ.get('FOCO_EMAIL_REMETENTE') or config.get('remetente')}

    def limitar(acao,valor,maximo,segundos=900):
        key=digest(acao+':'+valor);window=(int(time.time())//segundos)*segundos
        with db.conectar() as c:
            c.execute('DELETE FROM acesso_limites WHERE janela<?',(int(time.time())-7200,))
            c.execute('INSERT INTO acesso_limites VALUES (?,?,1) ON CONFLICT(chave) DO UPDATE SET total=CASE WHEN janela=excluded.janela THEN total+1 ELSE 1 END, janela=excluded.janela',(key,window))
            total=c.execute('SELECT total FROM acesso_limites WHERE chave=?',(key,)).fetchone()[0]
        if total>maximo:abort(429,'Muitas tentativas. Aguarde alguns minutos e tente novamente.')

    def limite(acao,valor=''):
        limitar(acao+':ip',request.remote_addr or 'local',20)
        if valor:limitar(acao+':conta',valor,5)

    def novo_codigo():return secrets.token_hex(16).upper()

    @app.before_request
    def verificar_versao():
        if g.usuario:
            with db.conectar() as c:
                row=c.execute('SELECT versao FROM acesso_seguranca WHERE usuario_id=?',(g.usuario['id'],)).fetchone()
            if session.get('auth_version',0)!=(row['versao'] if row else 0):
                session.clear();g.usuario=None
                return redirect(url_for('login'))
        if request.endpoint=='login' and request.method=='POST':limite('login',email())

    @app.route('/criar-conta',methods=['GET','POST'])
    def cadastro():
        if g.usuario:return redirect(url_for('home'))
        if request.method=='POST':
            limite('cadastro',email())
            nome=request.form.get('nome','').strip()
            if not 1<=len(nome)<=100 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email()):
                flash('Informe seu nome e um e-mail válido.','erro')
            elif not senha_valida():flash('Use de 10 a 256 caracteres e confirme a mesma senha.','erro')
            else:
                codigo=novo_codigo()
                try:
                    with db.conectar() as c:
                        uid=c.execute('INSERT INTO usuarios(nome,email,senha_hash,criado_em) VALUES (?,?,?,?)',(nome,email(),generate_password_hash(request.form['senha']),db.agora())).lastrowid
                        c.execute('INSERT INTO acesso_seguranca(usuario_id,codigo_hash) VALUES (?,?)',(uid,digest(codigo)))
                        c.executemany('INSERT INTO categorias(usuario_id,nome,cor) VALUES (?,?,?)',[(uid,'Estudos','#0035A3'),(uid,'Pessoal','#0E7C86')])
                except sqlite3.IntegrityError:
                    flash('Não foi possível cadastrar. Se você já tem conta, entre ou recupere a senha.','erro')
                else:
                    session.clear();session['usuario_id']=uid;session['csrf']=secrets.token_hex(32);session['auth_version']=0
                    g.usuario=db.usuario(uid)
                    return render_template('codigo_seguranca.html',codigo=codigo)
        return render_template('acesso.html',modo='cadastro')

    @app.route('/recuperar-senha',methods=['GET','POST'])
    def recuperar():
        config=configurar_email();disponivel=bool(config['api_key'] and config['remetente'])
        if request.method=='POST':
            limite('recuperar',email())
            if not disponivel:flash('Use seu código de segurança na opção abaixo.','erro')
            else:
                with db.conectar() as c:u=c.execute('SELECT id FROM usuarios WHERE email=?',(email(),)).fetchone()
                if u:
                    token=novo_codigo();token_hash=digest(token)
                    with db.conectar() as c:
                        c.execute('DELETE FROM recuperacoes WHERE usuario_id=? OR expira<?',(u['id'],int(time.time())))
                        c.execute('INSERT INTO recuperacoes VALUES (?,?,?)',(token_hash,u['id'],int(time.time())+1200))
                    payload={'personalizations':[{'to':[{'email':email()}]}],'from':{'email':config['remetente']},'subject':'Foco — recuperar senha','content':[{'type':'text/plain','value':f'Seu código de recuperação do Foco é:\n\n{token}\n\nEle vale por 20 minutos e só pode ser usado uma vez. Abra o site Foco, clique em Esqueci minha senha e depois em Já recebi um código por e-mail. Se não solicitou, ignore esta mensagem.'}]}
                    try:
                        req=urllib.request.Request('https://api.sendgrid.com/v3/mail/send',data=json.dumps(payload).encode(),headers={'Authorization':'Bearer '+config['api_key'],'Content-Type':'application/json'},method='POST')
                        with urllib.request.urlopen(req,timeout=15) as response:
                            if response.status!=202:raise ValueError('Envio recusado')
                    except Exception:
                        with db.conectar() as c:c.execute('DELETE FROM recuperacoes WHERE token_hash=?',(token_hash,))
                        app.logger.warning('Envio de recuperação indisponível; verifique a configuração do remetente.')
                flash('Se houver uma conta com esse e-mail e o envio estiver disponível, você receberá um código. Confira também o spam.','sucesso')
        return render_template('acesso.html',modo='recuperar',email_disponivel=disponivel)

    @app.route('/redefinir-senha',methods=['GET','POST'])
    def redefinir():
        metodo=request.values.get('metodo','seguranca')
        metodo='email' if metodo=='email' else 'seguranca'
        if request.method=='POST':
            limite('redefinir',email())
            if not senha_valida():flash('Use de 10 a 256 caracteres e confirme a mesma senha.','erro')
            else:
                codigo=re.sub(r'[\s-]','',request.form.get('codigo','')).upper()[:200]
                novo_hash=generate_password_hash(request.form['senha']);ok=False
                with db.conectar() as c:
                    c.execute('BEGIN IMMEDIATE')
                    u=c.execute('SELECT id FROM usuarios WHERE email=?',(email(),)).fetchone()
                    if u:
                        if metodo=='email':
                            row=c.execute('SELECT 1 FROM recuperacoes WHERE usuario_id=? AND token_hash=? AND expira>?',(u['id'],digest(codigo),int(time.time()))).fetchone()
                        else:
                            row=c.execute('SELECT 1 FROM acesso_seguranca WHERE usuario_id=? AND codigo_hash=?',(u['id'],digest(codigo))).fetchone()
                        if row:
                            c.execute('UPDATE usuarios SET senha_hash=? WHERE id=?',(novo_hash,u['id']))
                            c.execute('INSERT INTO acesso_seguranca(usuario_id,versao) VALUES (?,1) ON CONFLICT(usuario_id) DO UPDATE SET versao=versao+1,codigo_hash=NULL',(u['id'],))
                            c.execute('DELETE FROM recuperacoes WHERE usuario_id=?',(u['id'],));ok=True
                if ok:
                    session.clear();flash('Senha redefinida. Entre com a nova senha e gere outro código em Minha conta.','sucesso')
                    return redirect(url_for('login'))
                flash('E-mail ou código inválido, expirado ou já utilizado.','erro')
        return render_template('acesso.html',modo='redefinir',metodo=metodo)

    @app.post('/conta/codigo-seguranca')
    def codigo_seguranca():
        if not g.usuario:return redirect(url_for('login'))
        limite('codigo',str(g.usuario['id']))
        if not check_password_hash(g.usuario['senha_hash'],request.form.get('senha','')):
            flash('A senha atual não confere.','erro');return redirect(url_for('conta'))
        codigo=novo_codigo()
        with db.conectar() as c:c.execute('INSERT INTO acesso_seguranca(usuario_id,codigo_hash) VALUES (?,?) ON CONFLICT(usuario_id) DO UPDATE SET codigo_hash=excluded.codigo_hash',(g.usuario['id'],digest(codigo)))
        return render_template('codigo_seguranca.html',codigo=codigo)

    @app.errorhandler(429)
    def excesso(e):return render_template('erro.html',erro=e),429
