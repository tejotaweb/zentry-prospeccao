#!/usr/bin/env python3
"""Monta a prévia de uma empresa a partir de um modelo pronto (previa/modelos/), sem chamar IA.

Entra: os dados da empresa (leads-manuais.json), as fotos reais em img/ (fotos.json), maps.json (horário,
serviços e nota do Google, pelo Outscraper) e o logo/avatar. Sai: dados/previas/<código>/index.html e layout.md.

Regras: nada inventado. O que é da empresa e não veio dos dados fica marcado [CONFIRMAR]. A receita de
abertura gira (A, B, C, D, E) para duas empresas seguidas não saírem iguais.

Uso no terminal: python3 previa/preencher.py <código> [receita]
"""
import colorsys
import html
import json
import re
import subprocess
import sys
import tempfile
import time
import unicodedata
import urllib.parse
from datetime import datetime
from pathlib import Path

PASTA = Path(__file__).resolve().parent
sys.path.insert(0, str(PASTA))
from nichos import NICHOS, descobrir_nicho, sem_acento  # noqa: E402

MODELOS = PASTA / "modelos"
RECEITAS = {"A": "A-oralyn.html", "B": "B-dentora.html", "C": "C-experts.html", "D": "D-vivachat.html", "E": "E-agenda.html",
            "F": "F-bemestar.html", "G": "G-marca.html", "H": "H-bloco-cor.html"}
FOTOS_MINIMAS = {"A": 1, "B": 2, "C": 5, "D": 4, "E": 1, "F": 3, "G": 3, "H": 3}
DIAS = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]
DIAS_CURTOS = {"segunda-feira": "Seg", "terça-feira": "Ter", "quarta-feira": "Qua", "quinta-feira": "Qui", "sexta-feira": "Sex", "sábado": "Sáb", "domingo": "Dom"}

# Ícones em traço fino (estilo Lucide), todos em 24x24
ICONES = {
    "seta": '<path d="M7 17 17 7M8 7h9v9"/>',
    "seta-dir": '<path d="M5 12h14M13 6l6 6-6 6"/>',
    "seta-esq": '<path d="M19 12H5M11 6l-6 6 6 6"/>',
    "seta-baixo": '<path d="M12 5v14M6 13l6 6 6-6"/>',
    "mais": '<path d="M12 5v14M5 12h14"/>',
    "check": '<path d="m5 12 4.5 4.5L19 7"/>',
    "whats": '<path d="M3.5 20.5 5 16a8.5 8.5 0 1 1 3.2 3.1z"/><path d="M9 9.2c.2 2.6 3.1 5.6 5.8 5.8l1.2-1.4-1.9-1-1 .9c-1-.4-2.1-1.5-2.5-2.5l.9-1-1-1.9z"/>',
    "telefone": '<path d="M5 4h3.5l1.7 4.2-2 1.4a11 11 0 0 0 6.2 6.2l1.4-2L20 15.5V19a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2z"/>',
    "pino": '<path d="M12 21s-7-6.2-7-11.5A7 7 0 0 1 19 9.5C19 14.8 12 21 12 21z"/><circle cx="12" cy="9.5" r="2.5"/>',
    "relogio": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "calendario": '<rect x="3.5" y="5" width="17" height="15" rx="3"/><path d="M8 3v4M16 3v4M3.5 10h17"/>',
    "insta": '<rect x="3.5" y="3.5" width="17" height="17" rx="5"/><circle cx="12" cy="12" r="4"/><circle cx="17.2" cy="6.8" r=".6" fill="currentColor"/>',
    "estrela": '<path d="m12 3.5 2.6 5.4 5.9.8-4.3 4.1 1 5.8L12 16.8l-5.2 2.8 1-5.8L3.5 9.7l5.9-.8z"/>',
    "escudo": '<path d="M12 3 5 6v5.5c0 4.3 3 7.8 7 9.5 4-1.7 7-5.2 7-9.5V6z"/><path d="m9 12 2.2 2.2L15.5 10"/>',
    "brilho": '<path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M6 18l2.5-2.5M15.5 8.5 18 6"/>',
    "dente": '<path d="M7.5 3.5c-2.3 0-4 1.8-4 4.4 0 2.3 1 3.9 1.5 6.3.5 2.4.9 6.3 2.6 6.3 1.6 0 1.7-4.6 4.4-4.6s2.8 4.6 4.4 4.6c1.7 0 2.1-3.9 2.6-6.3.5-2.4 1.5-4 1.5-6.3 0-2.6-1.7-4.4-4-4.4-1.8 0-2.9 1-4.5 1s-2.7-1-4.5-1z"/>',
    "alinha": '<path d="M4 8h16M4 16h16"/><circle cx="8" cy="8" r="2"/><circle cx="16" cy="16" r="2"/>',
    "sol": '<circle cx="12" cy="12" r="4"/><path d="M12 2.5v2M12 19.5v2M2.5 12h2M19.5 12h2M5.3 5.3l1.4 1.4M17.3 17.3l1.4 1.4M5.3 18.7l1.4-1.4M17.3 6.7l1.4-1.4"/>',
    "busca": '<circle cx="11" cy="11" r="6.5"/><path d="m20 20-4.2-4.2"/>',
    "conversa": '<path d="M4 5h16v11H9l-5 4z"/><path d="M8 10h8M8 13h5"/>',
    "lista": '<path d="M9 6h11M9 12h11M9 18h11"/><circle cx="4.5" cy="6" r="1"/><circle cx="4.5" cy="12" r="1"/><circle cx="4.5" cy="18" r="1"/>',
    "coracao": '<path d="M12 20s-7.5-4.6-7.5-10.2A4.3 4.3 0 0 1 12 7.2a4.3 4.3 0 0 1 7.5 2.6C19.5 15.4 12 20 12 20z"/>',
    "bisturi": '<path d="M20 4 9 15l-3 1 1-3L18 2z"/><path d="M4 20h7"/>',
    "raio": '<path d="M13 3 5 13h6l-1 8 8-10h-6z"/>',
    "gota": '<path d="M12 3.5s6 6.4 6 10.5a6 6 0 0 1-12 0c0-4.1 6-10.5 6-10.5z"/>',
    "regua": '<rect x="2.5" y="8" width="19" height="8" rx="2"/><path d="M7 8v3M11 8v4M15 8v3M19 8v4"/>',
    "video": '<rect x="3" y="6" width="13" height="12" rx="3"/><path d="m16 10.5 5-3v9l-5-3"/>',
    "repete": '<path d="M4 12a8 8 0 0 1 13.7-5.6L20 9M20 4v5h-5M20 12a8 8 0 0 1-13.7 5.6L4 15M4 20v-5h5"/>',
    "atividade": '<path d="M3 12h4l2.5-6 5 12 2.5-6h4"/>',
    "documento": '<path d="M6 3h8l4 4v14H6z"/><path d="M14 3v4h4M9 12h6M9 16h6"/>',
    "caneta": '<path d="m15 4 5 5L9 20H4v-5z"/>',
    "maleta": '<rect x="3" y="7" width="18" height="13" rx="3"/><path d="M9 7V5h6v2M3 13h18"/>',
    "balanca": '<path d="M12 4v16M7 20h10M5 8h14M5 8l-2.5 6a3 3 0 0 0 5 0zM19 8l-2.5 6a3 3 0 0 0 5 0z"/>',
    "lua": '<path d="M19 14.5A7.5 7.5 0 1 1 9.5 5 6 6 0 0 0 19 14.5z"/>',
    "bussola": '<circle cx="12" cy="12" r="9"/><path d="m15.5 8.5-2 5-5 2 2-5z"/>',
    "usuarios": '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c.6-3.6 3.2-5.5 6.5-5.5s5.9 1.9 6.5 5.5"/><path d="M16 4.6a3.5 3.5 0 0 1 0 6.8M18 14.8c2 .7 3.2 2.4 3.5 5.2"/>',
    "predio": '<path d="M4 21V5l8-2v18M12 21V9l8 2v10M2 21h20M7 8h2M7 12h2M7 16h2M15 13h2M15 17h2"/>',
    "menu": '<path d="M4 7h16M4 12h16M4 17h10"/>',
    "folha": '<path d="M5 19c0-8 5-14 15-14 0 10-6 15-14 15"/><path d="M5 19 13 11"/>',
    "premio": '<circle cx="12" cy="9" r="5.5"/><path d="m8.5 13.5-1.5 7 5-2.5 5 2.5-1.5-7"/>',
    "casa": '<path d="M3 11 12 4l9 7M5.5 9.5V20h13V9.5"/><path d="M10 20v-5h4v5"/>',
    "acessivel": '<circle cx="12" cy="4.5" r="1.8"/><path d="M5 8.5h14M12 8.5V14l-3.5 6.5M12 14l3.5 6.5"/>',
}


def e(texto):
    return html.escape(str(texto or ""), quote=True)


def icone(nome, classe="ico"):
    return f'<svg class="{classe}" viewBox="0 0 24 24" aria-hidden="true">{ICONES.get(nome, ICONES["check"])}</svg>'


def confirmar(texto="confirmar"):
    return f'<mark class="confirmar">{e(texto)}</mark>'


