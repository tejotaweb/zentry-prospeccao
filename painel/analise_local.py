"""Análise das empresas SEM IA (03/11/2026: ele não quer gastar token na pesquisa).

Faz o que o Claude fazia, só com código e fontes abertas, nesta ordem:
  1. site: abre, mede (Lighthouse já vem de fora) e dá uma nota de 0 a 10 por sinais que dá para conferir no código;
  2. Instagram: o que a própria empresa divulga (campo "site" do Google, site, página de contato, Linktree).
     Sem busca em buscador e sem ler o Instagram por dentro: isso é driblar proteção contra robôs (barrado em 03/11);
  3. WhatsApp: link wa.me no site, no Linktree ou na bio; se não tiver, o celular do Google (marcado como provável);
  4. rede ou franquia: nome de rede conhecida, "seja um franqueado" no site ou o mesmo nome em vários endereços da busca;
  5. análise: 1 ou 2 frases montadas com o que foi achado.
Nada é inventado: o que não foi achado fica vazio.
"""
import json
import re
import ssl
import time
import unicodedata
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from html import unescape

NAVEGADOR = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36",
             "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.6"}
REDES_SOCIAIS = ("instagram.com", "wa.me", "whatsapp.com", "facebook.com", "linktr.ee", "doctoralia", "linkbio", "bio.link", "beacons.ai")
NAO_PERFIL = {"p", "reel", "reels", "explore", "stories", "accounts", "tv", "about", "developer", "legal", "direct", "share", "sharer",
              "web", "instagram", "privacy", "terms", "embed.js", "static", "graphql", "api"}
REDES_CONHECIDAS = (
    "odontocompany", "odonto company", "sorridents", "oral sin", "oralsin", "odontoclinic", "orthodontic", "orthoplus", "sorria",
    "amor saude", "amor saúde", "dr consulta", "dr. consulta", "clinica sim", "clínica sim", "hapvida", "unimed", "sabin", "fleury",
    "a+ medicina", "lavoisier", "dasa", "espaçolaser", "espaco laser", "espaçolaser", "maria jose", "depyl action", "pello menos",
    "contabilizei", "agilize", "bodytech", "smart fit", "smartfit", "selfit", "bluefit", "petz", "cobasi", "petlove",
    "oral unic", "oralunic", "implantodontia brasil", "odonto excellence", "odontoexcellence", "clinicorp", "oral dents",
)
ANTIGO = ("jquery-1.", "jquery/1.", "<table", "<font", "<marquee", "<center", "swfobject", ".swf", "frameset")
CONSTRUTORES = {"wix": ("wix.com", "wixstatic"), "Squarespace": ("squarespace",), "Elementor": ("elementor",),
                "WordPress": ("wp-content",), "Webnode": ("webnode",), "Hostinger": ("zyrosite", "hostinger"), "Weebly": ("weebly",),
                "Google Sites": ("sites.google",), "Site.br/Kangoo": ("kangoo",)}


def _ctx():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


CTX = _ctx()


def baixar(url, dados=None, cabecalhos=None, limite=1_500_000, timeout=15):
    pedido = urllib.request.Request(url, data=dados, headers={**NAVEGADOR, **(cabecalhos or {})})
    with urllib.request.urlopen(pedido, timeout=timeout, context=CTX) as r:
        return r.geturl(), r.read(limite).decode("utf-8", "ignore")


def sem_acento(texto):
    return "".join(c for c in unicodedata.normalize("NFD", str(texto or "").lower()) if unicodedata.category(c) != "Mn")


def palavras_do_nome(nome):
    """Palavras que identificam a empresa (sem Dr., Clínica, de, da...)."""
    vazias = {"dr", "dra", "clinica", "consultorio", "odontologia", "odontologica", "odontologico", "de", "da", "do", "das", "dos", "e",
              "studio", "estudio", "centro", "instituto", "escritorio", "ltda", "me", "eireli", "goiania", "go", "the", "and", "&", "-", "|"}
    return [p for p in re.findall(r"[a-z0-9]+", sem_acento(nome)) if p not in vazias and len(p) > 2]


# ---------- 1. contatos dentro de uma página ----------
def contatos_na_pagina(html):
    html = unescape(html or "")
    instas = []
    for h in re.findall(r"instagram\.com/(?:#!/)?([A-Za-z0-9_.]{2,30})", html, re.I):
        h = h.strip(".").lower()
        if h not in NAO_PERFIL and h not in instas and not h.endswith((".js", ".png", ".jpg")):
            instas.append(h)
    zaps = []
    for n in re.findall(r"(?:wa\.me/|api\.whatsapp\.com/send/?\?phone=|whatsapp\.com/send/?\?phone=|web\.whatsapp\.com/send\?phone=)\+?(\d{10,13})", html, re.I):
        if n not in zaps:
            zaps.append(n)
    links_bio = re.findall(r'href=["\'](https?://(?:linktr\.ee|bio\.link|beacons\.ai|linkbio\.co|link\.bio)/[^"\'#?]+)', html, re.I)
    contato = re.findall(r'href=["\']([^"\']*(?:contato|contact|fale-conosco|agende|agendamento)[^"\']*)["\']', html, re.I)
    return {"instagram": instas, "whatsapp": zaps, "links_bio": links_bio[:2], "contato": contato[:2]}


