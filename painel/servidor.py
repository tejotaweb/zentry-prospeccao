#!/usr/bin/env python3
"""Painel local de prospecção. Só abre neste computador (127.0.0.1).

Uso: python3 ~/sistema-prospeccao/painel/servidor.py
Depois abra http://localhost:4400
"""
import base64
import hashlib
import json
from html import escape as html_escape
import hmac
import secrets
import mimetypes
import os
import re
import shutil
import unicodedata
import socket
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PASTA = Path(__file__).resolve().parent
# O Python instalado no Mac não traz os certificados de segurança; sem isso, nenhuma chamada HTTPS funciona
try:
    import certifi
    os.environ.setdefault("SSL_CERT_FILE", certifi.where())
except ImportError:
    pass
sys.path.insert(0, str(PASTA.parent / "previa"))
sys.path.insert(0, str(PASTA))
import gerar as gerador  # noqa: E402
import fotos as fotos_reais  # noqa: E402
import preencher  # noqa: E402
from ia import CLIENTES, IA, ErroIA  # noqa: E402
import analise_local  # noqa: E402
from seguranca import Seguranca, ErroConta  # noqa: E402
from contas_web import ContasWeb  # noqa: E402
from espacos import Espacos  # noqa: E402

PORTA = int(os.environ.get("PROSPECCAO_PORTA", 4400))
DADOS = Path(os.environ.get("PROSPECCAO_DADOS", PASTA.parent / "dados"))
# 04/11: espaço de outra conta. O painel principal (do administrador) abre um processo destes por conta, com a pasta dela.
CONTA = os.environ.get("PROSPECCAO_CONTA", "")
MARCA = os.environ.get("PROSPECCAO_MARCA", "")
ENDERECO_ZENTRY = os.environ.get("PROSPECCAO_ENDERECO", "http://localhost:4400")  # endereço público do painel (ex.: https://zentry.seudominio.com.br)
# o que só o administrador usa (plano do Claude dele, chaves, contas)
SO_ADMIN = {"/api/maps/chave", "/api/maps/chave-outscraper", "/api/ia/entrar-plano", "/api/ia/preparar", "/api/ia/ajustar-previa",
            "/api/usuarios", "/api/acesso-config", "/api/criar-senha", "/criar-senha", "/api/conversa"}
LISTA = DADOS / "lista.json"
ESTADO = DADOS / "estado.json"
PREVIAS = DADOS / "previas"
ID_VALIDO = re.compile(r"^[\w-]{1,40}$")
PAPEIS = {"abertura", "equipe", "espaco"}
ASSINATURAS = {b"\xff\xd8\xff": ".jpg", b"\x89PNG": ".png"}
LIMITE_FOTO = 12 * 1024 * 1024
CHAVE_MAPS = DADOS / "chave-google.txt"
USO_MAPS = DADOS / "maps-uso.json"
LEADS_MAPS = DADOS / "maps-leads.json"
URL_MAPS = os.environ.get("PROSPECCAO_URL_MAPS", "https://places.googleapis.com/v1")
LIMITE_MAPS = int(os.environ.get("PROSPECCAO_LIMITE_MAPS", 1000))
CAMPOS_MAPS = ("id", "displayName", "formattedAddress", "rating", "userRatingCount", "websiteUri", "nationalPhoneNumber", "businessStatus", "googleMapsUri")
CACHE_MAPS = {}
LEADS_MANUAIS = DADOS / "leads-manuais.json"
# Outscraper: dados do Google Maps sem conta de faturamento no Google. Grátis até 500 empresas por mês.
CHAVE_OUTSCRAPER = DADOS / "chave-outscraper.txt"
USO_OUTSCRAPER = DADOS / "outscraper-uso.json"
URL_OUTSCRAPER = os.environ.get("PROSPECCAO_URL_OUTSCRAPER", "https://api.app.outscraper.com")
LIMITE_OUTSCRAPER = int(os.environ.get("PROSPECCAO_LIMITE_OUTSCRAPER", 500))
# Configurações do sistema e perfil do administrador (tela Configurações e Meu perfil)
CONFIG = DADOS / "config.json"
CONFIG_PADRAO = {
    "meta": 10, "limite_dia": 15, "nota_min": 4.0, "avaliacoes_min": 15, "site_nota_boa": 8, "site_recente_meses": 12, "previa_automatica": True, "copy_propria": "sem-ia", "analise_modo": "sem-ia", "limite_busca_google": 0,  # 03/11: aprovada na pesquisa já ganha a prévia por modelo pronto (sem Claude)
    # 03/11: a prévia sai de um modelo pronto (previa/modelos/), sem gastar o plano do Claude. "claude" volta ao layout feito do zero.
    "previa_modo": "modelo",
    "nicho_padrao": "clínica odontológica", "local_padrao": "Setor Bueno, Goiânia", "quantidade_padrao": 15,
    "perfil": {"nome": "Seu nome", "arroba": "@seuinstagram", "titulo": "Sites e Posicionamento", "cidade": "Sua cidade, UF",
               "site": "seusite.com.br", "whatsapp": "", "bio": "Edite em Meu perfil"},
}
if CONTA:
    CONFIG_PADRAO["perfil"] = {"nome": MARCA or "Minha empresa", "arroba": "", "titulo": "", "cidade": "", "site": "", "whatsapp": "", "bio": ""}
CAMPOS_OUTSCRAPER = "name,place_id,address,county,phone,website,rating,reviews,business_status,location_link,logo,photo"
DADOS.mkdir(parents=True, exist_ok=True)
(DADOS / "logs").mkdir(exist_ok=True)
ia = IA(DADOS)
SEG = Seguranca(DADOS)
WEB = ContasWeb(DADOS)
# o que abre sem login quando vem da internet
LIVRES = {"/login", "/cadastro", "/api/login", "/api/cadastro", "/api/login-opcoes", "/auth/google", "/auth/google/volta", "/favicon.ico"}
# 04/11: cada conta vai ter o próprio espaço (etapa 2). Até lá, conta aprovada que não é administradora só vê a tela de espera.
ESPACOS_PRONTOS = True  # etapa 2 pronta (04/11): cada conta com a própria pasta e o próprio processo
ESPACOS = Espacos(DADOS, PASTA / "servidor.py") if not CONTA else None
LIVRES_USUARIO = {"/espera", "/api/eu", "/api/sair"}
# Pesquisa rodando em segundo plano: o painel acompanha por /api/ia/progresso
TRAVA_BUSCA = threading.Lock()
ULTIMA_BUSCA = DADOS / "ultima-busca.json"
BUSCA = {"estado": "parada"}  # a última pesquisa pronta é carregada ao abrir o painel (fim do arquivo)
GRUPO_ANALISE = int(os.environ.get("PROSPECCAO_GRUPO_ANALISE", 3))
ANALISES_JUNTAS = int(os.environ.get("PROSPECCAO_ANALISES_JUNTAS", 5))


def progresso(**dados):
    with TRAVA_BUSCA:
        BUSCA.update(dados)


class ErroMaps(Exception):
    pass


def ler_json(caminho, padrao):
    return json.loads(caminho.read_text(encoding="utf-8")) if caminho.exists() else padrao


