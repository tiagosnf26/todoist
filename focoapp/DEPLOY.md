# Foco no PythonAnywhere

## Atualizar a instalação existente

Não apague focoapp, todo.db, .secret_key, email_config.json nem seu ambiente virtual.
Antes de atualizar, ative seu ambiente virtual existente e faça um backup consistente:

```bash
cd ~/focoapp
python backup.py
```

Use o Python do ambiente virtual correto; o nome desse ambiente depende da sua instalação. O código está em PROJETO_COMPLETO/focoapp dentro do kit. Faça upload somente dos arquivos dessa pasta para a pasta focoapp existente, preservando os arquivos locais de dados. Não envie a árvore de IMPORTACOES para produção. Após concluir todos os arquivos, Web > Reload; no navegador, Ctrl+F5. Não atualize produção com etapas incompletas.

## Nova instalação

1. Coloque a pasta focoapp em /home/SEU_USUARIO/focoapp.
2. Na aba Web escolha Manual configuration e uma versão Python disponível na conta.
3. Crie um ambiente virtual com a mesma versão. Exemplo, apenas se Python 3.10 estiver disponível:

```bash
mkvirtualenv --python=/usr/bin/python3.10 foco-env
cd ~/focoapp
python -m pip install -r requirements.txt
```

4. Em Source code e Working directory, informe /home/SEU_USUARIO/focoapp.
5. Em Virtualenv, informe o caminho real do ambiente, como /home/SEU_USUARIO/.virtualenvs/foco-env.
6. Abra o arquivo WSGI indicado na aba Web e use o exemplo de wsgi.py, trocando SEU_USUARIO pelo login real. Enviar apenas o arquivo de exemplo ao projeto não configura o servidor.
7. Mapeie /static/ para /home/SEU_USUARIO/focoapp/static/.
8. Clique em Reload. Abra a URL HTTPS da aba Web e use Criar conta.

Não execute python app.py para manter o servidor publicado: o PythonAnywhere usa WSGI. Não mapeie a pasta inteira do projeto como arquivo estático.

## Recuperação de senha

O código de segurança funciona sem serviços externos. Cada pessoa deve guardá-lo ao criar a conta ou gerá-lo em Minha conta. É de uso único. Depois de redefinir a senha, gere outro.

O envio por e-mail é opcional e exige conta SendGrid ativa, remetente verificado e API Key com Mail Send. Confira limites e preços atuais do provedor antes de contratá-lo.

Crie email_config.json ao lado de app.py usando email_config.exemplo.json como modelo:

```json
{"api_key":"SUA_CHAVE_SENDGRID","remetente":"SEU_EMAIL_VERIFICADO"}
```

Não versione esse arquivo. Restrinja a leitura no console:

```bash
chmod 600 ~/focoapp/email_config.json
```

Como alternativa, configure FOCO_SENDGRID_API_KEY e FOCO_EMAIL_REMETENTE antes do import de app no WSGI. Clique em Reload e teste com seu endereço. O provedor precisa aceitar e entregar a mensagem; a API configurada não garante chegada à caixa de entrada.

Sem código e sem e-mail, o responsável pode usar o console, na pasta do projeto e no ambiente virtual:

```bash
python -m flask --app app redefinir-senha
```

## Conferir a publicação

Teste cadastro, login, tarefa, filtros, conclusão, persistência e recuperação. Não declare e-mail como funcionando se não o configurou e testou. O banco da produção permanece no servidor, fora do Git.

Referências: https://help.pythonanywhere.com/pages/Flask/ e https://www.pythonanywhere.com/whitelist/
