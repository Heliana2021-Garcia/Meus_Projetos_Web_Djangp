# SIGEST - Sistema de Gestão de Estágios e Inserção Profissional

Aplicação web do **INSTIC** (Universidade de Luanda) para gerir o ciclo completo dos estágios dos
estudantes: registo e validação, oportunidades, candidaturas e selecção, estágio, avaliação,
conclusão e certificado. Projecto de fim de curso.

## Tecnologias

Python, Django, MySQL, HTML5, CSS3, Bootstrap 5 e JavaScript (tudo servido localmente, sem CDN).
Sem HTMX, Tailwind nem inteligência artificial.

## Perfis

| Perfil | O que faz |
|---|---|
| Estudante | Regista-se com documentos, candidata-se, acompanha as fases, preenche o diário e os relatórios, confirma o início e faz a sua avaliação. |
| Empresa | Publica vagas, conduz a selecção (Kanban), atribui o orientador, confirma o início, avalia, interrompe e regista a efectivação. |
| Orientador empresarial | Acompanha os seus estagiários, valida o diário e os relatórios e avalia. |
| Coordenador institucional | Valida estudantes, empresas e vagas, monitoriza e interrompe estágios, avalia, valida a conclusão e consulta relatórios e decisões. |

O administrador técnico acede ao painel de administração e às páginas de gestão, sem substituir os intervenientes.

## Instalação

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements/base.txt
```

1. Crie a base de dados MySQL e um utilizador com permissões sobre ela e sobre `test_<nome>`
   (necessário para correr os testes).
2. Crie o ficheiro `.env` na raiz (nunca é publicado) com as variáveis lidas em
   `config/settings/base.py`; a base de dados é definida por
   `DATABASE_URL=mysql://utilizador:palavra-passe@127.0.0.1:3306/sigest?charset=utf8mb4`.
   Sem `DATABASE_URL`, usa-se SQLite (apenas para desenvolvimento).
3. Aplique as migrações e crie os dados iniciais:

```powershell
python manage.py migrate
python scripts\criar_cursos.py
python scripts\criar_tecnologias.py
python scripts\criar_coordenador.py
python manage.py runserver
```

## Testes e verificações

```powershell
python manage.py check
python scripts\verificar_templates.py
python manage.py test
```

## Estrutura

- `apps/contas` - utilizadores, perfis e controlo de acesso por perfil
- `apps/estudantes` - perfil académico, documentos e validação do registo
- `apps/empresas` - empresas e orientadores empresariais
- `apps/vagas` - oportunidades e fases de selecção configuráveis
- `apps/candidaturas` - candidaturas, estágio, diário, relatórios, avaliação, conclusão e certificado
- `apps/relatorios` - painel da coordenação, relatórios de gestão (CSV e PDF) e registo de decisões
- `apps/core` - notificações, auditoria e utilitários
- `templates/`, `static/` - interface (Bootstrap local) e identidade visual do INSTIC
- `docs/DER.md` - diagrama entidade-relação (gerado por `scripts/gerar_der.py`)

## Regras principais

- Candidatura apenas com registo validado, 3.º ano ou superior e média mínima; um estudante não tem dois estágios activos.
- Fases de selecção definidas por vaga; só se avança com resultado favorável na fase anterior.
- O orientador pertence à empresa de acolhimento e tem um limite de estágios activos (`MAX_ESTAGIOS_POR_ORIENTADOR`).
- O estágio só começa com o orientador atribuído e a confirmação da empresa e do estudante.
- A nota final é a média pesada das 4 avaliações (`PESOS_AVALIACAO`: empresa 30%, orientador 30%, estudante 10%, coordenação 30%).
- A conclusão exige as avaliações, o relatório final e o diário validados, e é validada pela coordenação.
- O certificado só existe depois da conclusão.

## Segurança

Permissões verificadas no servidor em todas as vistas, CSRF, validação do tipo, tamanho e conteúdo dos
ficheiros, documentos privados servidos apenas a quem tem direito, transacções nas operações críticas e
registo das decisões (quem, o quê, quando). Em produção: HTTPS, `DEBUG=False`, segredos fora do código
e cópias de segurança periódicas da base de dados e da pasta `privado/`.

## Limites da primeira versão

Sem inteligência artificial, microserviços, assinatura digital ou integrações externas. Os documentos
finais são gerados em PDF para assinatura manual.

## Cópias de segurança

`.\scripts\backup.ps1` grava a base de dados (`mysqldump`) e a pasta `privado/` (documentos dos
utilizadores) na pasta `backups/`. Convém executá-lo periodicamente (por exemplo, com o Agendador de
Tarefas do Windows) e guardar as cópias fora da máquina.