def gravar_json(caminho, conteudo):
    temporario = caminho.with_suffix(".tmp")
    temporario.write_text(json.dumps(conteudo, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(temporario, caminho)


def extensao_foto(dados):
    if dados[:4] == b"RIFF" and dados[8:12] == b"WEBP":
        return ".webp"
    return next((ext for assinatura, ext in ASSINATURAS.items() if dados.startswith(assinatura)), None)


def maps_chave():
    return CHAVE_MAPS.read_text(encoding="utf-8").strip() if CHAVE_MAPS.exists() else ""


def maps_uso():
    uso = ler_json(USO_MAPS, {})
    return uso if uso.get("mes") == datetime.now().strftime("%Y-%m") else {"mes": datetime.now().strftime("%Y-%m"), "buscas": 0, "detalhes": 0}


def maps_chamar(tipo, url, mascara, corpo=None):
    """Chama o Google e conta o uso. Para no limite grátis do mês, para não gerar cobrança."""
    chave = maps_chave()
    if not chave:
        raise ErroMaps("A chave do Google ainda não foi colocada.")
    uso = maps_uso()
    if uso[tipo] >= LIMITE_MAPS:
        raise ErroMaps(f"Limite grátis do mês atingido ({LIMITE_MAPS} chamadas). Parei para não gerar cobrança.")
    dados = json.dumps(corpo).encode("utf-8") if corpo is not None else None
    pedido = urllib.request.Request(url, data=dados, headers={"Content-Type": "application/json", "X-Goog-Api-Key": chave, "X-Goog-FieldMask": mascara})
    try:
        with urllib.request.urlopen(pedido, timeout=25) as resposta:
            conteudo = json.load(resposta)
    except urllib.error.HTTPError as erro:
        try:
            motivo = json.loads(erro.read()).get("error", {}).get("message", "")
        except ValueError:
            motivo = ""
        raise ErroMaps(f"O Google recusou o pedido (código {erro.code}). {motivo}".strip())
    except (urllib.error.URLError, TimeoutError):
        raise ErroMaps("Não consegui falar com o Google. Confira a internet.")
    uso[tipo] += 1
    gravar_json(USO_MAPS, uso)
    return conteudo


def maps_lugar(p):
    return {
        "place_id": p.get("id", ""), "nome": (p.get("displayName") or {}).get("text", ""), "endereco": p.get("formattedAddress", ""),
        "nota": p.get("rating"), "avaliacoes": p.get("userRatingCount", 0), "site": p.get("websiteUri", ""),
        "telefone": p.get("nationalPhoneNumber", ""), "situacao": p.get("businessStatus", ""), "link": p.get("googleMapsUri", ""),
    }


def ler_chave(arquivo):
    return arquivo.read_text(encoding="utf-8").strip() if arquivo.exists() else ""


def gravar_chave(arquivo, chave):
    arquivo.touch(mode=0o600)
    os.chmod(arquivo, 0o600)
    arquivo.write_text(chave, encoding="utf-8")


def maps_motor():
    """Outscraper vem primeiro: o faturamento do Google Cloud dele está bloqueado."""
    return "outscraper" if ler_chave(CHAVE_OUTSCRAPER) else "google" if maps_chave() else ""


LIMITE_CONTATOS = int(os.environ.get("PROSPECCAO_LIMITE_CONTATOS", 480))  # Emails & Contacts: 500 sites grátis por mês


def outscraper_contatos(site, espera=150):
    """Contatos que o próprio site divulga em todas as páginas (Instagram, WhatsApp, e-mail), pelo Emails & Contacts
    do Outscraper (API oficial, 500 sites grátis por mês). Para antes do limite grátis. {} se não der."""
    chave = ler_chave(CHAVE_OUTSCRAPER)
    dominio = (urllib.parse.urlparse(site if site.startswith("http") else "https://" + site).hostname or "").removeprefix("www.")
    uso = outscraper_uso()
    if not chave or not dominio or uso.get("contatos", 0) >= LIMITE_CONTATOS:
        return {}
    cab = {"X-API-KEY": chave}
    try:
        q = urllib.parse.urlencode({"query": dominio, "async": "true"})
        pedido = json.load(urllib.request.urlopen(urllib.request.Request(f"{URL_OUTSCRAPER}/emails-and-contacts?{q}", headers=cab), timeout=40))
        resposta, fim = pedido, time.time() + espera
        while resposta.get("status") == "Pending" and resposta.get("results_location") and time.time() < fim:
            time.sleep(4)
            resposta = json.load(urllib.request.urlopen(urllib.request.Request(resposta["results_location"], headers=cab), timeout=40))
    except Exception:
        return {}
    uso = outscraper_uso()
    uso["contatos"] = uso.get("contatos", 0) + 1
    gravar_json(USO_OUTSCRAPER, uso)
    if resposta.get("status") not in ("Success", None):
        return {}
    return analise_local.contatos_na_pagina(json.dumps(resposta.get("data") or [], ensure_ascii=False))


# 04/11: ele autorizou ("Liga, com limite"), mas no teste a busca do Outscraper não achou nenhum Instagram (só o painel da
# empresa, e ignora "site:instagram.com"). Fica desligada (0) para não cobrar à toa; o código continua pronto.
LIMITE_BUSCA_GOOGLE = int(os.environ.get("PROSPECCAO_LIMITE_BUSCA_GOOGLE", 0))


def outscraper_google(termo):
    """Busca no Google pela API oficial do Outscraper. Devolve o texto dos resultados (título, link, resumo).
    Para no limite do mês. Só é usada quando a empresa não tem site no ar e o Instagram não apareceu de outro jeito."""
    chave = ler_chave(CHAVE_OUTSCRAPER)
    limite = int(config().get("limite_busca_google", LIMITE_BUSCA_GOOGLE))
    uso = outscraper_uso()
    if not chave or uso.get("google", 0) >= limite:
        return ""
    cab = {"X-API-KEY": chave}
    try:
        q = urllib.parse.urlencode({"query": termo, "pagesPerQuery": 1, "language": "pt", "region": "BR", "async": "false"})
        resposta = json.load(urllib.request.urlopen(urllib.request.Request(f"{URL_OUTSCRAPER}/google-search-v3?{q}", headers=cab), timeout=90))
        fim = time.time() + 120
        while resposta.get("status") == "Pending" and resposta.get("results_location") and time.time() < fim:
            time.sleep(4)
            resposta = json.load(urllib.request.urlopen(urllib.request.Request(resposta["results_location"], headers=cab), timeout=40))
    except Exception:
        return ""
    uso = outscraper_uso()
    uso["google"] = uso.get("google", 0) + 1
    gravar_json(USO_OUTSCRAPER, uso)
    return json.dumps(resposta.get("data") or [], ensure_ascii=False)


def outscraper_uso():
    uso = ler_json(USO_OUTSCRAPER, {})
    return uso if uso.get("mes") == datetime.now().strftime("%Y-%m") else {"mes": datetime.now().strftime("%Y-%m"), "lugares": 0}


def outscraper_buscar(termo, pagina, limite=20):
    """Cobra por empresa devolvida, então a conta é feita por empresa e para antes do limite grátis."""
    uso = outscraper_uso()
    if uso["lugares"] + limite > LIMITE_OUTSCRAPER:
        raise ErroMaps(f"Limite grátis do mês quase no fim ({uso['lugares']} de {LIMITE_OUTSCRAPER} empresas). Parei para não gerar cobrança.")
    pular = int(pagina) if str(pagina or "").isdigit() else 0
    corpo = {"query": [termo], "language": "pt-BR", "region": "BR", "organizationsPerQueryLimit": limite,
             "skipPlaces": pular, "async": False, "fields": CAMPOS_OUTSCRAPER}
    pedido = urllib.request.Request(f"{URL_OUTSCRAPER}/google-maps-search", data=json.dumps(corpo).encode("utf-8"), method="POST",
                                    headers={"Content-Type": "application/json", "X-API-KEY": ler_chave(CHAVE_OUTSCRAPER)})
    try:
        with urllib.request.urlopen(pedido, timeout=90) as resposta:
            conteudo = json.load(resposta)
    except urllib.error.HTTPError as erro:
        motivo = {401: "A chave não foi aceita. Copie de novo do Outscraper.", 402: "A conta do Outscraper pede pagamento."}.get(erro.code, "")
        raise ErroMaps(f"O Outscraper recusou o pedido (código {erro.code}). {motivo}".strip())
    except (urllib.error.URLError, TimeoutError):
        raise ErroMaps("Não consegui falar com o Outscraper. Confira a internet.")
    if conteudo.get("error"):
        raise ErroMaps(f"O Outscraper respondeu com erro: {conteudo.get('errorMessage', '')}".strip())
    blocos = conteudo.get("data") or [[]]
    achados = blocos[0] if blocos and isinstance(blocos[0], list) else blocos
    uso["lugares"] += len(achados)
    gravar_json(USO_OUTSCRAPER, uso)
    lugares = [{
        "place_id": p.get("place_id", ""), "nome": p.get("name", ""), "endereco": p.get("address", ""), "bairro": p.get("county", ""),
        "nota": p.get("rating"), "avaliacoes": p.get("reviews") or 0, "site": p.get("website", ""), "telefone": p.get("phone", ""),
        "situacao": p.get("business_status", ""), "link": p.get("location_link", ""),
        "logo": p.get("logo") or p.get("photo") or "",
    } for p in achados if p.get("place_id")]
    return {"lugares": lugares, "proxima": str(pular + limite) if len(achados) >= limite else ""}


def maps_buscar(termo, pagina):
    if maps_motor() == "outscraper":
        return outscraper_buscar(termo, pagina)
    corpo ={"textQuery": termo, "languageCode": "pt-BR", "regionCode": "BR", "pageSize": 20}
    if pagina:
        corpo["pageToken"] = pagina
    mascara = "nextPageToken," + ",".join(f"places.{c}" for c in CAMPOS_MAPS)
    r = maps_chamar("buscas", f"{URL_MAPS}/places:searchText", mascara, corpo)
    return {"lugares": [maps_lugar(p) for p in r.get("places", [])], "proxima": r.get("nextPageToken", "")}


REDES = ("instagram.com", "wa.me", "whatsapp.com", "facebook.com", "linktr.ee", "doctoralia")


def checar_site(url, guarda=None):
    """Abre o site como um cliente abriria. Devolve o defeito em português ("" = abriu normal).
    Em `guarda`, deixa o HTML da página para descobrir quando o site foi feito."""
    url = str(url or "").strip()
    if not url or any(r in url.lower() for r in REDES):
        return ""
    if not url.startswith("http"):
        url = "https://" + url
    dominio = urllib.parse.urlparse(url).hostname or ""
    try:
        socket.getaddrinfo(dominio, 443)
    except (socket.gaierror, UnicodeError):
        return "o domínio não existe mais (ninguém responde por ele)"
    pedido = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Macintosh) Chrome/124 Safari/537.36"})
    try:
        with urllib.request.urlopen(pedido, timeout=12) as r:
            corpo = r.read(400000).decode("utf-8", "ignore").lower()
            if guarda is not None:
                guarda["corpo"] = corpo
    except urllib.error.HTTPError as erro:
        if erro.code in (401, 403, 405, 429):
            return ""  # bloqueou robô, mas o site existe
        return f"o site abre com erro {erro.code}" + (" (página não encontrada)" if erro.code == 404 else " (servidor com problema)" if erro.code >= 500 else "")
    except (TimeoutError, socket.timeout):
        return "o site não carrega (passou de 12 segundos sem responder)"
    except urllib.error.URLError as erro:
        if "certificate" in str(erro.reason).lower() or "ssl" in str(erro.reason).lower():
            return "o site abre com aviso de \"não seguro\" (certificado vencido ou errado)"
        return "o site não abre (servidor fora do ar)"
    except Exception:
        return "o site não abre"
    if any(t in corpo for t in ("domain is for sale", "este domínio", "domínio está à venda", "dominio expirado", "domain expired",
                                "parked", "account suspended", "conta suspensa", "hostgator.com.br/404", "site em construção",
                                "under construction", "index of /")):
        return "o endereço abre uma página de domínio vencido, à venda ou em construção, não o site da empresa"
    return ""


CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PRINTS = DADOS / "claude-code" / "prints"


def print_site(e):
    """Print da página como o cliente vê (1366 px de largura), para o Claude julgar o desenho e não só o texto."""
    if not e.get("site") or e.get("site_defeito") or any(r in e["site"].lower() for r in REDES) or not Path(CHROME).exists():
        return ""
    url = e["site"] if e["site"].startswith("http") else "https://" + e["site"]
    PRINTS.mkdir(parents=True, exist_ok=True)
    arquivo = PRINTS / (hashlib.sha1(url.encode()).hexdigest()[:12] + ".png")
    try:
        subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--user-data-dir={PRINTS / 'perfil'}",
                        "--window-size=1366,900", "--virtual-time-budget=8000", f"--screenshot={arquivo}", url],
                       capture_output=True, timeout=45)
    except subprocess.TimeoutExpired:
        return ""
    return f"prints/{arquivo.name}" if arquivo.exists() and arquivo.stat().st_size > 5000 else ""


LIGHTHOUSE = PASTA.parent / "node_modules" / ".bin" / "lighthouse"


def velocidade_site(e):
    """Teste de velocidade no celular com o Lighthouse (o mesmo motor do PageSpeed do Google), rodando neste Mac."""
    if not e.get("site") or e.get("site_defeito") or any(r in e["site"].lower() for r in REDES) or not LIGHTHOUSE.exists():
        return None
    url = e["site"] if e["site"].startswith("http") else "https://" + e["site"]
    saida = PRINTS / (hashlib.sha1(url.encode()).hexdigest()[:12] + "-velocidade.json")
    try:
        subprocess.run([str(LIGHTHOUSE), url, "--only-categories=performance", "--form-factor=mobile", "--output=json",
                        f"--output-path={saida}", "--chrome-flags=--headless=new --disable-gpu", "--quiet"],
                       capture_output=True, timeout=90, env={**os.environ, "CHROME_PATH": CHROME})
        dados = json.loads(saida.read_text())
        saida.unlink(missing_ok=True)
        auditorias = dados["audits"]
        return {"nota": round((dados["categories"]["performance"]["score"] or 0) * 100),
                "carrega": auditorias["largest-contentful-paint"]["displayValue"].replace(".", ",").replace("\xa0", " "),
                "peso": auditorias["total-byte-weight"]["displayValue"].replace("Total size was ", "").replace(",", ".").replace("KiB", "KB").replace("\xa0", " ")}
    except (subprocess.TimeoutExpired, OSError, ValueError, KeyError, TypeError):
        return None


def tirar_prints(empresas):
    # um de cada vez: o Chrome sem janela usa a mesma pasta de perfil; o teste de velocidade roda ao lado
    with ThreadPoolExecutor(max_workers=2) as fila:
        velocidades = fila.map(velocidade_site, empresas)
        for e in empresas:
            e["print_site"] = print_site(e)
        for e, v in zip(empresas, velocidades):
            e["site_velocidade"] = v


def registro_dominio(url):
    """Data de registro do domínio (AAAA-MM), pela consulta pública RDAP."""
    host = (urllib.parse.urlparse(url if url.startswith("http") else "https://" + url).hostname or "").removeprefix("www.")
    try:
        with urllib.request.urlopen(f"https://rdap.org/domain/{host}", timeout=10) as r:
            eventos = json.load(r).get("events", [])
    except Exception:
        return ""
    return next((ev.get("eventDate", "")[:7] for ev in eventos if ev.get("eventAction") == "registration"), "")


def data_do_site(url, corpo):
    """Quando o site atual foi feito (AAAA-MM). Pistas: mês das imagens enviadas ao WordPress (o layout atual sobe junto
    com as imagens dele), ano do rodapé e registro do domínio. Vale a pista mais recente que tiver base."""
    pistas = {}
    meses = sorted(f"{a}-{m}" for a, m in re.findall(r"/wp-content/uploads/(20\d\d)/(\d\d)/", corpo or ""))
    if meses:
        pistas["imagens"] = meses[len(meses) // 2]  # a mediana: a maioria das imagens da página
    dominio = registro_dominio(url)
    if dominio:
        pistas["domínio"] = dominio
    anos = re.findall(r"(?:©|&copy;|copyright)\s*(?:20\d\d\s*[-–]\s*)?(20\d\d)", corpo or "")
    if anos:
        pistas["rodapé"] = max(anos) + "-12"  # só o ano; não serve para dizer que é recente sozinho
    if "imagens" in pistas:
        return pistas["imagens"], pistas  # as imagens mostram quando o layout atual subiu
    if "domínio" in pistas and pistas.get("rodapé", "9999")[:4] >= pistas["domínio"][:4]:
        return pistas["domínio"], pistas  # domínio novo e rodapé do mesmo ano ou depois: site novo
    return "", pistas  # pistas que não batem: não dá para afirmar


def meses_atras(aaaa_mm):
    agora = datetime.now()
    try:
        ano, mes = map(int, aaaa_mm.split("-")[:2])
    except ValueError:
        return 999
    return (agora.year - ano) * 12 + agora.month - mes


def checar_sites(empresas):
    def um(e):
        guarda = {}
        defeito = checar_site(e.get("site"), guarda)
        feito, pistas = data_do_site(e["site"], guarda.get("corpo", "")) if e.get("site") and not defeito else ("", {})
        return defeito, feito, pistas, guarda.get("corpo", "")
    with ThreadPoolExecutor(max_workers=8) as fila:
        for e, (defeito, feito, pistas, corpo) in zip(empresas, fila.map(um, empresas)):
            e["site_defeito"], e["site_feito_em"], e["site_pistas"] = defeito, feito, pistas
            HTML_DOS_SITES[e.get("nome", "")] = corpo  # só na memória: a análise sem IA lê os links do site


HTML_DOS_SITES = {}


def salvar_avatar(chave, url):
    """Foto de perfil (logo do Google) para identificar a empresa no painel."""
    pasta = PREVIAS / chave
    if not url or any(pasta.glob("avatar.*")):
        return
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=15) as r:
            tipo, imagem = r.headers.get("Content-Type", ""), r.read(3_000_000)
    except Exception:
        return
    if not tipo.startswith("image/") or len(imagem) < 500:
        return
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / ("avatar.png" if "png" in tipo else "avatar.webp" if "webp" in tipo else "avatar.jpg")).write_bytes(imagem)


def chave_manual(nome, endereco):
    return "ia-" + hashlib.sha1(f"{str(nome).strip()[:120]}|{endereco}".lower().encode()).hexdigest()[:12]


