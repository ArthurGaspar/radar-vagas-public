# radar-de-vagas

Monitora os sites de vagas (ATS) de empresas-alvo e portais de emprego **de hora
em hora** e avisa no Discord quando surge uma vaga nova compatível com o perfil,
com um **score de compatibilidade 0–100%** entre a vaga e o currículo, calculado
sem IA, no estilo de um ATS.

A motivação: quem se candidata nas primeiras horas de uma vaga tem muito mais
chance de ser visto. Com score alto, dá para mandar o currículo como está; com
score menor, a notificação já lista o que a vaga pede e o currículo não tem,
para personalizar antes de enviar.

> Este repositório é uma versão de demonstração: currículos, empresas e filtros
> são exemplos fictícios, e o agendamento vem montado, mas desligado.

```
a cada hora (GitHub Actions ou Agendador do Windows)
  └─ coleta   10 ATS × empresas do YAML  +  busca por termo em 4 portais
  └─ novas    só o que não estava no estado da execução anterior (dedup por id + link)
  └─ filtros  título → nível → localização
  └─ score    termos do dicionário presentes na vaga × presentes no CV (PT ou EN)
  └─ Discord  #alta-compat (≥ 75%) e #personalizar (o resto)
```

## Experimente (offline, sem Discord)

```bash
pip install -r requirements.txt
python -m vagas demo
```

```
Filtros:
  passa                       Fintech Exemplo · Desenvolvedor(a) Backend Júnior - Python
  passa                       Varejo Digital Exemplo · Pessoa Desenvolvedora Full Stack Pleno
  passa                       SaaS Global Exemplo · Software Engineer (Remote, LATAM)
  nível (senior)              Banco Exemplo · Senior Backend Engineer
  local (Presencial fora...)  Consultoria Exemplo · Desenvolvedor Java Júnior
  local (remoto restrito...)  Startup EUA Exemplo · Junior Frontend Engineer
  título                      Indústria Exemplo · Engenheiro Mecânico Júnior
  nível (estagio)             Agência Exemplo · Estágio em Desenvolvimento de Software

Seriam notificadas (3), com o score de compatibilidade:

★ [100%] Fintech Exemplo · Desenvolvedor(a) Backend Júnior - Python
         🟢 Júnior · 🌎 Remoto · Brasil · CV PT
★ [ 93%] SaaS Global Exemplo · Software Engineer (Remote, LATAM)
         ⚪ Não informado · 🌎 Remoto · Remote · CV EN
         faltam: Kubernetes
  [ 50%] Varejo Digital Exemplo · Pessoa Desenvolvedora Full Stack Pleno
         🟡 Pleno · 📍 São Paulo, SP, Brasil · Híbrido · CV PT
         faltam: E-commerce, GraphQL, Kubernetes, Mensageria, Next.js, Terraform
```

Com dados reais (precisa de internet, não precisa de Discord):

```bash
python -m vagas testar quintoandar           # vagas abertas que passariam hoje, com score
python -m vagas testar supabase --todas      # + o motivo de cada descarte
python -m vagas testar greenhouse:stripe     # qualquer empresa, mesmo fora do YAML
```

## Fontes

**ATS por empresa** (lista em `config/empresas.yaml`):

| ATS | Como lê | Slug de exemplo |
|---|---|---|
| Greenhouse | API pública | `quintoandar` |
| Lever | API pública | `ciandt` |
| Ashby | API pública | `supabase` |
| Workday | endpoint do próprio site de vagas | `nvidia.wd5/NVIDIAExternalCareerSite` |
| SmartRecruiters | API pública | `ServiceNow` |
| Workable | API do widget | `huggingface` |
| Teamtailor | feed RSS (aceita domínio próprio) | `empresa` ou `careers.empresa.com` |
| Recruitee | API pública (aceita domínio próprio) | `empresa` ou `jobs.empresa.com` |
| Gupy | JSON embutido na página (Next.js) | `creditas` |
| InHire | API pública das páginas de carreira | `empresa` |

**Portais com busca por termo** (listas em `config/filtros.yaml`), que cobrem
empresas fora do YAML:

| Portal | Cobertura |
|---|---|
| Gupy (portal) | todas as empresas brasileiras que usam Gupy |
| Get on Board | tecnologia em LATAM, usando os países realmente aceitos de cada vaga |
| Remotar | vagas remotas abertas a quem está no Brasil |
| Himalayas | remotas do mundo todo, só as que aceitam o Brasil ou são globais |

LinkedIn, Indeed e afins ficaram de fora de propósito: não têm API pública e
proíbem scraping nos termos de uso.

Para adicionar uma empresa, basta o link de qualquer vaga dela:

```bash
python -m vagas add https://jobs.ashbyhq.com/empresa/123 --nome "Empresa" --estagio
```

O comando identifica ATS e slug (inclusive em domínios próprios de Recruitee e
Teamtailor), confere se a API responde e acrescenta a linha no YAML sem apagar
os comentários.

## Como o score funciona

Sem IA, com a mesma ideia de um ATS simples:

1. Detecta o idioma da vaga (PT/EN/ES) e escolhe `cv_pt.md` ou `cv_en.md`.
2. Procura na vaga os termos de `config/skills.yaml`, unificando sinônimos
   (`k8s` = `kubernetes`, `nodejs` = `node.js`).