def ler_json(caminho, padrao):
    try:
        return json.loads(Path(caminho).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return padrao


# ---------- cor da marca, medida no logo ----------
def _pixels_bmp(arquivo):
    """Reduz a imagem a 48x48 pelo sips do Mac e lê os pixels do BMP (sem biblioteca de imagem)."""
    with tempfile.TemporaryDirectory() as tmp:
        saida = Path(tmp) / "p.bmp"
        subprocess.run(["sips", "-s", "format", "bmp", "-z", "48", "48", str(arquivo), "--out", str(saida)],
                       capture_output=True, timeout=30)
        dados = saida.read_bytes() if saida.exists() else b""
    if dados[:2] != b"BM":
        return []
    inicio = int.from_bytes(dados[10:14], "little")
    largura = int.from_bytes(dados[18:22], "little", signed=True)
    altura = abs(int.from_bytes(dados[22:26], "little", signed=True))
    bits = int.from_bytes(dados[28:30], "little")
    passo = bits // 8
    if passo not in (3, 4):
        return []
    linha = (largura * passo + 3) & ~3
    px = []
    for y in range(altura):
        for x in range(largura):
            i = inicio + y * linha + x * passo
            b, g, r = dados[i], dados[i + 1], dados[i + 2]
            a = dados[i + 3] if passo == 4 else 255
            if a > 200:
                px.append((r, g, b))
    return px


def tom_de_pele(arquivo):
    """Parte da foto em tom de pele/boca (0 a 1). Close de boca, antes e depois e procedimento passam de 0,4;
    foto de consultório, recepção e fachada fica abaixo. Sem IA: só a cor dos pixels."""
    px = _pixels_bmp(arquivo)
    if not px:
        return 0.0
    pele = 0
    for r, g, b in px:
        h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
        if (h < 0.1 or h > 0.85) and s > 0.18 and 0.2 < l < 0.88:
            pele += 1
    return round(pele / len(px), 3)


ROSTO_BIN = Path(__file__).resolve().parent / "bin" / "rosto"


def achar_rostos(arquivos):
    """Rostos e texto de várias fotos de uma vez, pelo Vision do Mac (bin/rosto).
    {arquivo: {"rostos": [{x,y,w,h}] em 0 a 1 do topo, "texto": parte da imagem coberta por texto}}"""
    if not arquivos or not ROSTO_BIN.exists():
        return {}
    try:
        r = subprocess.run([str(ROSTO_BIN), *map(str, arquivos)], capture_output=True, text=True, timeout=120)
    except (subprocess.TimeoutExpired, OSError):
        return {}
    saida = {}
    for linha in r.stdout.splitlines():
        try:
            d = json.loads(linha)
            saida[d["arquivo"]] = {"rostos": d["rostos"], "texto": round(d.get("texto", 0), 3)}
        except (ValueError, KeyError):
            pass
    return saida


def foco_da_foto(f):
    """Onde a foto deve "olhar" quando é cortada: no maior rosto (um pouco acima do meio dele) ou no centro."""
    if isinstance(f.get("foco"), list) and len(f["foco"]) == 2:
        return tuple(f["foco"])  # escolhido por ele no editor: vale mais que o rosto achado
    rostos = f.get("rostos") or []
    if not rostos:
        return None
    g = max(rostos, key=lambda q: q["w"] * q["h"])
    return round((g["x"] + g["w"] / 2) * 100), round(max(0, g["y"] + g["h"] * 0.45) * 100)


# ramos em que close de paciente e antes e depois são proibidos pelo conselho (CFO, CFM, estética)
RAMOS_SEM_PROCEDIMENTO = {"dentista", "estetica", "medico", "fisioterapia", "nutricionista"}
LIMITE_PELE = 0.4


def cor_do_logo(arquivo):
    """A cor mais marcante do logo: frequente e saturada, sem branco, preto nem cinza."""
    try:
        px = _pixels_bmp(arquivo)
    except (OSError, subprocess.SubprocessError):
        return None
    baldes = {}
    for r, g, b in px:
        h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
        if l > .9 or l < .12 or s < .22:
            continue
        chave = (round(h * 24) % 24, round(l * 6), round(s * 4))
        soma = baldes.setdefault(chave, [0, 0, 0, 0])
        soma[0] += r; soma[1] += g; soma[2] += b; soma[3] += 1
    if not baldes or sum(v[3] for v in baldes.values()) < max(12, len(px) * .015):
        return None
    def peso(v):
        r, g, b = v[0] / v[3], v[1] / v[3], v[2] / v[3]
        _, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
        return v[3] * (0.4 + s) * (1 - abs(l - .45))
    melhor = max(baldes.values(), key=peso)
    return "#%02x%02x%02x" % tuple(round(c / melhor[3]) for c in melhor[:3])


def tom(cor, luz=None, saturacao=None, fator_s=None):
    r, g, b = (int(cor[i:i + 2], 16) / 255 for i in (1, 3, 5))
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    if fator_s is not None:
        s = min(1, s * fator_s)
    r, g, b = colorsys.hls_to_rgb(h, l if luz is None else luz, s if saturacao is None else saturacao)
    return "#%02x%02x%02x" % (round(r * 255), round(g * 255), round(b * 255))


def luminancia(cor):
    canais = [int(cor[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    canais = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in canais]
    return 0.2126 * canais[0] + 0.7152 * canais[1] + 0.0722 * canais[2]


def paleta(cor):
    r, g, b = (int(cor[i:i + 2], 16) / 255 for i in (1, 3, 5))
    _, l, s = colorsys.rgb_to_hls(r, g, b)
    principal = tom(cor, min(max(l, .3), .56), max(s, .35))
    return {
        "--cor": principal,
        "--sobre": "#ffffff" if luminancia(principal) < .42 else "#111111",
        "--cor-forte": tom(cor, min(l, .32), max(s, .35)),
        "--cor-luz": tom(cor, .72, max(s, .45)),
        "--claro": tom(cor, .95, min(max(s, .25), .55)),
        "--medio": tom(cor, .86, min(max(s, .25), .45)),
        "--tinta": tom(cor, .1, min(s, .3)),
        "--fundo2": tom(cor, .965, min(s, .14)),
        "--linha": "color-mix(in srgb, var(--tinta) 11%, transparent)",
        "--cinza": tom(cor, .42, .06),
        "--fundo": "#ffffff",
    }


# ---------- dados da empresa ----------
def nome_curto(nome):
    """'Consultório Odontológico Dra. Maria Souza - Cidade UF' vira 'Dra. Maria Souza'."""
    nome = re.split(r"\s+[-|–·]\s+", str(nome or "").strip())[0].strip()
    pessoa = re.search(r"\b(Dra?\.?\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wáéíóúâêôãõç]+(?:\s+(?:d[aeo]s?\s+)?[A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wáéíóúâêôãõç]+)?)", nome)
    if pessoa and len(nome.split()) > 4:
        return pessoa.group(1).replace("Dra ", "Dra. ").replace("Dr ", "Dr. ")
    for prefixo in ("Consultório Odontológico ", "Clínica Odontológica ", "Consultório ", "Clínica "):
        if nome.startswith(prefixo) and pessoa:
            return nome[len(prefixo):]
    return nome[:40] if nome.isupper() is False else nome.title()[:40]


def profissional_do_nome(nome):
    achado = re.search(r"\b(Dra?)\.?\s+([A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wáéíóúâêôãõç]+(?:\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wáéíóúâêôãõç]+)?)", str(nome or ""))
    return f"{achado.group(1)}. {achado.group(2)}" if achado else ""


def horario_falado(resumo):
    """'Seg a Sex · 09h às 19h' vira 'De segunda a sexta, das 09h às 19h'."""
    if not resumo:
        return ""
    dias = {"Seg": "segunda", "Ter": "terça", "Qua": "quarta", "Qui": "quinta", "Sex": "sexta", "Sáb": "sábado", "Dom": "domingo"}
    partes = resumo.split(" · ")
    dia = re.sub(r"\b(" + "|".join(dias) + r")\b", lambda m: dias[m.group(1)], partes[0])
    texto = ("De " + dia) if " a " in dia else dia.capitalize()
    return texto + (f", das {partes[1]}" if len(partes) > 1 and "às" in partes[1] else (f", {partes[1]}" if len(partes) > 1 else ""))


def cidade_do_endereco(endereco):
    """'Av. dos Andradas, 3323 - Santa Tereza, Belo Horizonte - MG, 31010-560' vira 'Belo Horizonte'."""
    achado = re.search(r",\s*([^,\d]+?)\s*-\s*[A-Z]{2}\b", endereco or "")
    return achado.group(1).strip() if achado else "Goiânia"


def link_whatsapp(*numeros):
    for numero in numeros:
        d = re.sub(r"\D", "", str(numero or ""))
        if d.startswith("55") and len(d) in (12, 13):
            d = d[2:]
        if len(d) == 11 and d[2] == "9":  # celular com DDD
            return "https://wa.me/55" + d
    return ""


def arroba(insta):
    insta = str(insta or "").strip().rstrip("/")
    if not insta:
        return ""
    insta = insta.split("instagram.com/")[-1].split("?")[0].strip("/")
    usuario = re.match(r"@?([A-Za-z0-9_.]{2,30})", insta)  # só o @: anotações do tipo "(perfil não aberto)" ficam de fora
    return "@" + usuario.group(1).rstrip(".") if usuario else ""


def horario_tabela(horas):
    linhas = []
    for dia in DIAS:
        valor = (horas or {}).get(dia)
        if valor is None:
            continue
        texto = ", ".join(valor) if isinstance(valor, list) else str(valor)
        texto = texto.replace(":00", "h").replace("-", " às ")
        linhas.append((dia, "Fechado" if "fechad" in texto.lower() else texto))
    return linhas


def horario_resumo(linhas):
    abertos = [(d, h) for d, h in linhas if h != "Fechado"]
    if not abertos:
        return ""
    iguais = [d for d, h in abertos if h == abertos[0][1]]
    if len(iguais) >= 3:
        return f"{DIAS_CURTOS[iguais[0]]} a {DIAS_CURTOS[iguais[-1]]} · {abertos[0][1]}" if len(iguais) == len(abertos) or len(iguais) > 2 else ""
    return f"{len(abertos)} dias por semana"


class Dados:
    def __init__(self, empresa, pasta):
        self.emp = empresa
        self.pasta = Path(pasta)
        self.maps = ler_json(self.pasta / "maps.json", {})
        self.nicho_chave = descobrir_nicho(empresa, self.maps)
        self.endereco = self.maps.get("address") or empresa.get("endereco", "")
        self.cidade = cidade_do_endereco(self.endereco)
        # textos do nicho com a cidade certa; por cima, a copy própria da empresa (copy.json), quando existir
        self.n = json.loads(json.dumps(NICHOS[self.nicho_chave], ensure_ascii=False).replace("Goiânia", self.cidade))
        uf = (re.search(r"-\s*([A-Z]{2})\b,?\s*(\d{5}-?\d{3})?\s*$", self.endereco or "") or re.search(r"-\s*([A-Z]{2})\b", self.endereco or ""))
        self.uf = uf.group(1) if uf else "GO"
        # conselho com a UF do endereço (CRO-MG, OAB/MG); os regionais por número (CRN-1, CRP-09) ficam sem número fora de GO
        cons = self.n.get("conselho") or ""
        cons = re.sub(r"([-/])(UF|GO)$", lambda m: m.group(1) + self.uf, cons)
        if self.uf != "GO":
            cons = re.sub(r"-\d+$", "", cons)
        self.n["conselho"] = cons
        self.palavra_servicos = self.n.get("palavra_servicos") or ("Tratamentos" if self.nicho_chave == "dentista" else "Serviços")
        self.texto_site = (self.pasta / "texto-site.txt").read_text(encoding="utf-8") if (self.pasta / "texto-site.txt").exists() else ""
        self.nome_completo = empresa.get("nome", "")
        self.nome = nome_curto(self.nome_completo)
        self.bairro = empresa.get("bairro_nome") or self.cidade
        contatos = empresa.get("contatos") or {}
        self.whats = link_whatsapp(contatos.get("whatsapp"), empresa.get("telefone"), self.maps.get("phone"))
        self.telefone = contatos.get("whatsapp") or empresa.get("telefone") or self.maps.get("phone") or ""
        self.insta = arroba(contatos.get("instagram") or (empresa.get("dica") or {}).get("instagram"))
        self.maps_link = contatos.get("google_maps") or self.maps.get("location_link") or ""
        self.profissional = profissional_do_nome(self.nome_completo)
        self.horario = horario_tabela(self.maps.get("working_hours"))
        self.horario_resumo = horario_resumo(self.horario)
        nota = self.maps.get("rating") or (empresa.get("dica") or {}).get("nota")
        try:
            self.nota = float(str(nota).replace(",", ".")) if nota else None
        except ValueError:
            self.nota = None
        avaliacoes = self.maps.get("reviews") or (empresa.get("dica") or {}).get("avaliacoes")
        self.avaliacoes = int(re.sub(r"\D", "", str(avaliacoes)) or 0) if avaliacoes else 0
        self.servicos, self.servicos_do_google = self._servicos()
        self.fotos = self._fotos()
        self.avatar = next((f.name for f in sorted(self.pasta.glob("avatar.*")) if f.suffix in (".jpg", ".png", ".webp")), "")
        cor = cor_do_logo(self.pasta / self.avatar) if self.avatar else None
        self.cor_medida = bool(cor)
        self.paleta = paleta(cor or self.n["cor"])
        # copy própria: a do copy.json (se existir) ou a montada aqui com os fatos reais, sem IA e sem gastar token
        self.copy = ler_json(self.pasta / "copy.json", {}) or self._copy_dos_fatos()
        self._aplicar_copy()

    def _copy_dos_fatos(self):
        """Textos desta empresa a partir do que é fato (Google, nome, site atual). Nada inventado."""
        quem = self.profissional or ""
        com_quem = (("a " if quem.startswith("Dra") else "o ") + quem) if quem else "a equipe"
        horas = horario_falado(self.horario_resumo)
        # especialidade só onde ela é o que o cliente procura (Ortodontia, Dermatologia); nos outros, o nome do ramo
        area = self.servicos[0][0] if self.servicos_do_google and self.servicos and self.nicho_chave in ("dentista", "medico", "generico") else self.n["nome"]
        lista = [s[0] for s in self.servicos[:3]] if self.servicos_do_google else []
        onde = f"no {self.bairro}" if self.bairro != self.cidade else "em " + self.cidade
        # 03/11: ele reprovou o título montado com os fatos ("Advocacia no Centro, em linguagem clara."): longo, quebrava em 4 linhas.
        # A abertura usa só as frases curtas do nicho; bairro, cidade e serviços vão no texto de apoio.
        curtos = [list(t) for t in self.n["titulos"] if len(t[0] + t[1]) <= 42] or [list(t) for t in self.n["titulos"]]
        titulos = curtos
        lista = lista[:1] + [x[0].lower() + x[1:] for x in lista[1:]]
        frase_areas = (", ".join(lista[:-1]) + " e " + lista[-1]) if len(lista) > 1 else area
        sub = f"{frase_areas} {onde}, em {self.cidade}." if self.bairro != self.cidade else f"{frase_areas} em {self.cidade}."
        if horas:
            sub += f" Atendimento {horas[0].lower() + horas[1:]}."
        sub += f" Fale com {com_quem} pelo WhatsApp."
        forte, resto = self.n["sobre"]
        if self.nota and self.avaliacoes >= 10:
            resto = resto.rstrip() + f" Hoje são {self.avaliacoes} avaliações no Google, com nota {str(self.nota).replace('.', ',')}."
        faq = [list(f) for f in self.n["faq"]][:3]
        if self.horario_resumo:
            faq.insert(1, ["Quais os dias e horários?", f"{horas}. Confirme o melhor horário pelo WhatsApp."])
        sobre_g = self.maps.get("about") or {}
        acesso = [i for g in sobre_g.values() if isinstance(g, dict) for i, sim in g.items() if sim is True and "acessibilidade" in i.lower()]
        if acesso:
            partes = [a.split(" com acessibilidade")[0].lower() for a in acesso[:4]]
            juntas = ", ".join(partes[:-1]) + " e " + partes[-1] if len(partes) > 1 else partes[0]
            faq.append([f"O {self.n['lugar']} tem acessibilidade?", f"Sim. Segundo o Google, {juntas} têm acesso para cadeira de rodas."])
        t, c = self.n["chamada"]
        return {"titulos": titulos, "subtitulo": sub, "sobre": [forte, resto], "faq": faq,
                "chamada": [t, c.rstrip(".") + f", {onde}."] if quem == "" else [t, f"Chame {com_quem} no WhatsApp e escolha o melhor horário."],
                "abre_whats": f"Olá! Vi o site e quero agendar uma avaliação{' com ' + quem if quem else ''}."}

    def _aplicar_copy(self):
        c = self.copy
        if not c:
            return
        par = lambda x: isinstance(x, (list, tuple)) and len(x) == 2 and all(isinstance(i, str) and i.strip() for i in x)
        titulos = [t for t in c.get("titulos") or [] if par(t)]
        if titulos:
            self.n["titulos"] = titulos
        for chave in ("subtitulo", "botao", "abre_whats"):
            if isinstance(c.get(chave), str) and c[chave].strip():
                self.n[chave] = c[chave].strip().replace("{", "(").replace("}", ")")
        for chave in ("sobre", "chamada"):
            if par(c.get(chave)):
                self.n[chave] = list(c[chave])
        passos = [p for p in c.get("passos") or [] if p.get("titulo") and p.get("texto")]
        if len(passos) >= 3:
            icones = [p[2] for p in self.n["passos"]] + ["lista"] * 3
            self.n["passos"] = [[p["titulo"], p["texto"], icones[i]] for i, p in enumerate(passos[:3])]
        faq = [(f["pergunta"], f["resposta"]) if isinstance(f, dict) else tuple(f) for f in c.get("faq") or []]
        faq = [f for f in faq if len(f) == 2 and f[0] and f[1]]
        if len(faq) >= 3:
            self.n["faq"] = faq[:5]
        proprios = [[s.get("nome", "").strip(), s.get("texto", "").strip(), s.get("icone") if s.get("icone") in ICONES else "busca"]
                    for s in c.get("servicos") or [] if s.get("nome") and s.get("texto")]
        if len(proprios) >= 3:
            self.servicos = proprios[:6]

    def _servicos(self):
        subtipos = [s.strip() for s in str(self.maps.get("subtypes") or "").split(",") if s.strip()]
        subtipos += [self.nome_completo, self.texto_site[:3000]]
        achados, nomes = [], set()
        for sub in subtipos:
            alvo = sem_acento(sub)
            for termo, servico in self.n["subtipos"]:
                if sem_acento(termo) in alvo and servico[0] not in nomes:
                    nomes.add(servico[0])
                    achados.append(servico)
                    break
        if achados:
            # completa com os do nicho que fazem sentido para todos (avaliação, prevenção), até 6
            for s in self.n["servicos"]:
                if len(achados) >= 6:
                    break
                # dentista: só os de base (avaliação, prevenção); outros ramos completam até 4 com a lista do ramo
                if s[0] not in nomes and (s[2] in ("busca", "brilho") or (self.nicho_chave != "dentista" and len(achados) < 4)):
                    achados.append(s)
                    nomes.add(s[0])
            return achados[:6], len(achados) >= 1
        if self.n["servicos"]:
            return list(self.n["servicos"])[:6], False
        proprios = [[sub, "Fale pelo WhatsApp para saber como funciona.", "check"]
                    for sub in subtipos[:-2][:6]]
        return (proprios or [["Atendimento", "Fale pelo WhatsApp e conte o que você precisa.", "conversa"]]), bool(proprios)

    def _fotos(self):
        registro = ler_json(self.pasta / "fotos.json", {"fotos": []})
        fotos = [f for f in registro.get("fotos", []) if (self.pasta / "img" / f["arquivo"]).exists() and min(f.get("w", 0), f.get("h", 0)) >= 300]
        # 03/11: tira close de boca e antes e depois (o conselho proíbe) e põe as fotos do espaço primeiro
        mudou = False
        for f in fotos:
            if "pele" not in f:
                f["pele"] = tom_de_pele(self.pasta / "img" / f["arquivo"])
                mudou = True
        sem_rosto = [f for f in fotos if "rostos" not in f or "texto" not in f]
        if sem_rosto:
            achados = achar_rostos([self.pasta / "img" / f["arquivo"] for f in sem_rosto])
            for f in sem_rosto:
                a = achados.get(f["arquivo"], {})
                f["rostos"], f["texto"] = a.get("rostos", []), a.get("texto", 0)
            mudou = mudou or bool(achados)
        if mudou:
            try:
                (self.pasta / "fotos.json").write_text(json.dumps(registro, ensure_ascii=False, indent=1), encoding="utf-8")
            except OSError:
                pass
        if self.nicho_chave in RAMOS_SEM_PROCEDIMENTO:
            limpas = [f for f in fotos if f["pele"] < LIMITE_PELE]
            self.fotos_tiradas = len(fotos) - len(limpas)
            fotos = limpas
        else:
            self.fotos_tiradas = 0
        # pessoa = foto com rosto de verdade e de bom tamanho (03/11: a marca "people" do Google trazia close de boca)
        def retrato_bom(f):
            rs = f.get("rostos") or []
            return any(0.12 <= q["h"] <= 0.4 and q["y"] >= 0.06 and q["y"] + q["h"] <= 0.97 for q in rs)

        def close_cortado(f):  # rosto enorme ou batendo na borda: selfie cortada, close de boca (03/11, foto do Izaias)
            return any(q["h"] > 0.4 or (q["h"] >= 0.2 and q["y"] < 0.06) for q in f.get("rostos") or [])
        # post ou panfleto (5% ou mais da imagem com texto) também sai: não é foto do lugar nem de quem atende
        cortadas = [f for f in fotos if close_cortado(f) or f.get("texto", 0) >= 0.05]
        fotos = [f for f in fotos if f not in cortadas]
        pessoas = [f for f in fotos if retrato_bom(f)]
        # retrato bom primeiro: uma pessoa só, rosto de tamanho médio
        pessoas.sort(key=lambda f: (len(f.get("rostos") or []) != 1, -max(q["h"] for q in f["rostos"])))
        fachada = [f for f in fotos if "front" in f.get("marcas", []) and f not in pessoas]
        ambiente = [f for f in fotos if f not in pessoas and f not in fachada and "food" not in f.get("marcas", [])]
        outras = [f for f in fotos if "food" in f.get("marcas", [])]
        self.fotos_tiradas += len(cortadas)  # close cortado fica fora (aparece no resumo)
        # foto grande e deitada primeiro: é a que segura a abertura
        ambiente.sort(key=lambda f: (f.get("pele", 0) >= 0.25, -(f["w"] >= f["h"]), -(f["w"] * f["h"])))
        fachada.sort(key=lambda f: -(f["w"] * f["h"]))
        return {"ambiente": ambiente, "pessoas": pessoas, "fachada": fachada, "outras": outras,
                "todas": ambiente + fachada + pessoas + outras}

    def url_foto(self, n, grupo="todas"):
        """Foto n (começa em 0) do grupo, girando quando acaba: com poucas fotos, a mesma volta em outro recorte."""
        lista = self.fotos.get(grupo) or self.fotos["todas"]
        if not lista:
            return self.sem_foto()
        return "img/" + urllib.parse.quote(lista[n % len(lista)]["arquivo"])

    def retrato(self):
        return self.url_foto(0, "pessoas") if self.fotos["pessoas"] else (f"{self.avatar}" if self.avatar else self.url_foto(1))

    def sem_foto(self):
        cor = self.paleta["--cor"].lstrip("#")
        iniciais = "".join(p[0] for p in self.nome.replace("Dra.", "").replace("Dr.", "").split()[:2]).upper()
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 500"><rect width="400" height="500" fill="#{cor}"/>'
               f'<text x="50%" y="54%" font-family="sans-serif" font-size="120" fill="white" fill-opacity=".85" text-anchor="middle">{e(iniciais)}</text></svg>')
        return "data:image/svg+xml," + urllib.parse.quote(svg)


# ---------- pedaços comuns ----------
class Montador:
    def __init__(self, dados, receita):
        self.d = dados
        self.receita = receita
        self.n = dados.n
        self.uso_fotos = 0

    def botao(self, texto=None, classe="", destino=None, ico="seta"):
        destino = destino or self.d.whats or "#contato"
        alvo = ' target="_blank" rel="noopener"' if destino.startswith("http") else ""
        return f'<a class="botao {classe}" href="{e(destino)}"{alvo}>{e(texto or self.n["botao"])}<span class="seta">{icone(ico)}</span></a>'

    def whats_link(self):
        return self.d.whats + "?text=" + urllib.parse.quote(self.n["abre_whats"]) if self.d.whats else "#contato"

    def foto(self, n=None, grupo="todas"):
        if n is None:
            n = self.uso_fotos
            self.uso_fotos += 1
        return self.d.url_foto(n, grupo)

    def registro(self):
        conselho = self.n["conselho"]
        return confirmar(f"{conselho} nº" if conselho else "registro profissional")

    def nome_profissional(self):
        return e(self.d.profissional) if self.d.profissional else confirmar("Nome do profissional")

    def prova(self, claro=False):
        rostos = "".join(f'<img src="{self.d.url_foto(i, "pessoas")}" alt="">' for i in range(min(3, len(self.d.fotos["pessoas"]) or 0)))
        if not rostos and self.d.avatar:
            rostos = f'<img src="{e(self.d.avatar)}" alt="">'
        if self.d.nota:
            numero = f'<b>{str(self.d.nota).replace(".", ",")}<svg viewBox="0 0 24 24" class="estrela">{ICONES["estrela"]}</svg></b>'
            texto = f'{self.d.avaliacoes} avaliações no Google {confirmar()}' if self.d.avaliacoes else f'nota no Google {confirmar()}'
        elif self.d.horario_resumo:
            numero, texto = f'<b>{e(self.d.horario_resumo)}</b>', "horário de atendimento"
        else:
            numero, texto = f'<b>{e(self.d.bairro)}</b>', self.d.cidade
        return f'<div class="prova{" clara" if claro else ""}"><div class="rostos">{rostos}</div><div>{numero}<small>{texto}</small></div></div>'

    def chips(self, classe="chip", limite=5):
        return "".join(f'<span class="{classe}">{icone(s[2])}{e(s[0])}</span>' for s in self.d.servicos[:limite])

    def menu(self, classe=""):
        marca_img = f'<img src="{e(self.d.avatar)}" alt="">' if self.d.avatar else ""
        itens = [("#inicio", "Início", "casa"), ("#sobre", "Sobre", "coracao"), ("#servicos", self.d.palavra_servicos, "lista"),
                 ("#como", "Como funciona", "calendario"), ("#contato", "Contato", "pino")]
        nav = "".join(f'<a href="{h}">{icone(i)}{t}</a>' for h, t, i in itens)
        gaveta = "".join(f'<a href="{h}">{t}</a>' for h, t, _ in itens)
        return (f'<header class="menu {classe}"><div class="g"><a class="marca" href="#inicio">{marca_img}<span>{e(self.d.nome)}</span></a>'
                f'<nav aria-label="Menu">{nav}</nav><div class="menu-acoes">{self.botao("Falar agora", "peq cor", self.whats_link(), "whats")}'
                f'<button class="menu-celular seta-redonda" aria-label="Abrir menu" aria-expanded="false">{icone("menu")}</button></div></div>'
                f'<div class="leitura"></div></header><div class="gaveta">{gaveta}{self.botao(None, "cor", self.whats_link())}</div>')

    def aviso(self):
        return (f'<div class="aviso-previa"><span class="ponto"></span><span><b>Site de exemplo</b> feito por {e(autor()[0])} para a {e(self.d.nome)}. '
                f'Se aprovarem, montamos a versão completa e mais elaborada. Itens em amarelo precisam ser confirmados.</span></div>')

    def titulo(self, indice):
        t1, t2 = self.n["titulos"][indice % len(self.n["titulos"])]
        return t1, t2

    def cabeca(self, rotulo, titulo, lado="", centro=False, extra=""):
        lado_html = f'<p class="lado">{lado}</p>' if lado else ""
        return (f'<div class="cabeca{" centro" if centro else ""}" data-revela><div><p class="rotulo pilula">{e(rotulo)}</p>'
                f'<h2>{titulo}</h2></div>{lado_html}{extra}</div>')

    # ---------- seções ----------
    def secao_sobre(self, variante="dois-tons"):
        forte, resto = self.n["sobre"]
        pilula = f'<span class="pilula-foto"><img src="{self.foto(2)}" alt=""></span>'
        texto = f'{e(forte)}{pilula}<span class="cinza">{e(resto)}</span>'
        selos = [(icone("pino"), self.d.bairro, self.d.cidade)]
        if self.d.horario_resumo:
            selos.append((icone("relogio"), self.d.horario_resumo, "horário de atendimento"))
        if self.d.insta:
            selos.append((icone("insta"), self.d.insta, "no Instagram"))
        if self.d.profissional:
            selos.append((icone("escudo"), self.d.profissional, self.registro()))
        selos_html = "".join(f'<div class="selo"><span class="ico-caixa">{i}</span><span><b>{e(a)}</b>{b if "<mark" in str(b) else e(b)}</span></div>' for i, a, b in selos)
        mini = f'<div class="miniaturas"><img src="{self.foto(3)}" alt="Ambiente da {e(self.d.nome)}"><img src="{self.foto(4)}" alt=""></div>'
        if variante == "foto":
            return f'''<section class="secao" id="sobre"><div class="g sobre-foto">
<figure class="sobre-foto-img" data-revela><img src="{self.foto(1)}" alt="Ambiente da {e(self.d.nome)}"><figcaption class="chip cheio">{icone("pino")}{e(self.d.bairro)}</figcaption></figure>
<div data-revela="2"><p class="rotulo pilula">Sobre a {e(self.d.nome)}</p><h2>{e(forte)}</h2><p class="sobre-texto">{e(resto.strip())}</p>
<div class="selos">{selos_html}</div><div class="botoes" style="margin-top:32px">{self.botao(None, "", self.whats_link())}</div></div></div></section>'''
        return f'''<section class="secao" id="sobre"><div class="g sobre-grade">
<div data-revela><p class="rotulo pilula">Sobre</p>{mini}</div>
<div data-revela="2"><p class="texto-grande">{texto}</p><div class="selos">{selos_html}</div></div></div></section>'''

    def secao_numeros(self, variante="linha"):
        itens = []
        if self.d.nota:
            itens.append((str(self.d.nota).replace(".", ","), "", f"nota no Google {confirmar()}"))
        if self.d.avaliacoes:
            itens.append((str(self.d.avaliacoes), "", f"avaliações no Google {confirmar()}"))
        dias = len([1 for _, h in self.d.horario if h != "Fechado"])
        if dias:
            itens.append((str(dias), "", "dias de atendimento por semana"))
        if self.d.servicos_do_google:
            itens.append((str(len(self.d.servicos)), "", "áreas de atendimento cadastradas"))
        ano = self.d.emp.get("ano_abertura")
        if ano:
            itens.append((str(ano), "", "ano de abertura"))
        if len(itens) < 2:
            return ""
        blocos = "".join(f'<div class="numero" data-revela="{i % 3 + 1}"><b data-conta="{e(v.replace(",", "."))}" data-sufixo="{s}">{e(v)}{s}</b><span>{t}</span></div>' for i, (v, s, t) in enumerate(itens[:4]))
        titulo = f'<div class="numeros-titulo" data-revela><h2>Quem já foi, <span class="cinza">conta.</span></h2><p class="cinza">Números do perfil da {e(self.d.nome)} no Google, para {"a" if self.n["lugar"] in ("clínica", "empresa") else "o"} {e(self.n["lugar"])} confirmar.</p></div>' if self.d.nota else ""
        return f'<section class="secao numeros-secao {variante}"><div class="g numeros-caixa">{titulo}<div class="numeros">{blocos}</div></div></section>'

    def _cabeca_servicos(self, centro=False, setas=""):
        lado = "Áreas cadastradas no perfil do Google." + f" {confirmar('confirmar a lista')}" if self.d.servicos_do_google else f"Lista de exemplo do ramo {confirmar(f"confirmar o que {'a' if self.n['lugar'] in ('clínica', 'empresa') else 'o'} {self.n['lugar']} faz")}"
        palavra = self.d.palavra_servicos
        return self.cabeca(palavra, f'Do primeiro exame <span class="cinza">ao cuidado de rotina.</span>' if self.d.nicho_chave == "dentista"
                           else f'O que você encontra <span class="cinza">na {e(self.d.nome)}.</span>', lado, centro, setas)

    def secao_servicos(self, variante="cartoes"):
        s = self.d.servicos
        if variante == "carrossel":
            cartoes = "".join(f'''<article class="cartao-alto" data-revela="{i % 3 + 1}"><div class="topo"><div class="chips"><span class="chip">{e(self.d.bairro)}</span><span class="chip">{i + 1:02d}</span></div>
<span class="ico-caixa redondo">{icone(ic)}</span><h3>{e(t)}</h3><p>{e(c)}</p></div><div class="foto"><img src="{self.d.url_foto(i, "ambiente")}" alt="">{self.botao("Agendar", "claro peq", self.whats_link())}</div></article>''' for i, (t, c, ic) in enumerate(s))
            setas = f'<div class="carrossel-setas"><button class="seta-redonda" data-dir="-1" aria-label="Anterior">{icone("seta-esq")}</button><button class="seta-redonda" data-dir="1" aria-label="Próximo">{icone("seta-dir")}</button></div>'
            return f'<section class="secao" id="servicos"><div class="g" data-carrossel>{self._cabeca_servicos(setas=setas)}<div class="carrossel">{cartoes}</div></div></section>'
        if variante == "lista":
            itens = "".join(f'''<li{' class="ativo"' if i == 0 else ""}><button><span class="n mono">{i + 1:02d}</span><h3>{e(t)}</h3><span class="seta-redonda">{icone("seta-dir")}</span><p>{e(c)}</p></button></li>''' for i, (t, c, _) in enumerate(s))
            fotos = "".join(f'<img src="{self.d.url_foto(i, "ambiente")}" alt=""{" class=" + chr(34) + "ativa" + chr(34) if i == 0 else ""}>' for i in range(min(len(s), max(2, len(self.d.fotos["todas"])))))
            return f'''<section class="secao" id="servicos"><div class="g">{self._cabeca_servicos()}<div class="lista-troca" data-lista-troca><ol data-revela>{itens}</ol>
<div class="palco" data-revela="2">{fotos}<div class="legenda"><span class="ico-caixa cheio">{icone(s[0][2])}</span><span><small class="cinza">Em destaque</small><br><b>{e(s[0][0])}</b></span></div></div></div></div></section>'''
        if variante == "abas":
            botoes = "".join(f'<button role="tab"{" class=" + chr(34) + "ativo" + chr(34) if i == 0 else ""}>{icone(ic)}{e(t)}</button>' for i, (t, _, ic) in enumerate(s))
            paineis = "".join(f'''<div class="abas-painel{' ativo' if i == 0 else ''}" role="tabpanel"><div class="foto"><img src="{self.d.url_foto(i, "ambiente")}" alt=""></div><div class="info"><span class="ico-caixa">{icone(ic)}</span><h3>{e(t)}</h3><p>{e(c)}</p>
<ul><li>{icone("check")}Avaliação antes de começar</li><li>{icone("check")}Explicação de cada etapa</li><li>{icone("check")}Acompanhamento depois</li></ul>{self.botao(None, "cor", self.whats_link())}</div></div>''' for i, (t, c, ic) in enumerate(s))
            return f'<section class="secao fundo2" id="servicos"><div class="g">{self._cabeca_servicos(centro=True)}<div class="abas" data-abas data-revela><div class="abas-lista" role="tablist"><span class="indicador"></span>{botoes}</div><div>{paineis}</div></div></div></section>'
        cartoes = "".join(f'''<article class="servico" data-inclina data-revela="{i % 3 + 1}"><span class="num mono">{i + 1:02d}</span><span class="ico-caixa">{icone(ic)}</span><h3>{e(t)}</h3><p>{e(c)}</p></article>''' for i, (t, c, ic) in enumerate(s))
        lado = f'''<div class="servicos-lado" data-revela>{self.prova()}<p class="cinza">{e(self.n["subtitulo"].format(bairro=self.d.bairro).split(".")[0])}.</p><p class="frase">{e(self.n.get("frase_servicos", "Veja como funciona o atendimento."))}</p>{self.botao(self.n["botao2"], "", "#como")}</div>'''
        return f'<section class="secao fundo2" id="servicos"><div class="g">{self._cabeca_servicos()}<div class="servicos-bloco">{lado}<div class="servicos-cartoes">{cartoes}</div></div></div></section>'

    def secao_faixa(self):
        palavras = [s[0] for s in self.d.servicos] or self.n["faixa"]
        icones = [s[2] for s in self.d.servicos] or ["brilho"] * len(palavras)
        itens = "".join(f'<span>{icone(icones[i % len(icones)])}{e(p)}</span>' for i, p in enumerate(palavras))
        return f'<div class="faixa" aria-hidden="true"><div class="trilho">{itens}{itens}{itens}{itens}</div></div>'

    def secao_codigo(self):
        etapas = "".join(f'<span>{e(t)}</span>' for t in self.n["etapas"])
        return f'<div class="g faixa-codigo" aria-hidden="true">{etapas}</div>'

    def secao_situacoes(self):
        itens = self.n["situacoes"]
        if not itens:
            return ""
        cartoes = "".join(f'<article class="situacao" data-revela="{i % 3 + 1}"><span class="ico-caixa">{icone(ic)}</span><h3>{e(t)}</h3><p>{e(c)}</p></article>' for i, (t, c, ic) in enumerate(itens))
        return f'<section class="secao"><div class="g">{self.cabeca("Para você", "Alguma dessas situações <span class=" + chr(34) + "cinza" + chr(34) + ">é a sua?</span>", "Os motivos mais comuns para procurar o atendimento.")}<div class="situacoes">{cartoes}</div></div></section>'

    def secao_galeria(self):
        fotos = self.d.fotos["ambiente"] + self.d.fotos["fachada"] + self.d.fotos["pessoas"]
        if len(fotos) < 3:
            return ""
        def legenda(f):
            marcas = f.get("marcas", [])
            return "Fachada" if "front" in marcas else "Equipe" if "people" in marcas else "Por dentro"
        figs = "".join(f'<figure data-revela="{i % 3 + 1}"><img src="img/{urllib.parse.quote(f["arquivo"])}" alt="Foto da {e(self.d.nome)}" loading="lazy"><figcaption>{icone("pino", "ico ico-p")} {legenda(f)}</figcaption></figure>' for i, f in enumerate(fotos[:6]))
        return f'<section class="secao"><div class="g">{self.cabeca("O espaço", "Conheça por dentro <span class=" + chr(34) + "cinza" + chr(34) + ">antes de chegar.</span>", f"Fotos reais da {e(self.d.nome)}, no {e(self.d.bairro)}.")}<div class="mosaico">{figs}</div></div></section>'

    def secao_passos(self, escuro=False):
        cartoes = "".join(f'''<article class="passo" data-revela="{i + 1}"><div class="topo"><span class="ico-caixa">{icone(ic)}</span><span class="mono">Passo {i + 1:02d}</span></div><h3>{e(t)}</h3><p>{e(c)}</p><div class="barra"><i></i></div></article>''' for i, (t, c, ic) in enumerate(self.n["passos"]))
        return f'<section class="secao{" escura" if escuro else ""}" id="como"><div class="g">{self.cabeca("Como funciona", "Do primeiro contato <span class=" + chr(34) + "cinza" + chr(34) + ">ao atendimento.</span>", "Simples, do jeito que deve ser. Você sabe o que vai acontecer em cada etapa.", extra=self.botao(None, "cor", self.whats_link()))}<div class="passos" data-passos>{cartoes}</div></div></section>'

    def secao_equipe(self):
        retrato = self.d.retrato()
        ficha = [("Registro", self.registro()), ("Atuação", e(", ".join(s[0] for s in self.d.servicos[:3]))), ("Onde", e(self.d.bairro + ", " + self.d.cidade))]
        if self.d.insta:
            ficha.append(("Instagram", e(self.d.insta)))
        linhas = "".join(f'<div><span>{a}</span><b>{b}</b></div>' for a, b in ficha)
        return f'''<section class="secao"><div class="g equipe"><figure class="retrato" data-revela style="margin:0"><img src="{retrato}" alt="Quem atende na {e(self.d.nome)}"><span class="canto">{icone("seta")}</span></figure>
<div data-revela="2"><p class="rotulo pilula">Quem atende</p><p class="nome">{self.nome_profissional()}</p><p class="cargo">{e(self.n["profissao"])}</p>
<dl class="ficha">{linhas}</dl><p class="cinza" style="margin-top:22px;max-width:52ch">A apresentação de quem atende entra na versão completa, com a formação e a história que a {e(self.d.nome)} quiser contar. {confirmar("confirmar quem aparece nas fotos")}</p></div></div></section>'''

    def secao_duvidas(self, com_foto=True):
        perguntas = list(self.n["faq"])
        if not any(sem_acento(p[0]).lower().startswith("onde fica") for p in perguntas):
            perguntas.append(("Onde fica?", f"{self.d.endereco or self.d.bairro}. Veja o mapa logo abaixo."))
        itens = "".join(f'<div class="pergunta"><button aria-expanded="false">{e(p)}<span class="mais">{icone("mais")}</span></button><div class="resposta"><div><p>{e(r)}</p></div></div></div>' for p, r in perguntas)
        foto = f'<div class="lado-foto"><img src="{self.foto(5)}" alt="" loading="lazy"></div>' if com_foto else ""
        return f'''<section class="secao fundo2" id="duvidas"><div class="g duvidas"><div data-revela><p class="rotulo pilula">Dúvidas</p><h2>Antes de <span class="cinza">chamar.</span></h2>{foto}</div><div data-revela="2">{itens}</div></div></section>'''

    def secao_contato(self):
        linhas = []
        if self.d.endereco:
            mapa_link = self.d.maps_link or "https://www.google.com/maps/search/?api=1&query=" + urllib.parse.quote(f"{self.d.nome_completo} {self.d.endereco}")
            linhas.append(("pino", "Endereço", f'<a href="{e(mapa_link)}" target="_blank" rel="noopener">{e(self.d.endereco)}</a>'))
        linhas.append(("whats", "WhatsApp", f'<a href="{e(self.whats_link())}" target="_blank" rel="noopener">{e(self.d.telefone)}</a>' if self.d.whats else confirmar("WhatsApp")))
        if self.d.insta:
            linhas.append(("insta", "Instagram", f'<a href="https://instagram.com/{e(self.d.insta.lstrip("@"))}" target="_blank" rel="noopener">{e(self.d.insta)}</a>'))
        linhas_html = "".join(f'<div class="linha"><span class="ico-caixa">{icone(i)}</span><span><small>{t}</small>{v}</span></div>' for i, t, v in linhas)
        horario = "".join(f'<div data-dia="{e(d.split("-")[0])}"><span>{d.split("-")[0].capitalize()}</span><span>{e(h)}</span></div>' for d, h in self.d.horario)
        horario_html = f'<div><p class="rotulo">Horário</p><div class="horario">{horario}</div></div>' if horario else f'<div class="linha"><span class="ico-caixa">{icone("relogio")}</span><span><small>Horário</small>{confirmar("horário de atendimento")}</span></div>'
        lat, lng = self.d.maps.get("latitude"), self.d.maps.get("longitude")
        alvo = f"{lat},{lng}" if lat and lng else f"{self.d.nome_completo} {self.d.endereco}"
        abrir = self.d.maps_link or "https://www.google.com/maps/search/?api=1&query=" + urllib.parse.quote(f"{self.d.nome_completo} {self.d.endereco}")
        mapa = (f'<div class="mapa" data-revela="2"><div class="mapa-fundo" aria-hidden="true"><i></i><span class="pino-mapa">{icone("pino")}</span></div>'
                f'<iframe title="Mapa" loading="lazy" src="https://www.google.com/maps?q={urllib.parse.quote(alvo)}&z=16&output=embed"></iframe>'
                f'<div class="mapa-cartao"><span class="ico-caixa cheio">{icone("pino")}</span><span><b>{e(self.d.nome)}</b><small>{e(self.d.endereco)}</small></span>'
                f'<a class="seta-redonda" href="{e(abrir)}" target="_blank" rel="noopener" aria-label="Abrir no Google Maps">{icone("seta")}</a></div></div>')
        return f'''<section class="secao" id="contato"><div class="g">{self.cabeca("Contato", f"Venha conhecer <span class={chr(34)}cinza{chr(34)}>a {e(self.d.nome)}.</span>")}
<div class="contato"><div class="cartao" data-revela>{linhas_html}{horario_html}{self.botao(None, "cor", self.whats_link())}</div>{mapa}</div></div></section>'''

    def secao_chamada(self):
        t, c = self.n["chamada"]
        foto = self.d.url_foto(0, "fachada") if self.d.fotos["fachada"] else self.foto(0)
        return f'''<section class="chamada" data-revela><img src="{foto}" alt="" loading="lazy"><div class="g"><div><p class="rotulo" style="color:#fff">{e(self.d.bairro)} · {e(self.d.cidade)}</p><h2>{e(t)}</h2><p>{e(c)}</p></div>
<div class="botoes">{self.botao(None, "claro", self.whats_link())}{self.botao("Ver no mapa", "contorno branco", "#contato", "pino")}</div></div></section>'''

    # ---------- seções dos modelos F, G e H (03/11: referências de bem-estar, mais cor) ----------
    def secao_lista_foto(self):
        """Serviços em lista ao lado de uma foto grande com um cartão de fato real por cima (ref. wellness verde)."""
        itens = "".join(f'''<details class="lf-item"{" open" if i == 0 else ""} data-revela="{i % 3 + 1}"><summary><span class="ico-caixa">{icone(ic)}</span><span class="lf-nome">{e(n)}</span><span class="lf-mais">{icone("mais")}</span></summary><p>{e(t)}</p></details>''' for i, (n, t, ic) in enumerate(self.d.servicos[:6]))
        fato = (f'<b>{str(self.d.nota).replace(".", ",")}<svg viewBox="0 0 24 24" class="estrela">{ICONES["estrela"]}</svg></b><small>{self.d.avaliacoes} avaliações no Google {confirmar()}</small>' if self.d.nota
                else f'<b>{e(self.d.horario_resumo or self.d.bairro)}</b><small>{"horário de atendimento" if self.d.horario_resumo else e(self.d.cidade)}</small>')
        return f'''<section class="secao" id="servicos"><div class="g">{self._cabeca_servicos()}<div class="lf"><figure class="lf-foto" data-revela><img src="{self.foto(2)}" alt="" loading="lazy"><figcaption class="lf-fato">{fato}<a class="seta-redonda" href="{e(self.whats_link())}" target="_blank" rel="noopener" aria-label="{e(self.n["botao"])}">{icone("seta")}</a></figcaption></figure><div class="lf-lista">{itens}{self.botao(None, "cor", self.whats_link())}</div></div></div></section>'''

    def secao_faixa_cor(self):
        """Faixa cheia na cor da marca com um número grande verdadeiro e uma foto (ref. Slimor 96%)."""
        if self.d.nota:
            numero, legenda = str(self.d.nota).replace(".", ","), f"de nota no Google, em {self.d.avaliacoes} avaliações {confirmar()}" if self.d.avaliacoes else f"de nota no Google {confirmar()}"
        elif self.d.horario_resumo:
            numero, legenda = str(len([1 for _, h in self.d.horario if h != "Fechado"])), "dias de atendimento por semana"
        else:
            return ""
        t, c = self.n["chamada"]
        return f'''<section class="faixa-cor" data-revela><div class="fc-texto"><b class="fc-num">{e(numero)}</b><p class="fc-leg">{legenda}</p><h2>{e(t)}</h2><p class="fc-sub">{e(c)}</p>{self.botao(None, "claro", self.whats_link())}</div><div class="fc-foto"><img src="{self.foto(3)}" alt="" loading="lazy"></div></section>'''

    def secao_passos_grandes(self):
        """Como funciona em números grandes 01 02 03, com foto ao lado (ref. qura)."""
        linhas = "".join(f'''<div class="pg-linha" data-revela="{i + 1}"><span class="pg-num">{i + 1:02d}</span><div><h3>{e(t)}</h3><p>{e(c)}</p></div></div>''' for i, (t, c, _) in enumerate(self.n["passos"]))
        return f'''<section class="secao fundo2" id="como"><div class="g pg"><div class="pg-foto" data-revela><img src="{self.foto(4)}" alt="" loading="lazy"><span class="pg-selo">{icone("conversa")}Começa pelo WhatsApp</span></div><div><p class="rotulo pilula">Como funciona</p><h2>Do primeiro contato <span class="cinza">ao atendimento.</span></h2><div class="pg-lista">{linhas}</div>{self.botao(None, "cor", self.whats_link())}</div></div></section>'''

    def secao_destaque_escuro(self):
        """Bloco escuro na cor da marca com a frase do "sobre" num cartão claro (ref. wellness verde, sem depoimento inventado)."""
        forte, resto = self.n["sobre"]
        return f'''<section class="destaque-escuro" data-revela><div class="g de"><div class="de-topo"><p class="rotulo" style="color:var(--claro)">Sobre a {e(self.d.nome)}</p><h2>{e(forte)}</h2></div><div class="de-corpo"><img src="{self.d.url_foto(0, "pessoas") if self.d.fotos["pessoas"] else self.foto(1)}" alt="" loading="lazy"><div class="de-cartao"><span class="de-aspas">{icone("coracao")}Como {"a" if self.n["lugar"] in ("clínica", "empresa") else "o"} {e(self.n["lugar"])} trabalha</span><p>{e(resto.strip())}</p><div class="de-assina">{f'<img src="{e(self.d.avatar)}" alt="">' if self.d.avatar else ""}<span><b>{e(self.d.nome)}</b><small>{e(self.d.bairro)} · {e(self.d.cidade)}</small></span></div></div></div></div></section>'''

    def secao_bento(self):
        fotos = [self.foto(i) for i in (1, 2, 3)]
        nota = (f'<b data-conta="{self.d.nota}">{str(self.d.nota).replace(".", ",")}</b><span>nota no Google {confirmar()}</span>' if self.d.nota
                else f'<b>{len(self.d.servicos)}</b><span>áreas de atendimento</span>')
        dias = len([1 for _, h in self.d.horario if h != "Fechado"])
        horas = f'<b data-conta="{dias}">{dias}</b><span>dias de atendimento por semana</span>' if dias else f'<b>{e(self.d.bairro)}</b><span>{e(self.d.cidade)}</span>'
        forte, resto = self.n["sobre"]
        return f'''<section class="secao" id="sobre"><div class="g"><div class="bento">
<article class="b-cor" data-revela><svg class="ondas" viewBox="0 0 400 200" aria-hidden="true"><path d="M0 120c60-40 120-40 180 0s120 40 220-10M0 150c60-40 120-40 180 0s120 40 220-10M0 90c60-40 120-40 180 0s120 40 220-10"/></svg><span class="ico-caixa redondo">{icone("seta")}</span><p>{e(forte)}<span>{e(resto)}</span></p></article>
<article class="b-num" data-revela="2">{nota}</article>
<figure class="b-foto b-capsula" data-revela="2"><img src="{fotos[0]}" alt=""><img src="{fotos[1]}" alt=""></figure>
<article class="b-num b-escuro" data-revela="3">{horas}</article>
<figure class="b-foto b-organica" data-revela="3"><img src="{fotos[2]}" alt=""></figure>
</div></div></section>'''

    def rodape(self):
        servicos = "".join(f'<a href="#servicos">{e(s[0])}</a>' for s in self.d.servicos[:5])
        contato = []
        if self.d.whats:
            contato.append(f'<a href="{e(self.whats_link())}" target="_blank" rel="noopener">WhatsApp</a>')
        if self.d.insta:
            contato.append(f'<a href="https://instagram.com/{e(self.d.insta.lstrip("@"))}" target="_blank" rel="noopener">Instagram</a>')
        contato.append('<a href="#contato">Endereço e mapa</a>')
        responsavel = ""
        if self.n["conselho"]:
            responsavel = f'<p class="cinza" style="margin-top:14px">Responsável técnico: {self.nome_profissional()} · {self.registro()}</p>'
        return f'''<footer class="rodape"><div class="g"><div class="colunas"><div><a class="marca" href="#inicio">{f'<img src="{e(self.d.avatar)}" alt="">' if self.d.avatar else ""}<span>{e(self.d.nome)}</span></a>
<p class="cinza" style="margin-top:16px;max-width:36ch">{e(self.d.endereco)}</p>{responsavel}</div>
<div><h4>{e(self.d.palavra_servicos)}</h4>{servicos}</div><div><h4>Página</h4><a href="#sobre">Sobre</a><a href="#como">Como funciona</a><a href="#duvidas">Dúvidas</a></div><div><h4>Contato</h4>{"".join(contato)}</div></div>
<p class="gigante" aria-hidden="true">{e(self.d.nome.replace("Dra. ", "").replace("Dr. ", ""))}</p>
<div class="base"><span>Proposta de site por {e(autor()[0])}. Esta página é um exemplo e não é o site oficial da {e(self.d.nome)}.</span><span>{e(autor()[1])}</span></div></div></footer>'''

    def whats_flutuante(self):
        return f'<a class="whats" href="{e(self.whats_link())}" target="_blank" rel="noopener"><i>{icone("whats")}</i><span>Fale com a {e(self.d.nome.split()[0] if len(self.d.nome) > 22 else self.d.nome)}</span></a>'

    def secoes(self, ordem):
        saida = []
        for item in ordem:
            nome, _, variante = item.strip().partition(":")
            funcao = getattr(self, "secao_" + nome, None)
            if funcao:
                saida.append(funcao(variante) if variante else funcao())
        return "\n".join(s for s in saida if s)


# ---------- modelo ----------
def ler_meta(modelo, nome, padrao=""):
    achado = re.search(rf'<meta name="{nome}" content="([^"]*)"', modelo)
    return achado.group(1) if achado else padrao


def fatos_para_copy(empresa, pasta):
    """O que se sabe de verdade sobre a empresa, para a copy própria (sem nada inventado)."""
    d = Dados(empresa, pasta)
    sobre = d.maps.get("about") or {}
    extras = [item for grupo in sobre.values() if isinstance(grupo, dict) for item, sim in grupo.items() if sim is True]
    site = (empresa.get("contatos") or {}).get("site") or (empresa.get("dica") or {}).get("site") or d.maps.get("website") or ""
    fatos = {"nome": d.nome_completo, "area": d.n["nome"], "profissao": d.n["profissao"],
             "categorias_no_google": d.maps.get("subtypes") or d.maps.get("type") or "", "bairro": d.bairro, "cidade": d.cidade,
             "endereco": d.endereco, "nota_google": d.nota, "avaliacoes_google": d.avaliacoes or None,
             "horario": d.horario_resumo or None, "instagram": d.insta or None, "profissional": d.profissional or None,
             "detalhes_do_google": extras[:12] or None}
    return {k: v for k, v in fatos.items() if v}, site, d.n["cliente"], d.n["lugar"]


def autor():
    """Quem assina a prévia: o nome do perfil (Meu perfil) de cada conta."""
    import os
    perfil = ler_json(Path(os.environ.get("PROSPECCAO_DADOS", Path(__file__).resolve().parent.parent / "dados")) / "config.json", {}).get("perfil", {})
    return (perfil.get("nome") or os.environ.get("PROSPECCAO_MARCA") or "Seu nome"), (perfil.get("site") or "")


def marca_curta(nome):
    """Nome para o letreiro gigante do modelo G: sem Dr./Dra. e sem palavras do ramo, no máximo 2 palavras."""
    ramo = r"(Dra?\.?|Cl[ií]nica|Consult[óo]rio|Studio|Est[úu]dio|Escrit[óo]rio|Centro|Instituto|Veterin[áa]ri[ao]|Odontol[óo]gic[ao]|Odontologia|Fisioterapia|Contabilidade|Cont[áa]bil|Arquitetura|Advocacia|Advogados|M[ée]dica|Pet|de|da|do|e|&)"
    palavras = [w for w in nome.strip().split() if not re.fullmatch(ramo, w, flags=re.I)]
    return " ".join(palavras[:2]) or nome


def montar(empresa, pasta, receita=None):
    pasta = Path(pasta)
    dados = Dados(empresa, pasta)
    receita = receita or escolher_receita(empresa["cnpj"], dados)
    modelo = (MODELOS / RECEITAS[receita]).read_text(encoding="utf-8")
    m = Montador(dados, receita)
    indice_titulo = sum(ord(c) for c in empresa["cnpj"])
    t1, t2 = m.titulo(indice_titulo)
    fonte = ler_meta(modelo, "fonte", "Geist")
    valores = {
        "titulo_pagina": e(f"{dados.nome} · {dados.n['nome']} no {dados.bairro}, {dados.cidade}"),
        "fontes": f'<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin><link href="https://fonts.googleapis.com/css2?family={fonte.replace(" ", "+")}:wght@300;400;500;600&family=Geist+Mono:wght@400;500&display=swap" rel="stylesheet">',
        "css": (MODELOS / "base.css").read_text(encoding="utf-8"),
        "tokens": ":root{" + ";".join(f"{k}:{v}" for k, v in dados.paleta.items()) + f";--fonte:'{fonte}';--x:clamp(20px,4.5vw,64px);--max:1240px;--raio:22px}}",
        "js": (MODELOS / "base.js").read_text(encoding="utf-8"),
        "aviso": m.aviso(), "menu": m.menu(), "nome": e(dados.nome), "bairro": e(dados.bairro), "cidade": e(dados.cidade), "marca": e(marca_curta(dados.nome)),
        "marca_tam": f"clamp(30px,{min(24, round(150 / max(len(marca_curta(dados.nome)), 4), 1))}vw,{min(320, round(1500 / max(len(marca_curta(dados.nome)), 4)))}px)",
        "titulo1": e(t1), "titulo2": e(t2), "subtitulo": e(dados.n["subtitulo"].format(bairro=dados.bairro)),
        "botao": m.botao(None, "", m.whats_link()), "botao_cor": m.botao(None, "cor", m.whats_link()), "botao_claro": m.botao(None, "claro", m.whats_link()),
        "botao2": m.botao(dados.n["botao2"], "contorno", "#servicos", "seta-baixo"), "botao2_branco": m.botao(dados.n["botao2"], "contorno branco", "#servicos", "seta-baixo"),
        "prova": m.prova(), "prova_clara": m.prova(claro=True), "chips": m.chips(), "chips_vidro": m.chips("chip vidro", 5),
        "retrato": dados.retrato(), "profissional": m.nome_profissional(), "profissao": e(dados.n["profissao"]), "registro": m.registro(),
        "servico1": e(dados.servicos[0][0]), "servico1_texto": e(dados.servicos[0][1]), "servico1_icone": icone(dados.servicos[0][2]),
        "horario": e(dados.horario_resumo) if dados.horario_resumo else confirmar("horário"),
        "endereco": e(dados.endereco), "insta": e(dados.insta or dados.bairro), "whats_link": e(m.whats_link()), "telefone": e(dados.telefone),
        "rodape": m.rodape(), "whats_flutuante": m.whats_flutuante(), "lugar": e(dados.n["lugar"]),
        "abre_whats": e(dados.n["abre_whats"]), "agenda_destino": e(dados.whats),
        "opcoes_servico": "".join(f"<option>{e(s[0])}</option>" for s in dados.servicos),
        "opcoes_dia": "".join(f"<option>{d.split('-')[0].capitalize()}</option>" for d, h in dados.horario if h != "Fechado") or "<option>Qualquer dia</option>",
    }
    for nome in ("check", "seta", "whats", "pino", "relogio", "insta", "estrela", "escudo", "calendario", "conversa", "mais", "seta-dir", "seta-esq", "coracao", "busca", "seta-baixo"):
        valores["ico_" + nome.replace("-", "_")] = icone(nome)

    def troca(achado):
        chave, arg = achado.group(1), achado.group(2)
        if chave == "foto":
            return m.d.url_foto(int(arg) - 1)
        if chave == "foto_ambiente":
            return m.d.url_foto(int(arg) - 1, "ambiente")
        if chave == "fato":
            fatos = m_fatos(m)
            n = int(arg) - 1
            return f'<span class="fato fato-{n + 1}">{fatos[n]}</span>' if n < len(fatos) else ""
        if chave == "secoes":
            return m.secoes(ler_meta(modelo, "ordem").split(","))
        return valores.get(chave, achado.group(0))

    pagina = re.sub(r"\{\{(\w+)(?::(\w+))?\}\}", troca, modelo)
    # enquadramento: cada foto cortada "olha" para o rosto (03/11: o retrato mostrava só a boca)
    regras = [f'img[src$="{urllib.parse.quote(f["arquivo"])}"]{{object-position:{x}% {y}%}}' for f in dados.fotos["todas"]
              for x, y in [foco_da_foto(f) or (None, None)] if x is not None]
    if regras:
        pagina = pagina.replace("</head>", "<style data-foco>" + "".join(regras) + "</style>\n</head>", 1)
    total = len(t1) + len(t2)
    if total > 30:
        px = max(40, min(92, round(2900 / total)))
        ajuste = (f"<style>/* título longo: cabe em 2 linhas */ main h1{{font-size:clamp(34px,{round(px / 14.4, 2)}vw,{px}px)!important;line-height:1.02!important}}"
                  " main h1 .l2{padding-left:0!important}</style>\n</head>")
        pagina = pagina.replace("</head>", ajuste, 1)
    pagina = re.sub(r'<meta name="(ordem|fonte|receita)"[^>]*>\n?', "", pagina)
    return pagina, dados, receita


def m_fatos(m):
    """Pílulas da abertura C: só fatos reais."""
    d = m.d
    fatos = []
    if d.nota:
        fatos.append(f'{icone("estrela")}{str(d.nota).replace(".", ",")} no Google {confirmar()}')
    if d.horario_resumo:
        fatos.append(f'{icone("relogio")}{e(d.horario_resumo)}')
    fatos.append(f'{icone("pino")}{e(d.bairro)}, {e(d.cidade)}')
    if d.insta:
        fatos.append(f'{icone("insta")}{e(d.insta)}')
    if d.servicos_do_google:
        fatos.append(f'{icone("lista")}{len(d.servicos)} áreas de atendimento')
    return fatos


# ---------- rodízio das receitas ----------
ROTACAO = Path(__file__).resolve().parent.parent / "dados" / "modelos-rotacao.json"


MODELO_PADRAO = "B"


def escolher_receita(cnpj, dados):
    rot = ler_json(ROTACAO, {"ultima": "", "empresas": {}})
    if cnpj in rot["empresas"]:
        return rot["empresas"][cnpj]
    total = len(dados.fotos["todas"])
    if MODELO_PADRAO and total >= FOTOS_MINIMAS[MODELO_PADRAO]:
        return MODELO_PADRAO  # 03/11: "já deixa automático me entregar assim" (abertura do modelo B)
    letras = list(RECEITAS)
    inicio = (letras.index(rot["ultima"]) + 1) if rot["ultima"] in letras else 0
    total_fotos = len(dados.fotos["todas"])
    for passo in range(len(letras)):
        letra = letras[(inicio + passo) % len(letras)]
        if total_fotos >= FOTOS_MINIMAS[letra]:
            return letra
    return "A"


def registrar_receita(cnpj, receita):
    rot = ler_json(ROTACAO, {"ultima": "", "empresas": {}})
    rot["ultima"] = receita
    rot["empresas"][cnpj] = receita
    ROTACAO.write_text(json.dumps(rot, ensure_ascii=False, indent=1), encoding="utf-8")


NOMES_RECEITA = {"A": "Oralyn (texto à esquerda, foto em cartão com retrato e destaque sobrepostos)",
                 "B": "Dentora/ADEMI (foto cheia em cartão, menu em pílula, fotos que trocam, chips e mini-cartão)",
                 "C": "Experts/GreenVision (título centralizado com fotos soltas, pílulas de fatos e ícones ligados)",
                 "D": "VivaChat (título à esquerda e duas colunas de fotos que se mexem ao rolar)",
                 "E": "Barra de agendamento (foto em cartão com a barra que monta a mensagem do WhatsApp)",
                 "F": "Bem-estar (foto cheia de ponta a ponta, título leve embaixo, página em tom claro da marca e bloco escuro na cor forte)",
                 "G": "Nome gigante (o nome da empresa enorme por cima da foto, como funciona em números grandes)",
                 "H": "Bloco de cor (foto com véu na cor da marca e faixa cheia com a nota do Google gigante)"}


def gerar(empresa, pasta, receita=None, guardar_versao=True):
    """Escreve index.html e layout.md. A versão anterior, se houver, vai para versoes/."""
    inicio = time.time()
    pasta = Path(pasta)
    pedida = receita
    pagina, dados, receita = montar(empresa, pasta, receita)
    destino = pasta / "index.html"
    if destino.exists() and guardar_versao:
        (pasta / "versoes").mkdir(exist_ok=True)
        (pasta / "versoes" / f"index-{datetime.now():%Y%m%d-%H%M%S}.html").write_bytes(destino.read_bytes())
    destino.write_text(pagina, encoding="utf-8")
    # sem foto ainda (primeira passada, antes do Google): não fixa o modelo, senão toda prévia ficava no A (bug de 03/11)
    if pedida or dados.fotos["todas"]:
        registrar_receita(empresa["cnpj"], receita)
    pendencias = sorted(set(re.findall(r'<mark class="confirmar">([^<]+)</mark>', pagina)))
    fotos = ler_json(pasta / "fotos.json", {"fotos": []})["fotos"]
    linhas = [
        f"# Layout da prévia · {dados.nome}",
        f"- Feito pelo modelo pronto em {datetime.now():%d/%m/%Y %H:%M} ({time.time() - inicio:.1f} s, sem IA).",
        f"- Abertura: receita {receita}, {NOMES_RECEITA[receita]}.",
        f"- Nicho: {dados.nicho_chave} ({dados.n['regra']})",
        f"- Paleta: {dados.paleta['--cor']} {'medida no logo' if dados.cor_medida else 'padrão do nicho (logo sem cor marcante)'}; fonte {ler_meta((MODELOS / RECEITAS[receita]).read_text(encoding='utf-8'), 'fonte')}.",
        f"- Serviços: {'do perfil do Google' if dados.servicos_do_google else 'lista de exemplo do nicho (confirmar)'}: {', '.join(s[0] for s in dados.servicos)}.",
        f"- Fotos ({len(fotos)}): " + "; ".join(f"{f['arquivo']} ({f['origem'].split(' (')[0]})" for f in fotos[:14]),
        f"- Oferta: {empresa.get('oferta') or '-'}. Defeito do site atual: {empresa.get('site_defeito') or empresa.get('site_problemas') or '-'}.",
        f"- Para confirmar com a empresa: {', '.join(pendencias) or 'nada'}.",
        "- Antes de enviar: conferir se nenhuma foto mostra paciente identificável, criança ou procedimento.",
    ]
    (pasta / "layout.md").write_text("\n".join(linhas) + "\n", encoding="utf-8")
    return {"receita": receita, "segundos": round(time.time() - inicio, 1), "fotos": len(fotos), "pendencias": pendencias,
            "resumo": f"Prévia montada pelo modelo {receita} em {time.time() - inicio:.1f} s, com {len(dados.fotos["todas"])} fotos reais." + (f" {dados.fotos_tiradas} foto(s) ficaram de fora (procedimento, antes e depois, close cortado ou post com texto)." if dados.fotos_tiradas else "")}


if __name__ == "__main__":
    raiz = PASTA.parent / "dados"
    codigo = sys.argv[1]
    leads = ler_json(raiz / "leads-manuais.json", [])
    empresa = next(x for x in leads if x["cnpj"] == codigo)
    print(gerar(empresa, raiz / "previas" / codigo, sys.argv[2] if len(sys.argv) > 2 else None))