def normalizar(nome):
    return re.sub(r"\W+", " ", str(nome).lower()).strip()


def ler_nota(texto):
    achado = re.search(r"\d(?:[.,]\d)?", str(texto))
    return float(achado.group().replace(",", ".")) if achado else None


def ler_avaliacoes(texto):
    digitos = re.sub(r"\D", "", str(texto))  # "1.234 avaliações" vira 1234
    return int(digitos) if digitos else None


def config():
    salvo = ler_json(CONFIG, {})
    cfg = {**CONFIG_PADRAO, **{k: v for k, v in salvo.items() if k in CONFIG_PADRAO},
           "perfil": {**CONFIG_PADRAO["perfil"], **salvo.get("perfil", {})}}
    if CONTA:  # nas outras contas, nada que gaste o plano do Claude do administrador
        cfg.update({"analise_modo": "sem-ia", "copy_propria": "sem-ia", "previa_modo": "modelo", "limite_busca_google": 0})
    return cfg


def oferta(e):
    """O que oferecer: site novo, ou otimização quando o site é recente mas fraco."""
    feito = e.get("site_feito_em", "")
    if e.get("site") and not e.get("site_defeito") and feito and meses_atras(feito) < config()["site_recente_meses"]:
        return "otimização do site"
    return "site novo"


def motivos_descarte(e, ja_na_lista):
    """A mesma régua da Conferência (avaliar no painel), mais o que tira a chance de fechar."""
    motivos, cfg = [], config()
    nota, avals = ler_nota(e.get("nota", "")), ler_avaliacoes(e.get("avaliacoes", ""))
    if nota is None or avals is None:
        motivos.append("não achei nota e avaliações no Google")
    else:
        if nota <= cfg["nota_min"]:
            motivos.append(f"nota {e['nota']} (precisa passar de {str(cfg['nota_min']).replace('.', ',')})")
        if avals < cfg["avaliacoes_min"]:
            motivos.append(f"{e['avaliacoes']} avaliações (precisa de {cfg['avaliacoes_min']})")
    if not e.get("instagram"):
        # análise sem IA não procura em buscador: "não achado" não quer dizer "não tem" (03/11)
        if not str(e.get("analise_por", "")).startswith("sistema"):
            motivos.append("sem Instagram")
    elif e.get("instagram_ativo") == "não":
        motivos.append("Instagram parado")
    if e.get("rede_ou_franquia"):
        motivos.append("rede ou franquia")
    nota_site = e.get("site_nota")
    if isinstance(nota_site, int) and nota_site > 0 and e.get("situacao_site") != "sem site":
        site_bom = nota_site >= cfg["site_nota_boa"]  # julgado pelo print do site, não só pelo texto
    else:
        site_bom = e.get("situacao_site") == "site bom"
    # site feito há pouco: se for bom, sai; se a nota for baixa, entra com oferta de otimização (decisão dele, 02/11)
    if site_bom and not e.get("site_defeito"):
        motivos.append(f"já tem um site bom (nota {nota_site}/10)" if isinstance(nota_site, int) and nota_site else "já tem um site bom")
    nome = normalizar(e.get("nome", ""))
    if any(normalizar(c) in nome for c in CLIENTES):
        motivos.append("já é seu cliente")
    elif nome in ja_na_lista:
        motivos.append("já está na lista")
    return motivos


HISTORICO_BUSCAS = DADOS / "historico-buscas.json"


def guardar_no_historico(busca):
    """Toda pesquisa pronta fica guardada, para abrir de novo sem gastar notas do Google."""
    historico = ler_json(HISTORICO_BUSCAS, [])
    busca_id = datetime.fromtimestamp(busca.get("fim") or time.time()).strftime("%Y%m%d-%H%M%S")
    historico = [h for h in historico if h.get("id") != busca_id]
    historico.insert(0, {"id": busca_id, "data": datetime.fromtimestamp(busca.get("fim") or time.time()).strftime("%Y-%m-%d %H:%M"),
                         **{k: busca.get(k) for k in ("nicho", "local", "quantidade", "total", "aprovadas", "descartadas")}})
    gravar_json(HISTORICO_BUSCAS, historico[:60])


def executar_busca(nicho, local, quantidade):
    """Roda em segundo plano. O Claude analisa; a régua da Conferência decide. Só as aprovadas entram na lista."""
    try:
        todas = (ler_json(LISTA, None) or {"empresas": []})["empresas"] + ler_json(LEADS_MANUAIS, [])
        ja = {normalizar(e["nome"]) for e in todas}
        aprovadas, descartadas = [], []
        if ler_chave(CHAVE_OUTSCRAPER):
            achadas, descartadas = achar_no_maps(nicho, local, quantidade, ja)
        else:
            progresso(etapa=2)
            achadas = ia.pesquisar_e_analisar(nicho, local, sorted({e["nome"] for e in todas}), quantidade)
            progresso(total=len(achadas), passa_google=len(achadas), analisadas=len(achadas))
        progresso(etapa=3)
        for e in achadas:
            motivos = motivos_descarte(e, ja)
            (descartadas if motivos else aprovadas).append({**e, "motivos": motivos, "oferta": oferta(e)})
            ja.add(normalizar(e.get("nome", "")))
        gravar_manuais(aprovadas, "ia", "Encontrada e aprovada pela pesquisa com IA", nicho)
        estado = ler_json(ESTADO, {})
        for e in aprovadas:
            estado.setdefault(chave_manual(e["nome"], e.get("endereco", "")), {}).update({
                "nota": e["nota"], "avaliacoes": str(ler_avaliacoes(e["avaliacoes"])), "site": "tem" if e["site"] else "nao", "site_url": e["site"],
                "cliente": "nao", "instagram": e["instagram"], "obs": f"Oferta: {e.get('oferta', 'site novo')}. {e['analise']}", "aprovada_em": datetime.now().strftime("%Y-%m-%d")})
        gravar_json(ESTADO, estado)
        progresso(estado="pronta", etapa=4, aprovadas=aprovadas, descartadas=descartadas, fim=time.time())
        # decisão dele (02/11): a prévia é gerada quando ele clica em Empresas; o automático fica opcional
        if config().get("previa_automatica"):
            enfileirar_previas([chave_manual(e["nome"], e.get("endereco", "")) for e in aprovadas])
        with TRAVA_BUSCA:
            gravar_json(ULTIMA_BUSCA, dict(BUSCA))
            guardar_no_historico(dict(BUSCA))
    except (ErroIA, ErroMaps) as erro:
        progresso(estado="erro", erro=str(erro), fim=time.time())
    except Exception as erro:  # a pesquisa roda solta: qualquer falha precisa aparecer no painel
        progresso(estado="erro", erro=f"A pesquisa parou: {erro}", fim=time.time())


def achar_no_maps(nicho, local, quantidade, ja):
    """Nota, avaliações, telefone e link do Maps vêm do Google pelo Outscraper. O Claude só analisa quem passou nisso,
    em grupos pequenos rodando ao mesmo tempo."""
    lugares = outscraper_buscar(f"{nicho}, {local}", 0, quantidade)["lugares"]
    candidatas, descartadas = [], []
    for p in lugares:
        e = {"nome": p["nome"], "bairro": p["bairro"], "endereco": p["endereco"], "telefone": p["telefone"], "site": p["site"],
             "google_maps": p["link"], "nota": str(p["nota"] or "").replace(".", ","), "avaliacoes": str(p["avaliacoes"] or ""),
             "place_id": p["place_id"], "logo": p.get("logo", ""), "fontes": [p["link"]] if p["link"] else []}
        # Antes de gastar análise: o que o Maps já mostra (fechada, nota, avaliações, cliente, já na lista)
        motivos = [m for m in motivos_descarte({**e, "instagram": "-"}, ja) if m != "já tem um site bom"]
        if p["situacao"] and p["situacao"] != "OPERATIONAL":
            motivos.insert(0, "fechada no Google")
        (descartadas if motivos else candidatas).append({**e, "motivos": motivos})
    checar_sites(candidatas + descartadas)  # site fora do ar é oportunidade: o defeito vai junto para a abordagem
    progresso(etapa=2, total=len(lugares), passa_google=len(candidatas), fora_google=len(descartadas), analisadas=0)
    if not candidatas:
        return [], descartadas
    if config().get("analise_modo", "sem-ia") != "claude":
        return analisar_sem_ia(candidatas, descartadas)
    tirar_prints(candidatas)
    grupos = [candidatas[i:i + GRUPO_ANALISE] for i in range(0, len(candidatas), GRUPO_ANALISE)]
    analises, feitas = {}, 0
    with ThreadPoolExecutor(max_workers=ANALISES_JUNTAS) as fila:
        trabalhos = {fila.submit(ia.analisar_empresas, g, True): g for g in grupos}
        for t in as_completed(trabalhos):
            try:
                for a in t.result():
                    analises[normalizar(a.get("nome", ""))] = a
            except ErroIA:
                pass  # o grupo que falhou aparece como "o Claude não conseguiu analisar"
            feitas += len(trabalhos[t])
            progresso(analisadas=feitas)
    achadas = []
    for e in candidatas:
        a = analises.get(normalizar(e["nome"]))
        if not a:
            descartadas.append({**e, "motivos": ["o Claude não conseguiu analisar"]})
            continue
        site = a.get("site") or ("" if a.get("situacao_site") == "sem site" else e["site"])
        achadas.append({**a, **{k: e[k] for k in ("nome", "bairro", "endereco", "google_maps", "nota", "avaliacoes", "place_id", "logo", "site_defeito",
                                                  "print_site", "site_feito_em", "site_pistas", "site_velocidade")},
                        "telefone": e["telefone"] or a.get("telefone", ""), "site": site,
                        "fontes": e["fontes"] + [f for f in a.get("fontes", []) if f not in e["fontes"]]})
    # Instagram não achado na primeira passada: segunda busca, só para o perfil e o contato certo
    # (pedido dele: não perder empresa boa por "sem Instagram" que na verdade tem perfil)
    sem_perfil = [e for e in achadas if not e.get("instagram")]
    with ThreadPoolExecutor(max_workers=ANALISES_JUNTAS) as fila:
        for e, achado in zip(sem_perfil, fila.map(procurar_contato_seguro, sem_perfil)):
            juntar_contato(e, achado)
    return achadas, descartadas


def analisar_sem_ia(candidatas, descartadas):
    """03/11: a análise que o Claude fazia, feita pelo código (site, Instagram, WhatsApp, rede), sem gastar token."""
    with ThreadPoolExecutor(max_workers=2) as fila:  # velocidade no celular pelo Lighthouse, aqui mesmo
        for e, v in zip(candidatas, fila.map(velocidade_site, candidatas)):
            e["site_velocidade"] = v
    feitas = [0]
    trava = threading.Lock()

    def avancou():
        with trava:
            feitas[0] += 1
            progresso(analisadas=feitas[0])
    resultados = analise_local.analisar_lote(candidatas, HTML_DOS_SITES, funda=True, ao_terminar=avancou, mais_contatos=outscraper_contatos, buscar_google=outscraper_google)
    achadas = []
    for e, a in zip(candidatas, resultados):
        if not a:
            descartadas.append({**e, "motivos": ["não deu para analisar (site ou busca sem resposta)"]})
            continue
        achadas.append({**a, **{k: e.get(k) for k in ("nome", "bairro", "endereco", "google_maps", "nota", "avaliacoes", "place_id", "logo", "site_defeito",
                                                      "site_feito_em", "site_pistas", "site_velocidade")},
                        "telefone": e["telefone"], "fontes": e["fontes"] + [f for f in a["fontes"] if f not in e["fontes"]], "contato_procurado": True})
    HTML_DOS_SITES.clear()
    return achadas, descartadas


def contato_sem_ia(e):
    """Busca caprichada de Instagram e WhatsApp sem IA (site, Linktree, Bing/DuckDuckGo e perfil público)."""
    guarda = {}
    if e.get("site") and not e.get("site_defeito"):
        checar_site(e["site"], guarda)
    a = analise_local.analisar(e, guarda.get("corpo", ""), [], funda=True, mais_contatos=outscraper_contatos, buscar_google=outscraper_google)
    return {k: a[k] for k in ("instagram", "instagram_ativo", "whatsapp", "analise", "fontes")}


def procurar_contato(e):
    return ia.procurar_contato(e) if config().get("analise_modo", "sem-ia") == "claude" else contato_sem_ia(e)


def procurar_contato_seguro(e):
    try:
        return procurar_contato(e)
    except ErroIA:
        return {}


def juntar_contato(e, achado):
    for campo in ("instagram", "instagram_ativo", "whatsapp", "telefone"):
        if achado.get(campo) and not e.get(campo):
            e[campo] = achado[campo]
    if achado.get("instagram") and e.get("instagram_ativo") in ("", None):
        e["instagram_ativo"] = achado.get("instagram_ativo", "")
    if achado.get("analise"):
        e["analise"] = achado["analise"]
    e["fontes"] = e.get("fontes", []) + [f for f in achado.get("fontes", []) if f not in e.get("fontes", [])]
    e["contato_procurado"] = True