3. Pesa cada termo pela seção onde aparece: título **1.5** · requisitos **1.0** ·
   diferenciais ("nice to have", "desejável") **0.5** · benefícios **0**.
4. Score = peso dos termos presentes no CV ÷ peso total.

Termos fora do dicionário não contam. Com menos de 4 termos reconhecidos, a
notificação avisa que o score é pouco confiável.

## Decisões que deram trabalho

**Nível pelo título.** A ordem de checagem resolve ambiguidades:
`Júnior/Pleno` vira júnior, `Pleno/Sênior` vira pleno e `Associate Director`
vira sênior. Os casos que pegaram de surpresa viraram teste:
- `JR-186652 Full Stack Developer Senior`: "JR-xxxx" é código de requisição do
  Workday, não "júnior", e é ignorado.
- `Empresa I Engenheiro de Dados Sênior I Remoto`: o "I" é separador, não nível.
  Por isso os numerais (I, II, III) são o sinal mais fraco e só valem se nenhuma
  palavra de nível aparecer.
- `Staff+ Software Engineer`: a fronteira de palavra que trata `+` como parte do
  termo (para `C++` não casar com `C`) vale só no dicionário de skills, não nos
  filtros.

**Localização.** A região vem do campo de local e dos trechos entre parênteses
do título. O título inteiro não entra, senão "Global Payments" faria uma vaga em
Tóquio passar como "global". Para presencial, usa a cidade estruturada quando o
ATS a informa ("Campinas, São Paulo" não vira a capital).

**Mesma vaga em várias fontes.** A Remotar, por exemplo, reposta vagas da Gupy e
do Ashby. A deduplicação usa o id do ATS e o **link canônico de candidatura**
(decodificando inclusive o link base64 da Gupy), nunca o título: empresas
diferentes com o mesmo título, ou a mesma empresa com duas posições iguais,
continuam sendo vagas diferentes. Se um link se repete dentro da mesma fonte
(uma página genérica de carreiras), ele não vira chave.

**Pausas.** O radar compara com o estado salvo, não com "a última hora". A
primeira execução do dia notifica o que surgiu de madrugada e lê 3 páginas por
termo nos portais, que só devolvem as N vagas mais recentes. Depois de uma pausa
inesperada (PC desligado), o acumulado é registrado **sem notificar**: vaga que
surgiu com o radar parado já perdeu a vantagem de chegar cedo.

**Ser um bom cliente das APIs.** As empresas Workday dividem o mesmo domínio e
o limite de pedidos parece valer por IP, então todas passam por uma fila única,
com pausa e espera crescente em caso de 429. O Workday ordena por data, e a
paginação para na primeira página sem vagas de hoje/ontem (de 106 s para 7 s
numa empresa com 1.500 vagas). Os portais de busca rodam em sequência, com
pausa entre os pedidos.

**Erros sem ruído.** Uma falha isolada (um 429, um timeout) se resolve na hora
seguinte. O canal `#logs` só é avisado quando a mesma fonte falha 3 execuções
seguidas, com mensagens curtas e quebradas no limite de caracteres do Discord.

## Configuração

| Arquivo | O que é |
|---|---|
| `config/empresas.yaml` | empresas monitoradas (`estagio: true` libera estágios daquela empresa) |
| `config/filtros.yaml` | termos de título, níveis, regras de local, buscas nos portais, faixas de score |
| `config/skills.yaml` | dicionário de termos técnicos com sinônimos, usado no score |
| `curriculo/cv_pt.md`, `cv_en.md` | currículo em texto puro (os do repositório são fictícios) |

## Rodando de verdade

1. **Discord:** crie um servidor com os canais `#alta-compat` e `#personalizar`
   (opcional: `#logs`) e um webhook em cada.
2. Copie `.env.example` para `.env` e cole os webhooks.
3. Escolha como agendar:
   - **Agendador de Tarefas do Windows:** `powershell -ExecutionPolicy Bypass -File scripts\instalar_tarefa.ps1`.
     Roda das 06:17 às 23:17, sem abrir janela, com log em `logs/radar.log`.
   - **GitHub Actions:** siga as instruções no topo de `.github/workflows/radar.yml`.
     Vem desligado neste repositório. Use um fork **privado**, já que ele terá o seu currículo.
4. A primeira execução só registra as vagas existentes; a partir da segunda,
   chegam só as novas.

```bash
python -m vagas run --dry-run      # imprime no terminal, não notifica nem salva
python -m vagas run                # execução real
python -m vagas run --silencioso   # registra as novas sem notificar (descarta acumulado)
python -m pytest                   # 95 testes
```

## Estrutura

```
vagas/
├── fontes/        um adaptador por ATS/portal, todos devolvem o mesmo modelo de Vaga
├── filtros.py     título, nível e localização
├── match.py       score de compatibilidade
├── dedup.py       chave canônica do link de candidatura
├── radar.py       orquestra uma execução: coleta → novas → filtros → score → Discord
├── estado.py      vagas já vistas, falhas seguidas, horário da última execução
├── discord.py     webhooks, lotes dentro dos limites do Discord
└── adicionar.py   `add <url>`: descobre ATS e slug a partir de um link
config/            empresas, filtros e dicionário de skills
curriculo/         currículos fictícios de exemplo
exemplos/          vagas fictícias usadas por `python -m vagas demo`
scripts/           agendamento no Windows
tests/             pytest
```