def formatar_zap(numero):
    n = re.sub(r"\D", "", str(numero or ""))
    if len(n) in (10, 11):
        n = "55" + n
    if len(n) == 13:
        return f"+{n[:2]} {n[2:4]} {n[4:9]}-{n[9:]}"
    if len(n) == 12:
        return f"+{n[:2]} {n[2:4]} {n[4:8]}-{n[8:]}"
    return ""


def celular_do_telefone(tel):
    """Telefone do Google que é celular (9 dígitos começando com 9): quase sempre é o WhatsApp do consultório."""
    n = re.sub(r"\D", "", str(tel or ""))
    if n.startswith("55"):
        n = n[2:]
    return formatar_zap(n) if len(n) == 11 and n[2] == "9" else ""


# ---------- 2. Instagram: busca e conferência ----------
def parece_dela(usuario, perfil, nome, telefone, cidade):
    """O @ é desta empresa? Pontos por nome no @, nome no perfil, cidade ou telefone na bio."""
    palavras = palavras_do_nome(nome)
    alvo = sem_acento(usuario).replace("_", "").replace(".", "")
    pontos = sum(2 for p in palavras if p in alvo)
    if perfil and perfil.get("existe"):
        texto = sem_acento(f"{perfil.get('nome')} {perfil.get('bio')} {perfil.get('categoria')}")
        pontos += sum(1 for p in palavras if p in texto)
        if cidade and sem_acento(cidade) in texto:
            pontos += 1
        tel = re.sub(r"\D", "", str(telefone or ""))[-8:]
        if tel and tel in re.sub(r"\D", "", f"{perfil.get('bio')} {perfil.get('telefone')}"):
            pontos += 3
    return pontos


# ---------- 3. nota do site sem IA ----------
def nota_do_site(e, html):
    """0 a 10 por sinais que dá para conferir. Começa em 10 e tira pelo que pesa para o cliente.
    Não substitui o olho do designer: é a triagem; ele confere no print antes de abordar."""
    if not e.get("site") or e.get("site_defeito"):
        return 0, []
    h = (html or "").lower()
    nota, problemas = 10.0, []
    vel = e.get("site_velocidade") or {}
    if vel:
        if vel.get("nota", 100) < 50:
            nota -= 2.5
            problemas.append(f"no celular o site é lento (nota {vel['nota']}/100 no teste do Google, carrega em {vel.get('carrega', '?')})")
        elif vel.get("nota", 100) < 75:
            nota -= 1
    if 'name="viewport"' not in h and "name='viewport'" not in h:
        nota -= 2.5
        problemas.append("o site não se ajusta ao celular (não tem a configuração de tela de celular)")
    if any(a in h for a in ANTIGO):
        nota -= 1.5
        problemas.append("o código é antigo (tecnologia de mais de 10 anos)")
    feito = e.get("site_feito_em") or ""
    anos = re.findall(r"(?:©|&copy;|copyright)\s*(?:20\d\d\s*[-–]\s*)?(20\d\d)", h)
    ano = int(feito[:4]) if feito[:4].isdigit() else (int(max(anos)) if anos else 0)
    if ano and time.localtime().tm_year - ano >= 4:
        nota -= 1.5
        problemas.append(f"o site parece não mudar desde {ano}")
    construtor = next((n for n, marcas in CONSTRUTORES.items() if marcas and any(m in h for m in marcas)), "")
    if construtor in ("wix", "Webnode", "Hostinger", "Weebly", "Google Sites", "Site.br/Kangoo"):
        nota -= 1.5
        problemas.append(f"foi feito num construtor pronto ({construtor.capitalize()}), com cara de modelo")
    elif construtor == "Elementor":
        nota -= 0.5
    if not re.search(r"wa\.me|whatsapp", h):
        nota -= 1
        problemas.append("não tem botão de WhatsApp para o cliente chamar")
    if not re.search(r"<h1[\s>]", h):
        nota -= 0.5
        problemas.append("a página não tem um título principal claro (o Google também usa isso)")
    titulo = re.search(r"<title[^>]*>(.*?)</title>", h, re.S)
    if not titulo or len(titulo.group(1).strip()) < 12 or titulo.group(1).strip() in ("home", "início", "inicio", "página inicial"):
        nota -= 0.5
        problemas.append("o título da aba não diz o que a empresa faz (atrapalha no Google)")
    if not re.search(r'name=["\']description["\']', h):
        nota -= 0.5
    if len(re.sub(r"<[^>]+>", " ", re.sub(r"(?s)<(script|style).*?</\1>", "", h)).split()) < 120:
        nota -= 1
        problemas.append("tem pouco texto: a página não explica os serviços")
    return max(1, min(10, round(nota))), problemas[:4]