# ---------- fila automática de prévias (pedido dele em 02/11: aprovada no filtro já ganha o layout) ----------
FILA_PREVIAS = DADOS / "fila-previas.json"
TRAVA_FILA = threading.Lock()
FILA_ACORDA = threading.Event()


def fila_estado():
    with TRAVA_FILA:
        return ler_json(FILA_PREVIAS, {})


def fila_marcar(cnpj, **campos):
    with TRAVA_FILA:
        fila = ler_json(FILA_PREVIAS, {})
        fila[cnpj] = {**fila.get(cnpj, {}), **campos}
        gravar_json(FILA_PREVIAS, fila)


def enfileirar_previas(cnpjs):
    """Põe na fila quem ainda não tem prévia. A fila roda sozinha, uma empresa por vez."""
    novos = 0
    for cnpj in cnpjs:
        if (PREVIAS / cnpj / "index.html").exists():
            continue
        atual = fila_estado().get(cnpj, {})
        if atual.get("etapa") in ("na fila", "análise", "layout"):
            continue
        fila_marcar(cnpj, etapa="na fila", erro="", pedida=time.time())
        novos += 1
    FILA_ACORDA.set()
    return novos


TRABALHOS_JUNTOS = 1  # uma por vez: duas juntas estouravam o limite diário do plano dele (03/11)


def pegar_previa():
    """Tira da fila a próxima prévia, marcando na hora, para dois trabalhadores não pegarem a mesma."""
    with TRAVA_FILA:
        fila = ler_json(FILA_PREVIAS, {})
        pendentes = sorted((v.get("pedida", 0), k) for k, v in fila.items() if v.get("etapa") == "na fila")
        if not pendentes:
            return None
        cnpj = pendentes[0][1]
        fila[cnpj] = {**fila[cnpj], "etapa": "análise", "inicio": time.time()}
        gravar_json(FILA_PREVIAS, fila)
        return cnpj


AJUSTE_ACORDA = threading.Event()


def rodar_ajustes():
    """Vaga só para os ajustes que ele pede na tela de Prévias: nunca esperam prévia nova (pedido dele em 03/11)."""
    while True:
        AJUSTE_ACORDA.wait(timeout=20)
        AJUSTE_ACORDA.clear()
        while True:
            ajuste = proximo_ajuste()
            if not ajuste:
                break
            fazer_ajuste(*ajuste)


def rodar_fila():
    while True:
        FILA_ACORDA.wait(timeout=60)
        while True:
            cnpj = pegar_previa()
            if not cnpj:
                FILA_ACORDA.clear()
                break
            fazer_previa(cnpj)


# ---------- ajustes pedidos na tela de Prévias ----------
def ler_ajustes(cnpj):
    return ler_json(PREVIAS / cnpj / "ajustes.json", [])


def pedir_ajuste(cnpj, pedido, imagens=None):
    if not ID_VALIDO.match(cnpj) or not (PREVIAS / cnpj / "index.html").exists():
        raise ErroIA("Essa empresa ainda não tem prévia.")
    pedido = str(pedido or "").strip()[:2000]
    if len(pedido) < 3 and not imagens:
        raise ErroIA("Escreva o que quer mudar.")
    ajuste_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    # prints que ele anexa para mostrar onde mudar (até 4, colados ou escolhidos no computador)
    salvas = []
    for n, dado in enumerate((imagens or [])[:4]):
        achado = re.match(r"data:image/(png|jpe?g|webp|gif);base64,(.+)", str(dado), re.S)
        if not achado:
            continue
        conteudo = base64.b64decode(achado.group(2))
        if len(conteudo) > 10_000_000:
            raise ErroIA("Imagem grande demais (máximo 10 MB).")
        pasta_img = PREVIAS / cnpj / "ajustes-img"
        pasta_img.mkdir(exist_ok=True)
        nome = f"{ajuste_id}-{n + 1}.{achado.group(1).replace('jpeg', 'jpg')}"
        (pasta_img / nome).write_bytes(conteudo)
        salvas.append(f"ajustes-img/{nome}")
    with TRAVA_FILA:
        ajustes = ler_ajustes(cnpj)
        ajustes.append({"id": ajuste_id, "pedido": pedido or "Ajuste mostrado na imagem.", "imagens": salvas, "quando": time.time(), "etapa": "na fila"})
        gravar_json(PREVIAS / cnpj / "ajustes.json", ajustes)
    AJUSTE_ACORDA.set()
    return ajustes


def marcar_ajuste(cnpj, ajuste_id, **campos):
    with TRAVA_FILA:
        ajustes = ler_ajustes(cnpj)
        for a in ajustes:
            if a["id"] == ajuste_id:
                a.update(campos)
        gravar_json(PREVIAS / cnpj / "ajustes.json", ajustes)


def proximo_ajuste():
    if not PREVIAS.exists():
        return None
    with TRAVA_FILA:  # marca na hora, para dois trabalhadores não pegarem o mesmo ajuste
        for pasta in sorted(PREVIAS.iterdir()):
            ajustes = ler_ajustes(pasta.name) if pasta.is_dir() else []
            for a in ajustes:
                if a.get("etapa") == "na fila":
                    a.update(etapa="fazendo", inicio=time.time())
                    gravar_json(pasta / "ajustes.json", ajustes)
                    return pasta.name, a
    return None


def fazer_ajuste(cnpj, ajuste):
    pasta = PREVIAS / cnpj
    try:
        # guarda a versão de antes, para dá para voltar
        versoes = pasta / "versoes"
        versoes.mkdir(exist_ok=True)
        (versoes / f"index-{ajuste['id']}.html").write_bytes((pasta / "index.html").read_bytes())
        resumo = ia.ajustar_previa(pasta, ajuste["pedido"], ajuste.get("imagens") or [])
        if ler_json(pasta / "publicado.json", {}).get("link"):
            publicar_previa(cnpj)  # regra dele (03/11): todo ajuste já publicado vai para o link
            resumo += " Atualizado no link do cliente."
        marcar_ajuste(cnpj, ajuste["id"], etapa="pronto", fim=time.time(), resumo=resumo)
    except ErroIA as erro:
        marcar_ajuste(cnpj, ajuste["id"], etapa="erro", fim=time.time(), erro=str(erro))
    except Exception as erro:  # a fila roda solta: qualquer falha precisa aparecer no painel
        marcar_ajuste(cnpj, ajuste["id"], etapa="erro", fim=time.time(), erro=f"Parou: {erro}")


def previa_por_modelo(cnpj, empresa, pasta):
    """Modelo pronto preenchido com os dados da empresa, sem IA (decisão de 03/11: o layout do zero estourava o plano).
    Sai em segundos com o que já está na pasta; depois baixa as fotos do Google e do site atual e monta de novo."""
    fila_marcar(cnpj, etapa="layout", inicio_layout=time.time())
    feito = preencher.gerar(empresa, pasta)
    fila_marcar(cnpj, etapa="pronta", fim=time.time(), erro="", resumo=feito["resumo"], receita=feito["receita"])
    avisos = []
    if not (pasta / "maps.json").exists() or not (pasta / "fotos.json").exists():
        registro = fotos_reais.juntar_fotos(empresa, pasta, ler_chave(CHAVE_OUTSCRAPER))
        avisos += registro.get("avisos") or []
        feito = preencher.gerar(empresa, pasta, guardar_versao=False)
    if not (pasta / "texto-site.txt").exists():
        # texto do site atual (sem IA): a copy montada no modelo usa para achar os serviços reais
        fatos, site, _, _ = preencher.fatos_para_copy(empresa, pasta)
        (pasta / "texto-site.txt").write_text(fotos_reais.texto_do_site(site), encoding="utf-8")
        feito = preencher.gerar(empresa, pasta, guardar_versao=False)
    if config().get("copy_propria") == "claude" and not (pasta / "copy.json").exists():
        # 03/11: copy reescrita com os dados desta empresa numa chamada curta (sem ferramentas); se falhar, fica a do nicho
        fila_marcar(cnpj, etapa="copy")
        try:
            criar_copy(empresa, pasta)
            feito = preencher.gerar(empresa, pasta, guardar_versao=False)
        except ErroIA as erro:
            avisos.append(str(erro))
        fila_marcar(cnpj, etapa="pronta")
    fila_marcar(cnpj, resumo=(feito["resumo"] + (" " + " ".join(avisos) if avisos else "")).strip())


def criar_copy(empresa, pasta):
    fatos, site, cliente, lugar = preencher.fatos_para_copy(empresa, pasta)
    copy = ia.copy_da_empresa(fatos, fotos_reais.texto_do_site(site), pasta, cliente, lugar)
    copy["_fatos"] = fatos
    (pasta / "copy.json").write_text(json.dumps(copy, ensure_ascii=False, indent=1), encoding="utf-8")
    return copy


def completar_fotos():
    """Prévia que ficou sem as fotos do Google (o painel fechou no meio do download): baixa e monta de novo (03/11)."""
    todas = (ler_json(LISTA, None) or {"empresas": []})["empresas"] + ler_json(LEADS_MANUAIS, [])
    for e in todas:
        pasta = PREVIAS / e["cnpj"]
        if not (pasta / "index.html").exists() or (pasta / "fotos.json").exists() or (pasta / "publicado.json").exists():
            continue
        try:
            fotos_reais.juntar_fotos(e, pasta, ler_chave(CHAVE_OUTSCRAPER))
            (pasta / "texto-site.txt").exists() or (pasta / "texto-site.txt").write_text(
                fotos_reais.texto_do_site(preencher.fatos_para_copy(e, pasta)[1]), encoding="utf-8")
            feito = preencher.gerar(e, pasta, guardar_versao=False)
            fila_marcar(e["cnpj"], resumo=feito["resumo"], receita=feito["receita"])
        except Exception as erro:
            print(f"fotos de {e['cnpj']} não vieram: {erro}", flush=True)


def fazer_previa(cnpj):
    pasta = PREVIAS / cnpj
    try:
        todas = (ler_json(LISTA, None) or {"empresas": []})["empresas"] + ler_json(LEADS_MANUAIS, [])
        empresa = next((e for e in todas if e["cnpj"] == cnpj), None)
        if not empresa:
            raise ErroIA("Empresa não encontrada na lista.")
        pasta.mkdir(parents=True, exist_ok=True)
        if config().get("previa_modo", "modelo") != "claude":
            return previa_por_modelo(cnpj, empresa, pasta)
        if not (pasta / "copy.md").exists():
            fila_marcar(cnpj, etapa="análise", inicio=time.time())
            estado = ler_json(ESTADO, {}).get(cnpj, {})
            docs = ia.preparar_empresa(empresa, {k: v for k, v in estado.items() if k not in ("b", "m")}, com_posts=False, rapido=True)
            for nome in ("analise", "copy"):
                destino = pasta / f"{nome}.md"
                if not destino.exists():
                    destino.write_text(docs[f"{nome}_md"], encoding="utf-8")
        if not (pasta / "index.html").exists():
            fila_marcar(cnpj, etapa="layout", inicio_layout=time.time())
            resumo = ia.montar_layout(empresa, pasta)
            fila_marcar(cnpj, resumo=resumo)
        fila_marcar(cnpj, etapa="pronta", fim=time.time(), erro="")
    except ErroIA as erro:
        fila_marcar(cnpj, etapa="erro", erro=str(erro), fim=time.time())
        if "limite" in str(erro).lower():
            # plano sem limite agora: devolve para a fila e espera uma hora antes de tentar de novo
            fila_marcar(cnpj, etapa="na fila", erro=str(erro), pedida=time.time())
            time.sleep(3600)
    except Exception as erro:  # a fila roda solta: qualquer falha precisa aparecer no painel
        fila_marcar(cnpj, etapa="erro", erro=f"Parou: {erro}", fim=time.time())


# Etiquetas da conversa (pedido dele em 02/11: mensagem enviada já vira "Contatado")
ETIQUETAS = {"enviada", "respondeu", "pediu", "reuniao", "fechou", "sem_interesse", "encerrada"}


