# Foco — gerenciador de tarefas

Aplicação Flask + SQLite para organizar estudos e tarefas pessoais. Cada conta possui suas tarefas e categorias.

## Executar no Windows

Dentro de focoapp:

```powershell
py -3.13 -m venv .venv313
.\.venv313\Scripts\python.exe -m pip --isolated install --timeout 180 --retries 10 --no-cache-dir --index-url https://pypi.org/simple -r requirements.txt
.\.venv313\Scripts\python.exe app.py
```

Abra http://127.0.0.1:5000 e clique em Criar conta. Guarde o código de segurança mostrado no cadastro. Nos próximos acessos, execute somente o comando de app.py. O script criar_admin.py também permite criar contas pelo console.

## Funcionalidades

- Cadastro, login, logout e troca de senha.
- Tarefas com descrição, prazo, categoria, prioridade e status.
- Criar, editar, concluir, reabrir e excluir tarefas.
- Todas as tarefas é a visualização inicial; concluídas aparecem riscadas ao final.
- Busca, filtros combináveis, ordenação e exportação CSV.
- Contadores de tarefas abertas, em andamento, para hoje, atrasadas e concluídas.
- Categorias e interface responsiva com fontes locais.
- Recuperação por código de segurança de uso único.
- Recuperação por e-mail opcional via SendGrid, com configuração própria.

O cadastro não verifica a posse do endereço de e-mail. Sem configuração do SendGrid, a recuperação funciona com o código de segurança. Contas antigas podem gerar um código em Minha conta, confirmando a senha atual.

## Banco e segurança

O banco todo.db e a chave .secret_key são gerados junto a app.py. Não devem ser enviados ao GitHub. Cada instalação usa seu próprio banco. TODO_DB_PATH permite configurar outro caminho. Preserve o banco e a chave ao atualizar o servidor.

As senhas são armazenadas como hashes. Há proteção CSRF e isolamento das tarefas por conta. Os códigos de recuperação são protegidos por hash; os enviados por e-mail expiram em 20 minutos. Não coloque email_config.json em static ou no Git.

## Organização

app.py contém as rotas; db.py cuida do SQLite; acesso.py implementa cadastro e recuperação. templates contém as telas e static contém CSS, JavaScript, fontes e imagens. static/fotos é somente uma convenção, sem upload de fotos nesta aplicação.

## Manutenção

```bash
python diagnostico.py
python backup.py
python -m flask --app app redefinir-senha
```

O último comando é exclusivo do responsável com acesso ao console e solicita e-mail e nova senha. Use o Python do ambiente virtual. Para hospedagem e e-mail, leia DEPLOY.md.

## Trabalho da equipe

O código-base foi recebido em um pacote existente. A equipe fará importação progressiva, revisão, integração e validação nos dias 17, 18 e 19/10/2026. Registre responsáveis, testes efetivamente executados e contribuições no README da raiz e nos PRs. Não atribua ao cronograma a criação original do código.
