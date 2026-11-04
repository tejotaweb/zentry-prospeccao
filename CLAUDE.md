# CLAUDE.md · Zentry (guia técnico)

Guia para o Claude (ou quem for mexer) entender o projeto. O README explica como instalar e rodar.

Responda e escreva no código em **português simples**: nomes de funções, variáveis e comentários já são em português.

---

## 1. Princípios do projeto

- **A automação não gasta token.** Pesquisa, análise, prévia, copy, fotos e publicação rodam por código. O Claude (`painel/ia.py`, via `claude -p`) é opcional, e cada recurso que o usa tem uma chave em `config.json` (`analise_modo`, `copy_propria`, `previa_modo`). O padrão é sempre `"sem-ia"`/`"modelo"`.
- **Nada é inventado na prévia.** Número, depoimento, prêmio ou ano de experiência que não veio dos dados fica de fora ou aparece marcado `[CONFIRMAR]` (amarelo). Em saúde e advocacia valem as regras dos conselhos: sem promessa de resultado, sem preço, sem antes e depois.
- **Nada é enviado sozinho.** O painel monta as mensagens; quem aperta enviar no WhatsApp é a pessoa. Isso evita bloqueio da conta.
- **Mexa só no que foi pedido.** O dono do projeto edita prévias à mão. Antes de remontar uma prévia, veja se há edição (`versoes/`, `ajustes.json`); toda remontagem guarda a versão anterior em `versoes/`.

## 2. Como as peças conversam

```
navegador ──► painel/servidor.py (porta 4400)
                ├─ login e contas (seguranca.py) ── só para quem vem da internet
                ├─ admin: atende direto, com a pasta dados/
                └─ outra conta: repassa para o processo dela (espacos.py, porta 4501+, pasta dados/contas/<id>/)
```

- **Local x internet:** pedido sem os cabeçalhos da Cloudflare (`Cf-Connecting-Ip`/`Cf-Ray`) é tratado como "no próprio Mac" e entra sem login. É assim que o dono (e o Claude dele) altera o sistema. Pela internet tudo exige sessão. Ver `Painel.remoto()`, `liberado()`, `barrar()`.
- **Espaço por conta:** o mesmo `servidor.py` roda de novo com `PROSPECCAO_CONTA`, `PROSPECCAO_DADOS` e `PROSPECCAO_PORTA`. Nesse modo:
  - rotas de administrador ficam bloqueadas (`SO_ADMIN`);
  - nada usa o Claude (`config()` força `sem-ia`);
  - a prévia aprovada vira o link público `/v/<conta>/<empresa>/`, servido sem login só se existir `publicado.json`.
- **Créditos:** 1 crédito = 1 empresa pesquisada.
  - O painel principal cobra antes de repassar `/api/ia/buscar` e devolve o crédito se a pesquisa não começar (`busca_com_credito`).
  - O admin dá créditos na tela Usuários.
  - Chave e contador do Outscraper são os do admin; a pasta da conta tem links simbólicos para eles.
- **Erros explicados** saem com código **422**, nunca 502: a Cloudflare troca 502 pela página dela e a mensagem some.

## 3. Pesquisa e análise (sem IA)

`executar_busca` → `achar_no_maps` (Outscraper `google-maps-search`) → `checar_sites` (abre o site, detecta domínio vencido, data do site) → `analisar_sem_ia` (`analise_local.py`):
- **site:** Lighthouse para a velocidade no celular e uma nota de 0 a 10 por sinais do código (celular, tecnologia antiga, construtor pronto, botão de WhatsApp, título, texto);
- **Instagram e WhatsApp:** só o que a empresa divulga (campo site do Google, site, página de contato, Linktree e o Emails & Contacts do Outscraper, que tem 500 sites grátis por mês). Sem achar, o WhatsApp vira o celular do Google;
- **rede ou franquia:** lista de redes conhecidas, texto do site e o mesmo nome em vários endereços.

**Não** raspe buscador (Bing, DuckDuckGo, Google) nem a API interna do Instagram: é contornar proteção contra robôs. A Busca do Google do Outscraper foi testada e não acha Instagram; fica desligada (`limite_busca_google: 0`).

`motivos_descarte` decide quem sai: nota, avaliações, site bom, rede, já é cliente, já está na lista. "Sem Instagram" não descarta na análise sem IA, porque não achar não quer dizer que não tenha.