def marcar_conversa(corpo):
    """Muda a etiqueta de uma empresa. Usado pelo Claude logo depois de enviar uma mensagem com o "sim" do administrador:
    curl -s localhost:4400/api/conversa -H 'Content-Type: application/json' -d '{"cnpj":"...","status":"enviada","canal":"instagram","texto":"..."}'"""
    cnpj, status = str(corpo.get("cnpj", "")), str(corpo.get("status", ""))
    if not ID_VALIDO.match(cnpj) or status not in ETIQUETAS:
        raise ErroIA("Empresa ou etiqueta inválida.")
    hoje = datetime.now().strftime("%Y-%m-%d")
    estado = ler_json(ESTADO, {})
    m = estado.setdefault(cnpj, {}).setdefault("m", {})
    if status == "enviada" and m.get("status") == "enviada" and corpo.get("retorno"):
        m["retornos"] = m.get("retornos", 0) + 1
        m["ultimo_em"] = hoje
    else:
        m["status"] = status
    if status == "enviada" and not m.get("enviada_em"):
        m.update(enviada_em=hoje, ultimo_em=hoje, retornos=0)
    if status in ("respondeu", "pediu", "reuniao") and not m.get("respondeu_em"):
        m["respondeu_em"] = hoje
    if status == "fechou":
        m["fechou_em"] = hoje
    for campo in ("canal", "texto"):
        if corpo.get(campo):
            m["canal" if campo == "canal" else ("primeira" if not m.get("primeira") else "ultima")] = str(corpo[campo])[:600]
    m["atualizado_em"] = int(time.time() * 1000)
    gravar_json(ESTADO, estado)
    return {"ok": True, "m": m}


# ---------- publicar a prévia no site dele (03/11: "como vou enviar o link do site pra pessoa") ----------
SITE_PASTA = Path(os.environ.get("PROSPECCAO_SITE_PASTA", Path.home() / "meu-site"))  # repositório do seu site (Astro/Netlify) onde as prévias aprovadas são publicadas em /p/
DOMINIO = os.environ.get("PROSPECCAO_SITE_DOMINIO", "https://seusite.com.br")
TRAVA_PUBLICAR = threading.Lock()
FORA_DA_PUBLICACAO = {".md", ".json", ".txt"}
PASTAS_FORA = {"versoes", "ajustes-img", "bruto", "posts", "prints"}


def git_site(*args):
    r = subprocess.run(["git", "-C", str(SITE_PASTA), *args], capture_output=True, text=True, timeout=120, env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
    if r.returncode != 0:
        raise ErroIA(f"O GitHub recusou: {(r.stderr or r.stdout).strip()[:200]}")
    return r.stdout


def publicar_previa(cnpj):
    """Copia a prévia para <seu site>/p/<nome>-<código>/ e publica pelo GitHub (o Netlify põe no ar sozinho).
    Endereço com código, fora do Google (noindex + robots) e fora do menu do site."""
    pasta = PREVIAS / cnpj
    if not ID_VALIDO.match(cnpj) or not (pasta / "index.html").exists():
        raise ErroIA("Essa empresa ainda não tem prévia.")
    if CONTA:
        # outras contas: o link é do próprio Zentry (o painel principal mostra sem login só o que tem publicado.json)
        registro = ler_json(pasta / "publicado.json", {})
        registro.update({"slug": cnpj, "link": f"{ENDERECO_ZENTRY}/v/{CONTA}/{cnpj}/", "publicado_em": datetime.now().strftime("%Y-%m-%d %H:%M")})
        gravar_json(pasta / "publicado.json", registro)
        return registro
    if not (SITE_PASTA / ".git").exists():
        raise ErroIA("Não achei o repositório do seu site (defina PROSPECCAO_SITE_PASTA).")
    with TRAVA_PUBLICAR:
        registro = ler_json(pasta / "publicado.json", {})
        if not registro.get("slug"):
            todas = (ler_json(LISTA, None) or {"empresas": []})["empresas"] + ler_json(LEADS_MANUAIS, [])
            nome = next((e["nome"] for e in todas if e["cnpj"] == cnpj), cnpj)
            base = re.sub(r"[^a-z0-9]+", "-", unicodedata.normalize("NFD", nome).encode("ascii", "ignore").decode().lower()).strip("-")[:28].strip("-")
            registro["slug"] = f"{base}-{hashlib.sha1((cnpj + str(time.time())).encode()).hexdigest()[:4]}"
        destino = SITE_PASTA / "public" / "p" / registro["slug"]
        if destino.exists():
            shutil.rmtree(destino)
        for item in pasta.rglob("*"):
            relativo = item.relative_to(pasta)
            if item.is_dir() or relativo.parts[0] in PASTAS_FORA or item.suffix in FORA_DA_PUBLICACAO or relativo.name.startswith("versao"):
                continue
            (destino / relativo).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, destino / relativo)
        # uma vez só: tudo em /p/ fora do Google
        robots = SITE_PASTA / "public" / "robots.txt"
        if robots.exists() and "Disallow: /p/" not in robots.read_text():
            robots.write_text(robots.read_text().replace("Allow: /", "Allow: /\nDisallow: /p/", 1))
        toml = SITE_PASTA / "netlify.toml"
        if toml.exists() and "/p/*" not in toml.read_text():
            toml.write_text(toml.read_text().rstrip() + '\n\n# Prévias de proposta: fora do Google\n[[headers]]\n  for = "/p/*"\n  [headers.values]\n    X-Robots-Tag = "noindex, nofollow"\n')
        caminhos = [f"public/p/{registro['slug']}", "public/robots.txt", "netlify.toml"]
        git_site("add", "--", *caminhos)
        if git_site("diff", "--cached", "--name-only", "--", *caminhos).strip():
            git_site("commit", "-m", f"Prévia de proposta: {registro['slug']}", "--", *caminhos)
        # envia o que estiver pendente; se o GitHub tiver algo novo, sincroniza e tenta de novo
        try:
            git_site("push", "origin", "HEAD")
        except ErroIA:
            git_site("pull", "--rebase", "--autostash", "origin", "main")
            git_site("push", "origin", "HEAD")
        registro.update(link=f"{DOMINIO}/p/{registro['slug']}/", publicado_em=datetime.now().strftime("%Y-%m-%d %H:%M"))
        gravar_json(pasta / "publicado.json", registro)
        return registro


# ---------- editor visual (03/11, pedido dele: "deixar as alterações pra não consumir o Claude") ----------
def salvar_edicao(cnpj, html):
    pasta = PREVIAS / cnpj
    html = str(html or "")
    if not ID_VALIDO.match(cnpj) or not (pasta / "index.html").exists():
        raise ErroIA("Essa empresa não tem prévia.")
    if "<html" not in html.lower() or len(html) < 500 or len(html) > 5_000_000:
        raise ErroIA("A página editada veio incompleta. Nada foi salvo.")
    versoes = pasta / "versoes"
    versoes.mkdir(exist_ok=True)
    (versoes / f"index-{datetime.now():%Y%m%d-%H%M%S}-editor.html").write_bytes((pasta / "index.html").read_bytes())
    (pasta / "index.html").write_text(html, encoding="utf-8")
    resposta = {"ok": True}
    if ler_json(pasta / "publicado.json", {}).get("link"):
        resposta.update(publicar_previa(cnpj))  # já está no ar: o link mostra a versão nova
    return resposta


def imagem_edicao(cnpj, dado):
    pasta = PREVIAS / cnpj
    achado = re.match(r"data:image/(png|jpe?g|webp|gif);base64,(.+)", str(dado or ""), re.S)
    if not ID_VALIDO.match(cnpj) or not pasta.exists() or not achado:
        raise ErroIA("Imagem inválida.")
    conteudo = base64.b64decode(achado.group(2))
    if len(conteudo) > 10_000_000:
        raise ErroIA("Imagem grande demais (máximo 10 MB).")
    (pasta / "img").mkdir(exist_ok=True)
    nome = f"img/editor-{datetime.now():%Y%m%d-%H%M%S}.{achado.group(1).replace('jpeg', 'jpg')}"
    (pasta / nome).write_bytes(conteudo)
    return {"ok": True, "caminho": nome}


def procurar_contato_da_busca(place_id, nome):
    """Botão "Procurar perfil e contato" de um resultado já pesquisado: testa o site, faz a busca caprichada e reavalia."""
    with TRAVA_BUSCA:
        lista = [e for grupo in ("aprovadas", "descartadas") for e in BUSCA.get(grupo, [])]
    e = next((x for x in lista if (place_id and x.get("place_id") == place_id) or (not place_id and x.get("nome") == nome)), None)
    if not e:
        raise ErroIA("Não achei essa empresa na pesquisa aberta.")
    e["site_defeito"] = checar_site(e.get("site"))
    juntar_contato(e, procurar_contato(e))
    todas = (ler_json(LISTA, None) or {"empresas": []})["empresas"] + ler_json(LEADS_MANUAIS, [])
    ja = {normalizar(x["nome"]) for x in todas}
    pendentes = [m for m in e.get("motivos", []) if m in ("o Claude não conseguiu analisar", "fechada no Google")]
    e["motivos"] = pendentes + [m for m in motivos_descarte(e, ja) if m not in pendentes]
    with TRAVA_BUSCA:
        if not e["motivos"] and e in BUSCA.get("descartadas", []):
            # passou na régua com o contato achado: entra na lista como as aprovadas
            BUSCA["descartadas"].remove(e)
            e["oferta"] = oferta(e)
            BUSCA.setdefault("aprovadas", []).append(e)
            gravar_manuais([e], "ia", "Aprovada depois de achar o perfil e o contato", BUSCA.get("nicho", ""))
            if config().get("previa_automatica"):
                enfileirar_previas([chave_manual(e["nome"], e.get("endereco", ""))])
            e["entrou_na_lista"] = True
        gravar_json(ULTIMA_BUSCA, dict(BUSCA))
    return {"ok": True, "empresa": e}


def gravar_manuais(novas, fonte, razao, nicho=""):
    leads = ler_json(LEADS_MANUAIS, [])
    ids = {l["cnpj"] for l in leads}
    lugares = {l.get("place_id") for l in leads if l.get("place_id")}
    for e in novas if isinstance(novas, list) else []:
        nome = str(e.get("nome", "")).strip()[:120]
        place_id = str(e.get("place_id", ""))[:300]
        if not nome or (place_id and place_id in lugares):
            continue
        chave = chave_manual(nome, e.get("endereco", ""))
        if chave in ids:
            continue
        ids.add(chave)
        lugares.add(place_id)
        leads.append({
            "cnpj": chave, "cnpj_formatado": "a conferir", "nome": nome, "razao": razao, "nicho": str(e.get("nicho") or nicho)[:60],
            "natureza": "", "bairro_nome": str(e.get("bairro", ""))[:80], "endereco": str(e.get("endereco", ""))[:200],
            "telefone": str(e.get("telefone", ""))[:40], "anos": "?", "ano_abertura": "", "fonte": fonte, "place_id": place_id,
            "dica": {k: str(e.get(k, ""))[:200] for k in ("site", "instagram", "nota", "avaliacoes")},
            "contatos": {k: str(e.get(k, ""))[:300] for k in ("instagram", "whatsapp", "google_maps", "site")},
            "site_defeito": str(e.get("site_defeito", ""))[:200],
            # o que a pesquisa descobriu: vai junto para a tela Empresas
            "oferta": str(e.get("oferta") or oferta(e))[:40], "site_nota": e.get("site_nota") if isinstance(e.get("site_nota"), int) else None,
            "site_problemas": str(e.get("site_problemas", ""))[:600], "site_velocidade": e.get("site_velocidade") or None,
            "site_feito_em": str(e.get("site_feito_em", ""))[:7], "analise": str(e.get("analise", ""))[:800],
            "instagram_ativo": str(e.get("instagram_ativo", ""))[:20],
            "fontes": [str(f)[:300] for f in e.get("fontes", [])][:8],
        })
    gravar_json(LEADS_MANUAIS, leads)
    for e in novas if isinstance(novas, list) else []:
        salvar_avatar(chave_manual(str(e.get("nome", "")).strip()[:120], e.get("endereco", "")), e.get("logo"))
    return len(leads)


def maps_chave_lead(place_id):
    return "maps-" + hashlib.sha1(place_id.encode()).hexdigest()[:16]


def maps_empresas():
    """Só o código do lugar fica no disco. O resto é lido ao vivo, com memória de 1 hora."""
    empresas = []
    for lead in ler_json(LEADS_MAPS, []):
        guardado = CACHE_MAPS.get(lead["place_id"])
        if guardado and time.time() - guardado[0] < 3600:
            lugar = guardado[1]
        else:
            try:
                lugar = maps_lugar(maps_chamar("detalhes", f"{URL_MAPS}/places/{urllib.parse.quote(lead['place_id'])}", ",".join(CAMPOS_MAPS)))
                CACHE_MAPS[lead["place_id"]] = (time.time(), lugar)
            except ErroMaps as erro:
                lugar = {"nome": "Empresa do Maps (não consegui ler agora)", "erro": str(erro)}
        empresas.append({**lugar, "cnpj": lead["id"], "fonte": "maps", "cnpj_formatado": "a conferir", "razao": "Encontrada no Google Maps",
                         "endereco": lugar.get("endereco", ""), "bairro_nome": "", "anos": "?", "ano_abertura": ""})
    return empresas


