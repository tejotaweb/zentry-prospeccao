# Zentry · prospecção de sites

Painel para web designer achar empresas que precisam de site, montar uma **prévia do site de cada uma** e preparar a abordagem pelo WhatsApp.

O fluxo:

1. **Pesquisa:** busca empresas no Google Maps (nicho + bairro) pelo Outscraper.
2. **Filtro:** confere nota, avaliações, site (abre, mede a velocidade, dá uma nota), Instagram, WhatsApp e se é rede ou franquia. Tudo **sem IA**, por código.
3. **Prévia:** para cada empresa aprovada, monta um site de exemplo a partir de um modelo pronto. Usa as fotos reais do Google, a copy do nicho e os dados da empresa.
4. **Ajuste:** editor visual no próprio painel, estilo Figma.
5. **Publicação:** a prévia aprovada vira um link.
6. **Mensagens:** textos prontos para mandar no WhatsApp, com a etiqueta de cada conversa.
7. **Contas:** cadastro aberto (e-mail/senha ou Google) com liberação pelo administrador, espaço separado por conta e créditos para as pesquisas.

> Este repositório é uma **cópia de referência**: tem só o código e os materiais de método. Não tem dados de empresas, contas, senhas nem chaves.

---

## Requisitos

- **macOS.** Duas partes usam ferramentas do Mac: o `sips`, que lê as cores das fotos, e o Vision (`previa/rosto.swift`), que acha rostos e texto nas fotos. Em Linux, o resto roda, mas essas duas precisam de substituto (ex.: Pillow e OpenCV).
- **Python 3.11+**. Só biblioteca padrão; o `certifi` é recomendado.
- **Node 18+**, só para o Lighthouse (teste de velocidade do site).
- **Google Chrome** em `/Applications`, usado para o print do site e pelo Lighthouse.
- **Xcode Command Line Tools** (`xcode-select --install`), para compilar o detector de rosto.
- Uma chave do **Outscraper**: outscraper.com, 500 empresas grátis por mês.

## Instalação

```bash
git clone <este repositório> zentry && cd zentry
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
npm install                                   # instala o Lighthouse em node_modules/
mkdir -p previa/bin && swiftc -O previa/rosto.swift -o previa/bin/rosto
mkdir -p dados
```

## Rodar

```bash
.venv/bin/python painel/servidor.py
```

Abra `http://localhost:4400`. No Mac, o painel abre direto, sem login. O login só vale para quem chega pela internet; veja "Colocar no ar".

Primeiros passos no painel:
1. Em **Meu perfil**, coloque o seu nome, a sua cidade e o seu site. Eles aparecem nas prévias e nas mensagens.
2. Em **Configurações**, cole a chave do Outscraper.
3. Em **Pesquisa**, escolha nicho, bairro e quantidade.

## Variáveis de ambiente (opcionais)

| Variável | Para que serve | Padrão |
|---|---|---|
| `PROSPECCAO_PORTA` | porta do painel | `4400` |
| `PROSPECCAO_DADOS` | pasta dos dados | `./dados` |
| `PROSPECCAO_ENDERECO` | endereço público (links das prévias, e-mails, login com Google) | `http://localhost:4400` |
| `PROSPECCAO_SITE_PASTA` | repositório do seu site, onde as prévias aprovadas são publicadas em `/p/` | `~/meu-site` |
| `PROSPECCAO_SITE_DOMINIO` | domínio desse site | `https://seusite.com.br` |
| `PROSPECCAO_LIMITE_OUTSCRAPER` | trava de empresas por mês (para não cobrar) | `500` |

## Colocar no ar (opcional)

O jeito usado no projeto original foi o túnel da Cloudflare (`cloudflared`), com o domínio na Cloudflare:

```bash
brew install cloudflared
cloudflared tunnel login
cloudflared tunnel create zentry
cloudflared tunnel route dns zentry painel.seudominio.com.br
```

Depois crie `~/.cloudflared/config.yml` apontando o hostname para `http://localhost:4400` e rode `cloudflared tunnel run zentry`. Para ligar junto com o Mac, use dois LaunchAgents (`~/Library/LaunchAgents`): um para o painel e outro para o túnel.

Pela internet:
- tudo exige login;
- a conta de administrador só pode ser criada no próprio Mac, em `localhost:4400/criar-senha`;
- as outras pessoas se cadastram em `/cadastro` e esperam a liberação na tela **Usuários**.

## Estrutura

```
painel/        servidor e tela do painel
  servidor.py      servidor HTTP (biblioteca padrão), rotas, fila de prévias, publicação
  index.html       o painel inteiro (JS puro, sem build)
  estilo.css       estilos do painel
  login.html       entrar, criar conta, conta de administrador, espera
  seguranca.py     contas, senhas (PBKDF2), sessões, créditos
  contas_web.py    e-mail (Gmail SMTP) e login com Google (OAuth)
  espacos.py       um processo e uma pasta por conta (espaço separado)
  analise_local.py análise das empresas sem IA (site, Instagram, WhatsApp, rede)
  ia.py            chamadas ao Claude Code (opcional; o padrão é sem IA)
previa/        gerador das prévias
  preencher.py     monta a prévia a partir de um modelo + dados da empresa
  modelos/         8 modelos de página (A a H) + base.css + base.js
  nichos.py        textos-base por nicho (dentista, advogado, nutri...)
  nichos_extra.py  mais nichos (contabilidade, arquitetura, personal...)
  fotos.py         fotos do Google (Outscraper) e do site atual
  rosto.swift      detector de rosto e texto (Vision do Mac)
metodo/        regras de qualidade das prévias e referências visuais
scripts/       utilitários antigos (lista pela base de CNPJ)
dados/         (não vai para o Git) tudo o que o painel grava
```

Leia o **CLAUDE.md** antes de mexer: ele explica as decisões e as regras do projeto.