## 4. Prévia (previa/preencher.py)

- `Dados` lê `maps.json`, `fotos.json`, `copy.json` (opcional) e `texto-site.txt`. Descobre o nicho (`nichos.py` + `nichos_extra.py`), a cidade pelo endereço e o conselho com a UF.
- **Copy própria sem IA** (`_copy_dos_fatos`):
  - títulos curtos do nicho (até 42 letras; título longo ganha letra menor para caber em 2 linhas);
  - texto de apoio com serviços reais, bairro, cidade e horário;
  - dúvidas com horário e acessibilidade do Google.
  Nos textos dos nichos, "Goiânia" é só um marcador: ele é trocado pela cidade da empresa.
- **Fotos:**
  - Na leitura, `tom_de_pele` mede a cor e `achar_rostos` (binário `previa/bin/rosto`, Vision do Mac) acha rostos e texto. O resultado fica guardado em `fotos.json`.
  - Fica de fora: em saúde e estética, foto de procedimento e de antes e depois (40% ou mais de tom de pele); close cortado; post ou panfleto com 5% ou mais de texto.
  - Cada foto cortada centraliza no rosto (`object-position`). O enquadramento escolhido no editor é salvo em `foco` e vale nas próximas montagens.
- **Modelos:** `RECEITAS` A a H. O padrão é **B** (`MODELO_PADRAO`); os outros entram por "Trocar modelo" ou quando há poucas fotos. Cada modelo é um HTML com `{{marcadores}}`, `<meta name="ordem">` (as seções em ordem) e `<meta name="fonte">`. As seções são métodos `secao_*` do `Montador`.
- Toda prévia diz que é "site de exemplo", leva `noindex` e é assinada com o nome do perfil (`autor()`).

## 5. Painel (painel/index.html)

Um arquivo só, em JS puro, renderizado por `desenhar()`, com as telas em `TELAS`. Os cliques passam por um único `addEventListener('click')` que usa `closest([data-…])`; para um atributo novo, acrescente-o nessa lista ou use `onclick`.
- **Editor visual da prévia:** iframe com os scripts desligados. Larguras são gravadas em `vw` sobre a base de 1440 px. Salvar regrava o `index.html` e republica, se a prévia já tiver link.
- **Tela Usuários** (só admin): liberar, recusar, bloquear e dar créditos; configura o e-mail (senha de app do Gmail) e o Google OAuth. As chaves ficam em `dados/chaves/` com permissão 600.

## 6. Segurança (não afrouxar)

- Senha: PBKDF2-SHA256 com 310 mil voltas. Sessão: token aleatório em cookie HttpOnly, Secure e SameSite=Lax; no arquivo fica só o hash.
- 5 logins errados ou 5 cadastros em 15 minutos bloqueiam o IP.
- POST vindo da internet só com `Origin` do próprio painel, e o corpo precisa ser JSON.
- A conta de administrador só é criada no próprio Mac. Cadastro novo nasce `pendente`.
- `/api/estado` recusa gravação que apagaria mais da metade dos dados e guarda cópia por hora em `dados/copias-estado/`. **Nunca teste rota que grava com dados de mentira.**

## 7. Dados (dados/, fora do Git)

Os principais arquivos:
- `estado.json`: etiquetas, aprovações e conversas;
- `leads-manuais.json`: empresas aprovadas;
- `previas/<id>/`: cada prévia, com `index.html`, `img/`, `fotos.json`, `maps.json`, `publicado.json` e `versoes/`;
- `fila-previas.json`, `config.json`, `usuarios.json`, `sessoes.json`;
- `chaves/` e `chave-outscraper.txt`;
- `contas/<id>/`: o espaço de cada conta;
- `logs/`.

## 8. Rodar e testar

- `.venv/bin/python painel/servidor.py`. Se o painel estiver rodando como LaunchAgent, reinicie com `launchctl kickstart -k gui/$(id -u)/<label>`.
- Antes de reiniciar, confira que nenhum `claude -p` está rodando: reiniciar mata o trabalho no meio.
- Testes pela internet com `curl` usam o domínio público. Para simular um acesso de fora no Mac, mande `Cf-Connecting-Ip` e `Host`.