# ---------- 4. rede ou franquia ----------
def rede_ou_franquia(e, html, lote):
    nome = sem_acento(e.get("nome"))
    if any(sem_acento(r) in nome for r in REDES_CONHECIDAS):
        return True
    if re.search(r"seja (um )?franquead|nossas unidades|franquia|unidades em todo|\d{2,} unidades", sem_acento(html or "")):
        return True
    marca = " ".join(palavras_do_nome(e.get("nome"))[:2])
    return bool(marca) and sum(1 for o in lote if " ".join(palavras_do_nome(o.get("nome"))[:2]) == marca) >= 3


# ---------- 5. tudo junto ----------
def cidade_de(endereco):
    m = re.search(r",\s*([^,\d]+?)\s*-\s*[A-Z]{2}\b", endereco or "")
    return m.group(1).strip() if m else ""


def instagram_na_busca(resultados, nome):
    """Dos resultados do Google, o @ que bate com o nome da empresa (palavra do nome no @ ou no título do resultado)."""
    palavras = palavras_do_nome(nome)
    try:
        dados = json.loads(resultados or "[]")
    except ValueError:
        return ""
    itens = []

    def junta(x):
        if isinstance(x, dict):
            link = str(x.get("link") or x.get("url") or "")
            if "instagram.com/" in link:
                itens.append((link, f"{x.get('title', '')} {x.get('description', '')}"))
            for v in x.values():
                junta(v)
        elif isinstance(x, list):
            for v in x:
                junta(v)
    junta(dados)
    melhor, pontos_melhor = "", 0
    for i, (link, texto) in enumerate(itens):
        m = re.search(r"instagram\.com/([A-Za-z0-9_.]{2,30})", link)
        if not m or m.group(1).lower() in NAO_PERFIL:
            continue
        h = m.group(1).lower().strip(".")
        alvo = sem_acento(h).replace("_", "").replace(".", "")
        pontos = sum(2 for p in palavras if p in alvo) + sum(1 for p in palavras if p in sem_acento(texto)) - i * 0.1
        if pontos > pontos_melhor:
            melhor, pontos_melhor = h, pontos
    return melhor if pontos_melhor >= 2 else ""


