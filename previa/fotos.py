#!/usr/bin/env python3
"""Fotos reais da empresa para a prévia, sem IA.

De onde vêm: as fotos do lugar no Google Maps (pelo Outscraper, que também traz o horário e os serviços
cadastrados) e as imagens do site atual. Tudo vai para dados/previas/<código>/img/ e o que foi achado
fica em fotos.json, para o preenchedor escolher onde cada foto entra.

Custo: o Outscraper cobra por foto depois de 500 no mês. A conta fica em dados/outscraper-uso.json
(campo "fotos") e para antes do limite grátis.
"""
import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from html import unescape
from pathlib import Path

try:
    import certifi
    os.environ.setdefault("SSL_CERT_FILE", certifi.where())
except ImportError:
    pass

RAIZ = Path(__file__).resolve().parent.parent
DADOS = Path(os.environ.get("PROSPECCAO_DADOS", RAIZ / "dados"))
URL_OUTSCRAPER = os.environ.get("PROSPECCAO_URL_OUTSCRAPER", "https://api.app.outscraper.com")
LIMITE_FOTOS = int(os.environ.get("PROSPECCAO_LIMITE_FOTOS", 480))  # 500 grátis por mês, com folga
FOTOS_POR_EMPRESA = 12
NAVEGADOR = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 Chrome/130 Safari/537.36"}


class ErroFotos(Exception):
    pass