def producao():
    """Em que etapa cada prévia está, olhando os arquivos que existem na pasta dela."""
    saida = {}
    if not PREVIAS.exists():
        return saida
    for pasta in PREVIAS.iterdir():
        if pasta.is_dir():
            fotos = pasta / "img"
            saida[pasta.name] = {
                "analise": (pasta / "analise.md").exists(), "copy": (pasta / "copy.md").exists(), "posts": (pasta / "posts.md").exists(),
                "fotos": len(list(fotos.iterdir())) if fotos.exists() else 0, "layout": (pasta / "index.html").exists(),
                # foto de perfil ou logo da empresa, para identificar no painel
                "avatar": next((f.name for f in sorted(pasta.glob("avatar.*")) if f.suffix in (".jpg", ".png", ".webp")), ""),
                "versao": int((pasta / "index.html").stat().st_mtime) if (pasta / "index.html").exists() else 0,
                "ajustes": ler_ajustes(pasta.name)[-20:],
                "link": ler_json(pasta / "publicado.json", {}).get("link", ""),
            }
    return saida


def receita_status():
    if LISTA.exists():
        return "pronta"
    return "processando" if subprocess.run(["pgrep", "-f", "filtrar_receita"], capture_output=True).returncode == 0 else "parada"


def achar_empresa(cnpj, enviada):
    """Empresa real vem da lista. Empresa de exemplo vem do painel e nunca entra no estado."""
    lista = ler_json(LISTA, None) or {"empresas": []}
    real = next((x for x in lista["empresas"] if x["cnpj"] == cnpj), None)
    if real:
        return real
    return enviada if cnpj.startswith("exemplo-") and isinstance(enviada, dict) else None


def avisar_nova_conta(conta):
    """E-mail para o administrador quando alguém se cadastra (se o e-mail estiver ligado)."""
    para = WEB.avisos_para()
    if para:
        threading.Thread(target=WEB.enviar, daemon=True, args=(
            para, f"Nova conta no Zentry: {conta['nome']}",
            f"{conta['nome']} ({conta['email']}) criou uma conta pelo {'Google' if conta['metodo'] == 'google' else 'e-mail'} e está esperando liberação. Libere em {WEB.situacao()['endereco']} → Configurações → Usuários.",
            WEB.html("Nova conta esperando liberação", f"<b>{conta['nome']}</b> ({conta['email']}) criou uma conta pelo {'Google' if conta['metodo'] == 'google' else 'e-mail'}.",
                     "Abrir Usuários", WEB.situacao()["endereco"] + "/#usuarios"))).start()