def analisar(e, html="", lote=(), funda=False, mais_contatos=None, buscar_google=None):
    """Uma empresa. `html` é a página do site que o checar_site já baixou. `funda` faz a busca mais caprichada."""
    fontes, site = [], e.get("site") or ""
    cidade = cidade_de(e.get("endereco")) or e.get("bairro") or ""
    achado = {"instagram": [], "whatsapp": [], "links_bio": [], "contato": []}
    if site and any(r in site.lower() for r in REDES_SOCIAIS):
        achado = contatos_na_pagina(site)  # o "site" do Google é o próprio Instagram, WhatsApp ou Linktree
        if re.search(r"linktr\.ee|bio\.link|beacons\.ai|linkbio", site, re.I):
            achado["links_bio"].append(site)
        site = ""
    elif html:
        achado = contatos_na_pagina(html)
        fontes.append(site)
    # página de contato e Linktree: muitos sites só põem o WhatsApp lá
    paginas = []
    if site and not e.get("site_defeito") and (not achado["whatsapp"] or not achado["instagram"]):
        base = site if site.startswith("http") else "https://" + site
        paginas += [urllib.parse.urljoin(base, c) for c in achado["contato"][:1]]
    paginas += achado["links_bio"][:1]
    for url in paginas:
        try:
            _, h = baixar(url, timeout=10)
        except Exception:
            continue
        mais = contatos_na_pagina(h)
        achado["instagram"] += [x for x in mais["instagram"] if x not in achado["instagram"]]
        achado["whatsapp"] += [x for x in mais["whatsapp"] if x not in achado["whatsapp"]]
        fontes.append(url)
    # varredura do site inteiro pela API oficial do Outscraper, quando a página inicial não mostrou o Instagram ou o WhatsApp
    if site and not e.get("site_defeito") and mais_contatos and (not achado["instagram"] or not achado["whatsapp"]):
        mais = mais_contatos(site) or {}
        achado["instagram"] += [x for x in mais.get("instagram", []) if x not in achado["instagram"]]
        achado["whatsapp"] += [x for x in mais.get("whatsapp", []) if x not in achado["whatsapp"]]
        if mais.get("instagram") or mais.get("whatsapp"):
            fontes.append("Outscraper · contatos do site")
    # sem site no ar e sem @ achado: busca no Google pela API oficial do Outscraper (autorizada por ele em 04/11, com limite)
    if not achado["instagram"] and buscar_google and funda:
        h = instagram_na_busca(buscar_google(f"{e.get('nome', '')} {cidade} instagram"), e.get("nome", ""))
        if h:
            achado["instagram"].append(h)
            fontes.append("Busca no Google (Outscraper)")
    # Instagram: só o que a própria empresa divulga (campo "site" do Google, site, contato, Linktree).
    # 03/11: buscar em Bing/DuckDuckGo ou ler a parte interna do Instagram foi barrado (é driblar a proteção contra robôs).
    candidatos = achado["instagram"][:5]
    escolhido, perfil, melhor = "", None, -1
    for i, c in enumerate(candidatos):
        pontos = parece_dela(c, None, e.get("nome", ""), e.get("telefone"), cidade) - i * 0.1
        if pontos > melhor:
            escolhido, melhor = c, pontos
    instagram = "@" + escolhido if escolhido else ""
    if escolhido:
        fontes.append(f"https://instagram.com/{escolhido}")
    # WhatsApp: o divulgado pela empresa; senão o da bio; senão o celular do Google
    zap = formatar_zap(achado["whatsapp"][0]) if achado["whatsapp"] else ""
    origem_zap = "site" if zap else ""
    if not zap and perfil and perfil.get("existe"):
        bio = f"{perfil.get('bio')} {perfil.get('link')} {perfil.get('telefone')}"
        n = contatos_na_pagina(bio)["whatsapp"] or re.findall(r"\(?\d{2}\)?\s?9\s?\d{4}[-\s]?\d{4}", bio)
        zap = formatar_zap(n[0]) if n else ""
        origem_zap = "Instagram" if zap else ""
    if not zap:
        zap = celular_do_telefone(e.get("telefone"))
        origem_zap = "celular do Google (provável WhatsApp)" if zap else ""
    nota, problemas = nota_do_site({**e, "site": site}, html if site else "")
    situacao = "sem site" if not site else ("site fraco" if e.get("site_defeito") or nota < 8 else "site bom")
    rede = rede_ou_franquia(e, html, lote)
    est_insta = "não deu para ver" if escolhido else ""
    # análise em 1 ou 2 frases, só com o que foi achado
    if not site:
        frase = "Não tem site próprio" + (f": o Google leva para o Instagram {instagram}" if instagram and "instagram" in (e.get("site") or "") else "") + "."
        frase += " Um site daria mais confiança a quem chega pelo Google e levaria direto para o WhatsApp."
    elif e.get("site_defeito"):
        frase = f"O site atual tem um problema: {e['site_defeito']}. Quem procura no Google não consegue ver a empresa; vale oferecer um site novo."
    elif situacao == "site fraco":
        frase = f"O site existe, mas tem pontos fracos ({'; '.join(problemas[:2]) or 'visual e conteúdo'})."
        frase += " Dá para propor otimizar o site." if (e.get("site_feito_em") or "") >= time.strftime("%Y", time.localtime(time.time() - 365 * 86400)) else " Dá para propor um site novo."
    else:
        frase = "O site parece bem cuidado pelos sinais medidos; conferir o visual no print antes de abordar."
    if est_insta == "não":
        frase += " O Instagram está parado há mais de 3 meses."
    return {
        "nome": e.get("nome", ""), "bairro": e.get("bairro", ""), "endereco": e.get("endereco", ""), "telefone": e.get("telefone", ""),
        "whatsapp": zap, "whatsapp_origem": origem_zap, "google_maps": "", "site": site, "situacao_site": situacao,
        "site_nota": nota, "site_problemas": "; ".join(problemas), "instagram": instagram, "instagram_ativo": est_insta,
        "instagram_seguidores": (perfil or {}).get("seguidores"), "nota": "", "avaliacoes": "", "rede_ou_franquia": rede,
        "analise": frase, "fontes": fontes, "analise_por": "sistema (sem IA)",
    }


def analisar_lote(empresas, htmls, funda=False, ao_terminar=None, mais_contatos=None, buscar_google=None):
    """Várias de uma vez (6 ao mesmo tempo, para não ser bloqueado nas buscas)."""
    def uma(e):
        try:
            return analisar(e, htmls.get(e.get("nome"), ""), empresas, funda, mais_contatos, buscar_google)
        except Exception:
            return None
        finally:
            if ao_terminar:
                ao_terminar()
    with ThreadPoolExecutor(max_workers=6) as fila:
        return list(fila.map(uma, empresas))