def _ler_json(caminho, padrao):
    try:
        return json.loads(Path(caminho).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return padrao


def _gravar_json(caminho, conteudo):
    Path(caminho).write_text(json.dumps(conteudo, ensure_ascii=False, indent=1), encoding="utf-8")


def _uso():
    uso = _ler_json(DADOS / "outscraper-uso.json", {})
    mes = datetime.now().strftime("%Y-%m")
    return uso if uso.get("mes") == mes else {"mes": mes, "lugares": 0}


def _baixar(url, limite=8_000_000, timeout=25):
    with urllib.request.urlopen(urllib.request.Request(url, headers=NAVEGADOR), timeout=timeout) as r:
        return r.headers.get("Content-Type", ""), r.read(limite)


def medidas(arquivo):
    """Largura e altura pela ferramenta sips do Mac (sem biblioteca de imagem)."""
    try:
        saida = subprocess.run(["sips", "-g", "pixelWidth", "-g", "pixelHeight", str(arquivo)], capture_output=True, text=True, timeout=20).stdout
        w = re.search(r"pixelWidth: (\d+)", saida)
        h = re.search(r"pixelHeight: (\d+)", saida)
        return (int(w.group(1)), int(h.group(1))) if w and h else (0, 0)
    except (OSError, subprocess.SubprocessError):
        return (0, 0)


def _salvar_imagem(conteudo, tipo, destino_sem_ext):
    ext = ".png" if "png" in tipo else ".webp" if "webp" in tipo else ".jpg"
    if conteudo[:3] == b"\xff\xd8\xff":
        ext = ".jpg"
    elif conteudo[:4] == b"\x89PNG":
        ext = ".png"
    elif conteudo[8:12] == b"WEBP":
        ext = ".webp"
    elif not tipo.startswith("image/"):
        return None
    arquivo = destino_sem_ext.with_suffix(ext)
    arquivo.write_bytes(conteudo)
    return arquivo


# ---------- Google Maps pelo Outscraper ----------
def outscraper_lugar(place_id, chave, limite=FOTOS_POR_EMPRESA, espera=300):
    """Pede as fotos do lugar (as do dono primeiro) e espera a resposta. Devolve o lugar com photos_data."""
    uso = _uso()
    if uso.get("fotos", 0) + limite > LIMITE_FOTOS:
        raise ErroFotos(f"Limite grátis de fotos do mês quase no fim ({uso.get('fotos', 0)} de {LIMITE_FOTOS}). Parei para não gerar cobrança.")
    cabecalho = {"X-API-KEY": chave}
    lugar = None
    for marcador in ("by_owner", "all"):
        q = urllib.parse.urlencode({"query": place_id, "photosLimit": limite, "limit": 1, "tag": marcador,
                                    "language": "pt-BR", "region": "BR", "async": "true"})
        try:
            pedido = json.load(urllib.request.urlopen(urllib.request.Request(f"{URL_OUTSCRAPER}/maps/photos-v3?{q}", headers=cabecalho), timeout=60))
            fim = time.time() + espera
            resposta = {"status": "Pending"}
            while resposta.get("status") == "Pending" and time.time() < fim:
                time.sleep(4)
                resposta = json.load(urllib.request.urlopen(urllib.request.Request(pedido["results_location"], headers=cabecalho), timeout=60))
        except urllib.error.HTTPError as erro:
            raise ErroFotos(f"O Outscraper recusou o pedido de fotos (código {erro.code}).")
        except (urllib.error.URLError, TimeoutError, KeyError, ValueError):
            raise ErroFotos("Não consegui falar com o Outscraper para pegar as fotos.")
        if resposta.get("status") != "Success":
            raise ErroFotos("O Outscraper demorou demais para mandar as fotos. Tente de novo daqui a pouco.")
        blocos = resposta.get("data") or [[]]
        achado = (blocos[0] or [None])[0] if isinstance(blocos[0], list) else blocos[0]
        uso = _uso()
        uso["fotos"] = uso.get("fotos", 0) + len((achado or {}).get("photos_data") or [])
        _gravar_json(DADOS / "outscraper-uso.json", uso)
        if achado and (lugar is None or len(achado.get("photos_data") or []) > len(lugar.get("photos_data") or [])):
            lugar = achado
        # o dono quase sempre sobe fotos da clínica; se ele subiu poucas, completa com as de todos
        if lugar and len(lugar.get("photos_data") or []) >= 6:
            break
        if _uso().get("fotos", 0) + limite > LIMITE_FOTOS:
            break
    return lugar or {}


def fotos_do_maps(place_id, pasta, chave):
    lugar = outscraper_lugar(place_id, chave)
    img = Path(pasta) / "img"
    img.mkdir(parents=True, exist_ok=True)
    saida = []
    for n, f in enumerate(lugar.get("photos_data") or []):
        if f.get("photo_source_video"):
            continue  # quadro de vídeo costuma sair borrado
        url = f.get("photo_url_big") or f.get("photo_url")
        if not url:
            continue
        url = re.sub(r"=w\d+-h\d+.*$", "=w1800-h1800-k-no", url) if "=w" in url else url + "=w1800-h1800-k-no"
        try:
            tipo, conteudo = _baixar(url)
        except Exception:
            continue
        arquivo = _salvar_imagem(conteudo, tipo, img / f"maps-{n + 1:02d}")
        if arquivo:
            w, h = medidas(arquivo)
            saida.append({"arquivo": arquivo.name, "origem": "Google Maps (Outscraper)", "w": w, "h": h,
                          "marcas": f.get("photo_tags") or [], "data": f.get("photo_date", "")})
    # horário, serviços e nota cadastrados no Google: o preenchedor usa (a nota vai marcada para confirmar)
    info = {k: lugar.get(k) for k in ("name", "address", "phone", "website", "rating", "reviews", "subtypes", "type",
                                     "working_hours", "logo", "photo", "location_link", "latitude", "longitude", "about")}
    _gravar_json(Path(pasta) / "maps.json", info)
    if lugar.get("logo") and not any(Path(pasta).glob("avatar.*")):
        logo = re.sub(r"/s\d+-p-k", "/s400-p-k", lugar["logo"])
        try:
            tipo, conteudo = _baixar(logo)
            _salvar_imagem(conteudo, tipo, Path(pasta) / "avatar")
        except Exception:
            pass
    return saida


# ---------- site atual ----------
PULAR = re.compile(r"(logo|icon|favicon|sprite|whats|wpp|instagram|facebook|banner-?text|placeholder|loading|pixel|avatar-default|seal|selo)", re.I)


def _imagens_da_pagina(url, html):
    achadas = []
    for padrao in (r'property=["\']og:image["\'][^>]*content=["\']([^"\']+)', r'content=["\']([^"\']+)["\'][^>]*property=["\']og:image',
                   r'<img[^>]+(?:data-src|data-lazy-src|src)=["\']([^"\']+)', r'srcset=["\']([^"\']+)',
                   r'url\(["\']?([^"\')]+\.(?:jpe?g|png|webp))'):
        for achado in re.findall(padrao, html, re.I):
            for parte in achado.split(","):
                candidato = unescape(parte.strip().split(" ")[0])
                if candidato and not candidato.startswith("data:") and re.search(r"\.(jpe?g|png|webp)(\?|$)", candidato, re.I):
                    achadas.append(urllib.parse.urljoin(url, candidato))
    vistos, saida = set(), []
    for a in achadas:
        chave = re.sub(r"-\d+x\d+(?=\.\w+$)", "", a.split("?")[0])  # WordPress: a mesma foto em vários tamanhos
        if chave not in vistos and not PULAR.search(a.rsplit("/", 1)[-1]):
            vistos.add(chave)
            saida.append(re.sub(r"-\d+x\d+(?=\.\w+(\?|$))", "", a))
    return saida


def fotos_do_site(url, pasta, maximo=10):
    if not url:
        return []
    url = url if url.startswith("http") else "https://" + url
    try:
        _, corpo = _baixar(url, 3_000_000, timeout=20)
    except Exception:
        return []
    html = corpo.decode("utf-8", "ignore")
    img = Path(pasta) / "img"
    img.mkdir(parents=True, exist_ok=True)
    saida = []
    for n, endereco in enumerate(_imagens_da_pagina(url, html)[:30]):
        try:
            tipo, conteudo = _baixar(endereco)
        except Exception:
            continue
        if len(conteudo) < 25_000:
            continue  # ícone, selo ou miniatura
        arquivo = _salvar_imagem(conteudo, tipo, img / f"site-{n + 1:02d}")
        if not arquivo:
            continue
        w, h = medidas(arquivo)
        if min(w, h) < 380:
            arquivo.unlink()
            continue
        saida.append({"arquivo": arquivo.name, "origem": f"site atual ({endereco})", "w": w, "h": h, "marcas": ["site"]})
        if len(saida) >= maximo:
            break
    return saida


def texto_do_site(url, limite=5000):
    """Texto corrido da página inicial do site atual (sem IA), para a copy partir do que a empresa já diz."""
    if not url or re.search(r"instagram\.com|facebook\.com|wa\.me|whatsapp", url, re.I):
        return ""
    url = url if url.startswith("http") else "https://" + url
    try:
        _, corpo = _baixar(url, 2_000_000, timeout=20)
    except Exception:
        return ""
    html_ = corpo.decode("utf-8", "ignore")
    html_ = re.sub(r"(?is)<(script|style|noscript|svg|nav|footer)[^>]*>.*?</\1>", " ", html_)
    texto = unescape(re.sub(r"<[^>]+>", " ", html_))
    return re.sub(r"\s+", " ", texto).strip()[:limite]


def juntar_fotos(empresa, pasta, chave_outscraper=""):
    """Baixa o que der das duas fontes e grava fotos.json. Nunca apaga foto que já está na pasta."""
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    registro = _ler_json(pasta / "fotos.json", {"fotos": [], "avisos": []})
    ja = {f["arquivo"] for f in registro["fotos"]}
    avisos = []
    if chave_outscraper and empresa.get("place_id") and not (pasta / "maps.json").exists():
        try:
            registro["fotos"] += [f for f in fotos_do_maps(empresa["place_id"], pasta, chave_outscraper) if f["arquivo"] not in ja]
        except ErroFotos as erro:
            avisos.append(str(erro))
    elif not chave_outscraper:
        avisos.append("Sem a chave do Outscraper: as fotos do Google Maps não foram baixadas.")
    site = (empresa.get("contatos") or {}).get("site") or (empresa.get("dica") or {}).get("site") or ""
    if site and not any(f["arquivo"].startswith("site-") for f in registro["fotos"]):
        registro["fotos"] += [f for f in fotos_do_site(site, pasta) if f["arquivo"] not in ja]
    # fotos que já estavam na pasta (baixadas à mão ou por prévias antigas) também valem
    ja = {f["arquivo"] for f in registro["fotos"]}
    for arquivo in sorted((pasta / "img").glob("*")) if (pasta / "img").exists() else []:
        if arquivo.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp") and arquivo.name not in ja:
            w, h = medidas(arquivo)
            if min(w, h) >= 300:
                registro["fotos"].append({"arquivo": arquivo.name, "origem": "pasta da prévia", "w": w, "h": h, "marcas": []})
    registro["avisos"] = avisos
    _gravar_json(pasta / "fotos.json", registro)
    return registro