class Painel(BaseHTTPRequestHandler):
    def responder(self, corpo, tipo="application/json; charset=utf-8", codigo=200, extra=None):
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "same-origin")
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        if self.remoto():
            self.send_header("Strict-Transport-Security", "max-age=31536000")
        for chave, valor in (extra or {}).items():
            self.send_header(chave, valor)
        self.end_headers()
        self.wfile.write(corpo)

    def responder_json(self, conteudo, codigo=200):
        self.responder(json.dumps(conteudo, ensure_ascii=False).encode("utf-8"), codigo=codigo)

    def corpo_json(self):
        return json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))

    def servir_previa(self):
        partes = self.path.split("?")[0].split("/")[2:]
        if not partes or not ID_VALIDO.match(partes[0]):
            return self.responder_json({"erro": "prévia não encontrada"}, 404)
        raiz = (PREVIAS / partes[0]).resolve()
        relativo = "/".join(partes[1:]) or "index.html"
        arquivo = (raiz / relativo).resolve()
        if not arquivo.is_relative_to(raiz) or not arquivo.is_file():
            return self.responder_json({"erro": "prévia não encontrada"}, 404)
        tipo = mimetypes.guess_type(arquivo.name)[0] or "application/octet-stream"
        if arquivo.suffix == ".md":
            tipo = "text/plain"
        if tipo.startswith("text/"):
            tipo += "; charset=utf-8"
        self.responder(arquivo.read_bytes(), tipo, extra={"X-Robots-Tag": "noindex, nofollow"})

    # ---------- segurança (04/11) ----------
    def remoto(self):
        """Veio pela internet (túnel da Cloudflare)? A Cloudflare sempre põe esses cabeçalhos; no Mac eles não existem."""
        return bool(self.headers.get("Cf-Connecting-Ip") or self.headers.get("Cf-Ray"))

    def ip(self):
        return self.headers.get("Cf-Connecting-Ip") or self.client_address[0]

    def conta(self):
        return SEG.conta_da_sessao(SEG.do_cookie(self.headers.get("Cookie")))

    def eh_admin(self):
        if not self.remoto():
            return True
        c = self.conta()
        return bool(c and c.get("papel") == "admin")

    def liberado(self):
        if not self.remoto():
            return True  # no próprio Mac: entra direto (é como o Claude altera o sistema)
        caminho = self.path.split("?")[0]
        if caminho in LIVRES:
            return True
        c = self.conta()
        if not c:
            return False
        return c.get("papel") == "admin" or ESPACOS_PRONTOS or caminho in LIVRES_USUARIO

    def barrar(self):
        caminho = self.path.split("?")[0]
        if self.conta():  # logado, mas sem permissão para isto (conta comum antes dos espaços separados)
            if caminho.startswith("/api/"):
                return self.responder_json({"erro": "Sem permissão."}, 403)
            return self.ir("/espera")
        if caminho.startswith("/api/"):
            return self.responder_json({"erro": "Entre com o seu usuário e senha.", "login": True}, 401)
        return self.ir("/login")

    def ir(self, destino, cookie=None):
        self.send_response(302)
        self.send_header("Location", destino)
        self.send_header("Cache-Control", "no-store")
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()

    def origem_ok(self):
        """Pedido que muda dados, vindo da internet, só do próprio painel (protege contra outro site abrir pedidos em seu nome)."""
        if not self.remoto():
            return True
        origem = self.headers.get("Origin", "")
        host = self.headers.get("Host", "")
        return bool(host) and origem in (f"https://{host}",)

    def para_https(self):
        """Pela internet, sempre com cadeado: http vira https (o cookie de login só anda em https)."""
        if self.remoto() and self.headers.get("X-Forwarded-Proto", "https") == "http":
            self.send_response(301)
            self.send_header("Location", f"https://{self.headers.get('Host', 'localhost:4400')}{self.path}")
            self.end_headers()
            return True
        return False

    def com_sessao(self, conta, destino=None):
        token = SEG.abrir_sessao(conta["id"])
        if destino:
            return self.ir(destino, SEG.cookie(token))
        return self.responder(json.dumps({"ok": True}).encode(), extra={"Set-Cookie": SEG.cookie(token)})

    def do_GET(self):
        if self.para_https():
            return
        caminho = self.path.split("?")[0]
        if CONTA and caminho in SO_ADMIN:
            return self.responder_json({"erro": "Disponível só para o administrador."}, 403)
        if caminho in ("/login", "/cadastro", "/criar-senha", "/espera"):
            if caminho == "/criar-senha" and self.remoto():
                return self.responder_json({"erro": "A conta de administrador só pode ser criada no próprio Mac."}, 403)
            return self.responder((PASTA / "login.html").read_bytes(), "text/html; charset=utf-8")
        if caminho.startswith("/v/") and not CONTA:
            return self.previa_publica()
        if caminho == "/api/login-opcoes":
            return self.responder_json({"google": WEB.situacao()["google_ligado"]})
        if caminho == "/auth/google":
            if not WEB.situacao()["google_ligado"]:
                return self.ir("/login?erro=google")
            estado = secrets.token_urlsafe(24)
            return self.ir(WEB.google_link(estado), SEG.cookie(estado, nome="zentry_estado", duracao=600))
        if caminho == "/auth/google/volta":
            return self.volta_google()
        if not self.liberado():
            return self.barrar()
        if caminho == "/api/eu":
            c = self.conta()
            return self.responder_json(SEG.publico(c) if c else {"papel": "admin", "local": True, "creditos": None})
        if caminho == "/api/usuarios":
            if not self.eh_admin():
                return self.responder_json({"erro": "Sem permissão."}, 403)
            return self.responder_json({"contas": SEG.listar(), "acesso": WEB.situacao()})
        if self.de_outra_conta():
            return self.repassar("GET")
        return self.get_liberado()

    # ---------- espaço das outras contas ----------
    def de_outra_conta(self):
        if CONTA or not self.remoto():
            return False
        c = self.conta()
        return bool(c and c.get("papel") != "admin")

    def repassar(self, metodo, corpo=b""):
        c = self.conta()
        porta = ESPACOS.garantir(c)
        try:
            codigo, cabecalhos, dados = ESPACOS.repassar(porta, metodo, self.path, corpo, dict(self.headers))
        except Exception as erro:
            print(f"espaço da conta {c['id']} não respondeu: {erro}", flush=True)
            return self.responder_json({"erro": "Seu espaço está reiniciando. Tente de novo em alguns segundos."}, 503)
        tipo = next((v for k, v in cabecalhos if k == "Content-Type"), "application/octet-stream")
        extra = {k: v for k, v in cabecalhos if k not in ("Content-Type", "Cache-Control")}
        if codigo in (301, 302) and "Location" in extra:
            return self.ir(extra["Location"])
        self.responder(dados, tipo, codigo, extra)
        return codigo, dados

    def previa_publica(self):
        """Prévia publicada de outra conta: aberta sem login (é o link que vai para o cliente), só se tiver publicado.json."""
        partes = self.path.split("?")[0].split("/")
        if len(partes) < 4 or not ID_VALIDO.match(partes[2]) or not ID_VALIDO.match(partes[3]):
            return self.responder_json({"erro": "não encontrado"}, 404)
        if len(partes) == 4:
            self.send_response(301)
            self.send_header("Location", self.path.split("?")[0] + "/")
            self.end_headers()
            return
        raiz = (DADOS / "contas" / partes[2] / "previas" / partes[3]).resolve()
        if not (raiz / "publicado.json").exists():
            return self.responder_json({"erro": "não encontrado"}, 404)
        arquivo = (raiz / ("/".join(partes[4:]) or "index.html")).resolve()
        if not arquivo.is_relative_to(raiz) or not arquivo.is_file() or arquivo.suffix in (".json", ".md", ".txt") or "versoes" in arquivo.relative_to(raiz).parts:
            return self.responder_json({"erro": "não encontrado"}, 404)
        tipo = mimetypes.guess_type(arquivo.name)[0] or "application/octet-stream"
        if tipo.startswith("text/"):
            tipo += "; charset=utf-8"
        self.responder(arquivo.read_bytes(), tipo, extra={"X-Robots-Tag": "noindex, nofollow"})

    def volta_google(self):
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        estado = SEG.do_cookie(self.headers.get("Cookie"), "zentry_estado")
        if not estado or not hmac.compare_digest(estado, (q.get("state") or [""])[0]) or not q.get("code"):
            return self.ir("/login?erro=google")
        try:
            email, nome, sub = WEB.google_trocar(q["code"][0])
            conta, nova = SEG.entrar_google(email, nome, sub)
        except Exception as erro:
            print(f"login Google falhou: {erro}", flush=True)
            return self.ir("/login?erro=google")
        if nova:
            avisar_nova_conta(conta)
        if conta["status"] == "ativo":
            return self.com_sessao(conta, "/")
        return self.ir("/login?aguardando=1")

    def do_POST(self):
        if self.para_https():
            return
        caminho = self.path.split("?")[0]
        if CONTA and caminho in SO_ADMIN:
            return self.responder_json({"erro": "Disponível só para o administrador."}, 403)
        if not self.origem_ok():
            return self.responder_json({"erro": "pedido inválido"}, 403)
        if caminho == "/api/login":
            return self.entrar()
        if caminho == "/api/cadastro":
            return self.cadastrar()
        if caminho == "/api/criar-senha":
            if self.remoto():
                return self.responder_json({"erro": "A conta de administrador só pode ser criada no próprio Mac."}, 403)
            try:
                corpo = self.corpo_json()
                conta = SEG.criar_admin(corpo.get("email") or corpo.get("usuario"), corpo.get("senha"), corpo.get("nome", ""))
            except (ErroConta, ValueError, TypeError) as erro:
                return self.responder_json({"erro": str(erro)}, 400)
            return self.com_sessao(conta)
        if caminho == "/api/sair":
            SEG.fechar_sessao(SEG.do_cookie(self.headers.get("Cookie")))
            return self.responder(json.dumps({"ok": True}).encode(), extra={"Set-Cookie": SEG.cookie("", apagar=True)})
        if not self.liberado():
            return self.barrar()
        if caminho in ("/api/usuarios", "/api/acesso-config"):
            if not self.eh_admin():
                return self.responder_json({"erro": "Sem permissão."}, 403)
            try:
                corpo = self.corpo_json()
                if caminho == "/api/acesso-config":
                    return self.responder_json({"ok": True, "acesso": WEB.salvar(corpo)})
                if corpo.get("acao") == "creditos":
                    saldo = SEG.creditar(str(corpo.get("id", "")), int(corpo.get("quantidade", 0)), "liberado pelo administrador")
                    return self.responder_json({"ok": True, "saldo": saldo})
                conta = SEG.mudar(str(corpo.get("id", "")), str(corpo.get("acao", "")))
                if corpo.get("acao") in ("bloquear", "recusar", "remover") and ESPACOS:
                    ESPACOS.desligar(conta["id"])
                enviado = False
                if corpo.get("acao") == "aprovar":
                    enviado = WEB.enviar(conta["email"], "Seu acesso ao Zentry foi liberado",
                                         f"Olá, {conta['nome']}! Seu acesso ao Zentry foi liberado. Entre em {WEB.situacao()['endereco']}/login",
                                         WEB.html("Seu acesso foi liberado", f"Olá, {conta['nome']}! Já pode entrar no Zentry com o seu e-mail ({conta['email']}).",
                                                  "Entrar no Zentry", WEB.situacao()["endereco"] + "/login"))
                return self.responder_json({"ok": True, "conta": conta, "email_enviado": enviado})
            except (ErroConta, ValueError, TypeError) as erro:
                return self.responder_json({"erro": str(erro)}, 400)
        if self.de_outra_conta():
            corpo = self.rfile.read(int(self.headers.get("Content-Length", 0) or 0))
            if caminho == "/api/ia/buscar":
                return self.busca_com_credito(corpo)
            self.repassar("POST", corpo)
            return
        return self.post_liberado()

    def busca_com_credito(self, corpo):
        """1 crédito = 1 empresa pesquisada. Cobra antes; se a busca nem começar, devolve."""
        c = self.conta()
        try:
            q = min(40, max(5, int(json.loads(corpo or b"{}").get("quantidade") or 15)))
        except (ValueError, TypeError):
            return self.responder_json({"erro": "pedido inválido"}, 400)
        if not SEG.debitar(c["id"], q, f"pesquisa de {q} empresas"):
            return self.responder_json({"erro": f"Sem créditos para pesquisar {q} empresas (seu saldo: {SEG.publico(SEG.por_id(c['id']))['creditos']}). Peça créditos ao administrador.", "sem_creditos": True}, 402)
        resultado = self.repassar("POST", corpo)
        if not resultado or resultado[0] >= 400:
            SEG.creditar(c["id"], q, "devolução: a pesquisa não começou")

    def entrar(self):
        ip = self.ip()
        if SEG.bloqueado("login:" + ip):
            return self.responder_json({"erro": "Muitas tentativas erradas. Espere 15 minutos."}, 429)
        try:
            corpo = self.corpo_json()
        except (ValueError, TypeError):
            return self.responder_json({"erro": "pedido inválido"}, 400)
        conta = SEG.conferir(corpo.get("email") or corpo.get("usuario"), corpo.get("senha"))
        if not conta:
            SEG.errou("login:" + ip)
            time.sleep(0.8)
            return self.responder_json({"erro": "E-mail ou senha errados."}, 401)
        if conta.get("status") == "pendente":
            return self.responder_json({"erro": "Sua conta está aguardando liberação. Você recebe um e-mail quando for liberada."}, 403)
        if conta.get("status") != "ativo":
            return self.responder_json({"erro": "Esta conta não tem acesso."}, 403)
        return self.com_sessao(conta)

    def cadastrar(self):
        ip = self.ip()
        if SEG.bloqueado("cadastro:" + ip):
            return self.responder_json({"erro": "Muitos cadastros seguidos. Espere 15 minutos."}, 429)
        try:
            corpo = self.corpo_json()
            SEG.errou("cadastro:" + ip)  # conta toda tentativa de cadastro, para ninguém encher a lista
            conta = SEG.cadastrar(corpo.get("email"), corpo.get("senha"), corpo.get("nome"))
        except (ErroConta, ValueError, TypeError) as erro:
            return self.responder_json({"erro": str(erro)}, 400)
        avisar_nova_conta(conta)
        return self.responder_json({"ok": True, "aguardando": True})

    def get_liberado(self):
        if self.path == "/":
            self.responder((PASTA / "index.html").read_bytes(), "text/html; charset=utf-8")
        elif self.path == "/api/arsenal":
            self.responder_json(ler_json(PASTA.parent / "metodo" / "arsenal-abordagens.json", []))
        elif self.path == "/foto-perfil.jpg":  # foto de perfil no topo do painel (painel/foto.jpg se existir; senão a inicial do nome)
            if CONTA or not (PASTA / "foto.jpg").exists():
                inicial = (config()["perfil"].get("nome") or "Z")[:1].upper()
                svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="32" fill="#3b82f6"/>'
                       f'<text x="50%" y="54%" font-family="Inter,Arial" font-size="28" font-weight="600" fill="#fff" text-anchor="middle" dominant-baseline="middle">{html_escape(inicial)}</text></svg>')
                return self.responder(svg.encode(), "image/svg+xml")
            self.responder((PASTA / "foto.jpg").read_bytes(), "image/jpeg")
        elif self.path == "/api/ia/historico":
            self.responder_json(ler_json(HISTORICO_BUSCAS, []))
        elif self.path == "/api/ia/progresso":
            with TRAVA_BUSCA:
                self.responder_json({**BUSCA, "agora": time.time()})
        elif self.path == "/estilo.css":
            self.responder((PASTA / "estilo.css").read_bytes(), "text/css; charset=utf-8")
        elif self.path == "/api/dados":
            self.responder_json({"lista": ler_json(LISTA, None), "estado": ler_json(ESTADO, {}), "maps": maps_empresas(), "manuais": ler_json(LEADS_MANUAIS, []),
                                 "plano_ligado": ia.plano_ligado(), "config": config(),
                                 "producao": producao(), "receita": receita_status(), "maps_ligado": bool(maps_motor()), "outscraper_ligado": bool(ler_chave(CHAVE_OUTSCRAPER)), "maps_motor": maps_motor(),
                                 "maps_uso": maps_uso(), "maps_limite": LIMITE_MAPS, "outscraper_uso": outscraper_uso(), "outscraper_limite": LIMITE_OUTSCRAPER,
                                 "fila_previas": fila_estado()})
        elif self.path == "/api/ia/fila":
            self.responder_json({**fila_estado(), "_ajustes": {p.name: [a.get("etapa") for a in ler_ajustes(p.name)] for p in PREVIAS.iterdir() if p.is_dir()}})
        elif self.path.startswith("/previas/"):
            parte = self.path.split("/")
            if len(parte) == 3:  # /previas/x sem a barra: as imagens relativas quebrariam
                self.send_response(301)
                self.send_header("Location", self.path + "/")
                self.end_headers()
                return
            self.servir_previa()
        else:
            self.responder_json({"erro": "não encontrado"}, 404)

    def post_liberado(self):
        # Exigir JSON impede que outro site aberto no navegador faça pedidos a este painel.
        if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
            return self.responder_json({"erro": "pedido inválido"}, 415)
        try:
            corpo = self.corpo_json()
        except (ValueError, TypeError):
            return self.responder_json({"erro": "pedido inválido"}, 400)
        if self.path == "/api/estado":
            # a etiqueta marcada pelo Claude (rota /api/conversa) não pode ser apagada por um painel aberto com dados velhos
            atual = ler_json(ESTADO, {})
            # 04/11: um pedido com o estado quase vazio apagou aprovações e notas; agora isso é recusado e há cópia por hora
            tam_atual, tam_novo = len(json.dumps(atual)), len(json.dumps(corpo))
            if tam_atual > 2000 and tam_novo < tam_atual * 0.5:
                return self.responder_json({"erro": "Gravação recusada: apagaria mais da metade dos dados. Recarregue o painel."}, 409)
            copias = DADOS / "copias-estado"
            copias.mkdir(exist_ok=True)
            hora = copias / f"estado-{datetime.now():%Y%m%d-%H}.json"
            if atual and not hora.exists():
                hora.write_text(json.dumps(atual, ensure_ascii=False), encoding="utf-8")
                for velha in sorted(copias.glob("estado-*.json"))[:-72]:
                    velha.unlink()
            for cnpj, reg in atual.items():
                m = reg.get("m") or {}
                novo = corpo.setdefault(cnpj, {})
                if m.get("atualizado_em", 0) > (novo.get("m") or {}).get("atualizado_em", 0):
                    novo["m"] = m
            gravar_json(ESTADO, corpo)
            return self.responder_json({"ok": True})
        if self.path == "/api/conversa":
            try:
                return self.responder_json(marcar_conversa(corpo))
            except ErroIA as erro:
                return self.responder_json({"erro": str(erro)}, 400)
        if self.path == "/api/config":
            return self.salvar_config(corpo)
        if self.path == "/api/maps/chave":
            return self.salvar_chave(corpo)
        if self.path == "/api/maps/chave-outscraper":
            chave = str(corpo.get("chave", "")).strip()
            if not re.fullmatch(r"[\w\-=|.+/]{20,300}", chave):
                return self.responder_json({"erro": "Essa chave não parece certa. Copie de novo do Outscraper."}, 400)
            gravar_chave(CHAVE_OUTSCRAPER, chave)
            return self.responder_json({"ok": True})
        if self.path == "/api/maps/buscar":
            try:
                return self.responder_json({**maps_buscar(str(corpo.get("termo", "")), corpo.get("pagina")), "uso": maps_uso(), "outscraper_uso": outscraper_uso()})
            except ErroMaps as erro:
                return self.responder_json({"erro": str(erro)}, 422)  # 502 a Cloudflare troca pela página dela (04/11)
        if self.path == "/api/maps/adicionar":
            return self.adicionar_leads(corpo)
        if self.path.startswith("/api/ia/"):
            try:
                return self.rota_ia(self.path.removeprefix("/api/ia/"), corpo)
            except ErroIA as erro:
                return self.responder_json({"erro": str(erro)}, 422)  # 502 a Cloudflare troca pela página dela (04/11)
        if self.path == "/api/previa":
            return self.criar_previa(corpo)
        if self.path == "/api/foto":
            return self.salvar_foto(corpo)
        self.responder_json({"erro": "não encontrado"}, 404)

    def salvar_config(self, corpo):
        """Só aceita os campos conhecidos, com limites que não quebram o painel."""
        atual, erros = config(), []
        limites = {"meta": (1, 500, int), "limite_dia": (1, 100, int), "nota_min": (0, 5, float), "avaliacoes_min": (0, 5000, int), "site_nota_boa": (1, 10, int), "site_recente_meses": (0, 60, int), "quantidade_padrao": (5, 40, int)}
        for campo, (mini, maxi, tipo) in limites.items():
            if campo in corpo:
                try:
                    valor = tipo(str(corpo[campo]).replace(",", "."))
                    if not mini <= valor <= maxi:
                        raise ValueError
                    atual[campo] = valor
                except ValueError:
                    erros.append(campo)
        if corpo.get("previa_modo") in ("modelo", "claude"):
            atual["previa_modo"] = corpo["previa_modo"]
        for campo in ("nicho_padrao", "local_padrao"):
            if campo in corpo:
                atual[campo] = str(corpo[campo]).strip()[:80] or CONFIG_PADRAO[campo]
        if isinstance(corpo.get("perfil"), dict):
            atual["perfil"] = {k: str(corpo["perfil"].get(k, atual["perfil"][k])).strip()[:200] for k in CONFIG_PADRAO["perfil"]}
        if erros:
            return self.responder_json({"erro": "Confira estes campos: " + ", ".join(erros)}, 400)
        gravar_json(CONFIG, atual)
        self.responder_json({"ok": True, "config": atual})

    def salvar_chave(self, corpo):
        chave = str(corpo.get("chave", "")).strip()
        if not re.fullmatch(r"[\w-]{20,100}", chave):
            return self.responder_json({"erro": "Essa chave não parece certa. Copie de novo do Google."}, 400)
        gravar_chave(CHAVE_MAPS, chave)
        self.responder_json({"ok": True})

    def adicionar_leads(self, corpo):
        # Vindo do Outscraper não há a regra de só guardar o código do lugar: entra como empresa comum.
        if isinstance(corpo.get("lugares"), list):
            novas = [{**l, "nota": str(l.get("nota") or ""), "avaliacoes": str(l.get("avaliacoes") or ""), "fontes": [l.get("link", "")] if l.get("link") else []}
                     for l in corpo["lugares"] if isinstance(l, dict)]
            return self.responder_json({"ok": True, "total": self.gravar_manuais(novas, "busca", "Encontrada na busca do Maps")})
        leads = ler_json(LEADS_MAPS, [])
        existentes = {l["place_id"] for l in leads}
        for place_id in corpo.get("place_ids", []):
            if isinstance(place_id, str) and re.fullmatch(r"[\w-]{5,300}", place_id) and place_id not in existentes:
                leads.append({"id": maps_chave_lead(place_id), "place_id": place_id})
                existentes.add(place_id)
        gravar_json(LEADS_MAPS, leads)
        self.responder_json({"ok": True, "total": len(leads)})

    def rota_ia(self, rota, corpo):
        if rota == "entrar-plano":
            ia.entrar_no_plano()
            return self.responder_json({"ok": True})
        if rota == "buscar":
            nicho, local = str(corpo.get("nicho", "")).strip(), str(corpo.get("local", "")).strip()
            if not nicho or not local:
                raise ErroIA("Escreva o nicho e o bairro ou cidade.")
            quantidade = min(40, max(5, int(corpo.get("quantidade") or 15)))
            if not ler_chave(CHAVE_OUTSCRAPER) and not ia.plano_ligado():
                raise ErroIA("A busca do Google (Outscraper) não está ligada.")
            with TRAVA_BUSCA:
                if BUSCA.get("estado") == "rodando":
                    raise ErroIA("Já tem uma pesquisa rodando. Espere ela terminar.")
                BUSCA.clear()
                BUSCA.update({"estado": "rodando", "etapa": 0, "nicho": nicho, "local": local, "quantidade": quantidade, "inicio": time.time(),
                              "total": None, "passa_google": None, "fora_google": None, "analisadas": None, "aprovadas": [], "descartadas": []})
            threading.Thread(target=executar_busca, args=(nicho, local, quantidade), daemon=True).start()
            return self.responder_json({"ok": True})
        if rota == "adicionar":
            empresas = [e for e in corpo.get("empresas", []) if isinstance(e, dict)]
            total = self.gravar_manuais(empresas, "ia", "Colocada na lista por você, depois da pesquisa com IA" if corpo.get("preencher") else "Encontrada pela pesquisa com IA",
                                        str(corpo.get("nicho") or BUSCA.get("nicho") or ""))
            if corpo.get("preencher"):
                # leva os dados que a pesquisa achou para a Conferência; quem aprova é ele
                estado = ler_json(ESTADO, {})
                for e in empresas:
                    reg = estado.setdefault(chave_manual(str(e.get("nome", "")).strip()[:120], e.get("endereco", "")), {})
                    # sem a Conferência (02/11): o que ele põe na lista vai direto para Empresas
                    reg.update(forcada=True, cliente="nao", aprovada_em=reg.get("aprovada_em") or datetime.now().strftime("%Y-%m-%d"))
                    for campo, valor in (("nota", e.get("nota")), ("avaliacoes", str(ler_avaliacoes(e.get("avaliacoes", "")) or "")),
                                         ("site", "tem" if e.get("site") else ""), ("site_url", e.get("site")), ("instagram", e.get("instagram")),
                                         ("obs", "; ".join(e.get("motivos", [])) + (f" — {e['analise']}" if e.get("analise") else ""))):
                        if valor and not reg.get(campo):
                            reg[campo] = str(valor)[:300]
                gravar_json(ESTADO, estado)
                if config().get("previa_automatica"):
                    enfileirar_previas([chave_manual(str(e.get("nome", "")).strip()[:120], e.get("endereco", "")) for e in empresas])
            return self.responder_json({"ok": True, "total": total})
        if rota == "salvar-edicao":
            return self.responder_json(salvar_edicao(str(corpo.get("cnpj", "")), corpo.get("html")))
        if rota == "foto-foco":
            # o enquadramento que ele escolhe no editor fica guardado na foto: toda remontagem usa o dele (03/11, "deixa treinável")
            cnpj, arquivo = str(corpo.get("cnpj", "")), str(corpo.get("arquivo", ""))
            if not ID_VALIDO.match(cnpj) or not re.fullmatch(r"[\w.-]+", arquivo):
                raise ErroIA("Foto inválida.")
            caminho = PREVIAS / cnpj / "fotos.json"
            registro = ler_json(caminho, {"fotos": []})
            for f in registro.get("fotos", []):
                if f.get("arquivo") == arquivo:
                    f["foco"] = [max(0, min(100, round(float(corpo.get("x", 50))))), max(0, min(100, round(float(corpo.get("y", 50)))))]
            gravar_json(caminho, registro)
            return self.responder_json({"ok": True})
        if rota == "imagem-edicao":
            return self.responder_json(imagem_edicao(str(corpo.get("cnpj", "")), corpo.get("imagem")))
        if rota == "publicar":
            return self.responder_json({"ok": True, **publicar_previa(str(corpo.get("cnpj", "")))})
        if rota == "ajustar-previa":
            return self.responder_json({"ok": True, "ajustes": pedir_ajuste(str(corpo.get("cnpj", "")), corpo.get("pedido"), corpo.get("imagens"))})
        if rota == "previas-auto":
            # botão "Gerar prévias": põe na fila as aprovadas que ainda não têm layout
            cnpjs = [str(c) for c in corpo.get("cnpjs", []) if ID_VALIDO.match(str(c))]
            return self.responder_json({"ok": True, "novas": enfileirar_previas(cnpjs)})
        if rota == "trocar-modelo":
            # monta de novo pelo modelo pronto, com outra receita de abertura (ou a pedida), sem IA
            cnpj = str(corpo.get("cnpj", ""))
            todas = (ler_json(LISTA, None) or {"empresas": []})["empresas"] + ler_json(LEADS_MANUAIS, [])
            empresa = next((e for e in todas if e["cnpj"] == cnpj), None) if ID_VALIDO.match(cnpj) else None
            if not empresa:
                raise ErroIA("Empresa não encontrada.")
            receita = str(corpo.get("receita", "")).upper()
            if receita not in preencher.RECEITAS:
                atual = ler_json(preencher.ROTACAO, {"empresas": {}})["empresas"].get(cnpj, "A")
                letras = list(preencher.RECEITAS)
                receita = letras[(letras.index(atual) + 1) % len(letras)]
            feito = preencher.gerar(empresa, PREVIAS / cnpj, receita)
            fila_marcar(cnpj, etapa="pronta", resumo=feito["resumo"], receita=receita, fim=time.time(), erro="")
            return self.responder_json({"ok": True, **feito})
        if rota == "limpar":
            # apaga só o resultado das pesquisas; as empresas que já entraram na lista continuam lá
            with TRAVA_BUSCA:
                if BUSCA.get("estado") == "rodando":
                    raise ErroIA("Tem uma pesquisa rodando. Espere ela terminar para limpar.")
                BUSCA.clear()
                for arquivo in (ULTIMA_BUSCA, HISTORICO_BUSCAS):
                    arquivo.unlink(missing_ok=True)
            return self.responder_json({"ok": True})
        if rota == "testar-analise":
            # roda a análise sem IA numa empresa que já está na lista e só mostra o resultado (não grava nada)
            cnpj = str(corpo.get("cnpj", ""))
            todas = (ler_json(LISTA, None) or {"empresas": []})["empresas"] + ler_json(LEADS_MANUAIS, [])
            emp = next((x for x in todas if x["cnpj"] == cnpj), None)
            if not emp:
                raise ErroIA("Empresa não encontrada.")
            e = {"nome": emp.get("nome", ""), "endereco": emp.get("endereco", ""), "bairro": emp.get("bairro_nome", ""), "telefone": emp.get("telefone", ""),
                 "site": (emp.get("contatos") or {}).get("site") or (emp.get("dica") or {}).get("site") or ""}
            guarda = {}
            e["site_defeito"] = checar_site(e["site"], guarda) if e["site"] else ""
            if e["site"] and not e["site_defeito"]:
                e["site_feito_em"] = data_do_site(e["site"], guarda.get("corpo", ""))[0]
                e["site_velocidade"] = velocidade_site(e) if corpo.get("velocidade") else None
            inicio = time.time()
            r = analise_local.analisar(e, guarda.get("corpo", ""), [], funda=True, mais_contatos=outscraper_contatos, buscar_google=outscraper_google)
            return self.responder_json({"ok": True, "segundos": round(time.time() - inicio, 1), "site_testado": e["site"], "defeito": e["site_defeito"], "antes": {k: emp.get(k) or (emp.get("contatos") or {}).get(k) for k in ("instagram", "whatsapp", "site_nota", "analise")}, "agora": r})
        if rota == "procurar-contato":
            return self.responder_json(procurar_contato_da_busca(str(corpo.get("place_id", "")), str(corpo.get("nome", ""))))
        if rota == "preparar":
            return self.preparar_com_ia(str(corpo.get("cnpj", "")))
        self.responder_json({"erro": "não encontrado"}, 404)

    def gravar_manuais(self, novas, fonte, razao, nicho=""):
        return gravar_manuais(novas, fonte, razao, nicho)

    def preparar_com_ia(self, cnpj):
        if not ID_VALIDO.match(cnpj):
            raise ErroIA("Empresa inválida.")
        todas = (ler_json(LISTA, None) or {"empresas": []})["empresas"] + ler_json(LEADS_MANUAIS, [])
        empresa = next((e for e in todas if e["cnpj"] == cnpj), None)
        if not empresa:
            raise ErroIA("Empresa não encontrada. Empresas vindas do Maps não podem ir para o site.")
        estado = ler_json(ESTADO, {}).get(cnpj, {})
        docs = ia.preparar_empresa(empresa, {k: v for k, v in estado.items() if k not in ("b", "m")})
        pasta = PREVIAS / cnpj
        pasta.mkdir(parents=True, exist_ok=True)
        # Nunca sobrescreve uma análise ou copy que já existe: a nova vai com sufixo
        salvos = []
        for nome, texto in (("analise", docs["analise_md"]), ("copy", docs["copy_md"]), ("posts", docs["posts_md"])):
            destino = pasta / f"{nome}.md"
            if destino.exists():
                destino = pasta / f"{nome}-ia-{datetime.now():%Y%m%d-%H%M}.md"
            destino.write_text(texto, encoding="utf-8")
            salvos.append(destino.name)
        self.responder_json({"ok": True, "arquivos": salvos})

    def criar_previa(self, corpo):
        cnpj = str(corpo.get("cnpj", ""))
        empresa = achar_empresa(cnpj, corpo.get("empresa")) if ID_VALIDO.match(cnpj) else None
        if not empresa:
            return self.responder_json({"erro": "empresa não encontrada"}, 404)
        pasta = PREVIAS / cnpj
        pasta.mkdir(parents=True, exist_ok=True)
        briefing = corpo.get("briefing") or {}
        (pasta / "index.html").write_text(gerador.gerar(empresa, briefing), encoding="utf-8")
        self.responder_json({
            "ok": True, "url": f"/previas/{cnpj}/", "gerada_em": datetime.now().isoformat(timespec="minutes"),
            "pendencias": gerador.pendencias(briefing),
        })

    def salvar_foto(self, corpo):
        cnpj, papel = str(corpo.get("cnpj", "")), corpo.get("papel")
        if not ID_VALIDO.match(cnpj) or papel not in PAPEIS:
            return self.responder_json({"erro": "foto inválida"}, 400)
        try:
            dados = base64.b64decode(corpo.get("base64", ""), validate=True)
        except ValueError:
            return self.responder_json({"erro": "foto inválida"}, 400)
        extensao = extensao_foto(dados)
        if not extensao or len(dados) > LIMITE_FOTO:
            return self.responder_json({"erro": "Use JPG, PNG ou WebP com até 12 MB"}, 400)
        pasta = PREVIAS / cnpj / "img"
        pasta.mkdir(parents=True, exist_ok=True)
        for antigo in pasta.glob(f"{papel}.*"):
            antigo.unlink()
        (pasta / f"{papel}{extensao}").write_bytes(dados)
        self.responder_json({"ok": True, "arquivo": f"{papel}{extensao}"})

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    DADOS.mkdir(parents=True, exist_ok=True)
    ultima = ler_json(ULTIMA_BUSCA, {})
    if ultima.get("estado") == "pronta":
        BUSCA.update(ultima)
        if not ler_json(HISTORICO_BUSCAS, []):
            guardar_no_historico(ultima)
    # fila de prévias: o que estava no meio quando o painel fechou volta para a fila
    for cnpj, item in fila_estado().items():
        if item.get("etapa") in ("análise", "layout"):
            fila_marcar(cnpj, etapa="na fila")
    for pasta in PREVIAS.iterdir() if PREVIAS.exists() else []:
        for a in ler_ajustes(pasta.name) if pasta.is_dir() else []:
            if a.get("etapa") == "fazendo":
                marcar_ajuste(pasta.name, a["id"], etapa="na fila")
    threading.Thread(target=completar_fotos, daemon=True).start()
    for _ in range(TRABALHOS_JUNTOS):
        threading.Thread(target=rodar_fila, daemon=True).start()
    threading.Thread(target=rodar_ajustes, daemon=True).start()
    AJUSTE_ACORDA.set()
    FILA_ACORDA.set()
    print(f"Painel aberto em http://localhost:{PORTA}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", PORTA), Painel).serve_forever()
