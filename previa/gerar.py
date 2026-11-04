#!/usr/bin/env python3
"""Gera a prévia de site de uma empresa, seguindo metodo/METODO-SITES.md.

Nada é inventado: o que não veio do briefing nem da Receita aparece marcado para confirmar.
A variação (composição, ordem, fonte, cantos, rótulo, animação) vem do CNPJ, para cada
clínica sair diferente mesmo quando o briefing é curto.
"""
import colorsys
import hashlib
import html
import re


def _autor():
    """Nome de quem assina a prévia: o "nome" em Meu perfil (dados/config.json)."""
    import json, os
    from pathlib import Path as _P
    try:
        cfg = json.loads((_P(os.environ.get("PROSPECCAO_DADOS", _P(__file__).resolve().parent.parent / "dados")) / "config.json").read_text())
        return cfg.get("perfil", {}).get("nome") or "Seu nome"
    except (OSError, ValueError):
        return "Seu nome"

FONTES = {"geist": "Geist", "inter": "Inter", "archivo": "Archivo"}
COMPOSICOES = ("cartao", "lado", "tipografica")
ORDENS = (
    ["reconhece", "metodo", "diferenca", "quem", "unica", "primeiro", "duvidas"],
    ["quem", "reconhece", "metodo", "unica", "diferenca", "primeiro", "duvidas"],
    ["unica", "reconhece", "quem", "metodo", "diferenca", "duvidas", "primeiro"],
    ["reconhece", "quem", "diferenca", "metodo", "primeiro", "unica", "duvidas"],
)
CORES = ("#1F6F78", "#2F5D9B", "#7A4E8C", "#3E7C59", "#B0563B", "#34495E")
ABERTURAS = (
    "Cuidar do sorriso começa por entender o que ele precisa.",
    "Você merece saber o que está acontecendo antes de decidir.",
    "Dentista que explica antes de tratar.",
    "Sua boca não precisa doer para merecer atenção.",
)
SITUACOES = (
    ("Dor ao mastigar", "Incômodo ao mastigar tem várias causas. Uma consulta ajuda a entender a sua."),
    ("Sensibilidade", "Sentir o frio, o quente ou o doce é um motivo comum para procurar o dentista."),
    ("Gengiva sangrando", "Sangramento ao escovar merece atenção, mesmo quando não dói."),
    ("Dente quebrado", "Um dente lascado ou uma restauração solta pedem avaliação do dentista."),
    ("Faz tempo que não vou", "Muita gente adia a consulta. Dá para retomar o cuidado a partir de hoje."),
)
PASSOS = (
    ("Conversa", "Você conta o que está sentindo e o que espera da consulta."),
    ("Avaliação", "O dentista examina e explica o que encontrou."),
    ("Plano", "Você entende as opções antes de decidir o próximo passo."),
)


def e(texto):
    return html.escape(str(texto or ""), quote=True)


def confirmar(texto):
    return f'<mark class="confirmar">{e(texto)}</mark>'


def exemplo():
    return '<span class="selo-exemplo">Texto de exemplo, a confirmar</span>'


def linhas(texto):
    return [l.strip() for l in str(texto or "").splitlines() if l.strip()]


def pares(texto):
    """Cada linha no formato 'título | texto'."""
    saida = []
    for linha in linhas(texto):
        titulo, _, corpo = linha.partition("|")
        saida.append((titulo.strip(), corpo.strip()))
    return saida


def cor_valida(valor, padrao):
    return valor if re.fullmatch(r"#[0-9a-fA-F]{6}", str(valor or "")) else padrao


def rgb(cor):
    return tuple(int(cor[i:i + 2], 16) / 255 for i in (1, 3, 5))


def tom(cor, luz, saturacao=None):
    r, g, b = rgb(cor)
    h, _, s = colorsys.rgb_to_hls(r, g, b)
    r, g, b = colorsys.hls_to_rgb(h, luz, s if saturacao is None else saturacao)
    return "#%02x%02x%02x" % (round(r * 255), round(g * 255), round(b * 255))


def luminancia(cor):
    canais = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb(cor)]
    return 0.2126 * canais[0] + 0.7152 * canais[1] + 0.0722 * canais[2]


def so_digitos(texto):
    return re.sub(r"\D", "", str(texto or ""))


def link_whatsapp(numero, nome):
    digitos = so_digitos(numero)
    if len(digitos) < 10:
        return ""
    if not digitos.startswith("55"):
        digitos = "55" + digitos
    return f"https://wa.me/{digitos}?text=" + e(f"Olá! Vi o site da {nome} e quero marcar uma consulta.").replace(" ", "%20")


class Previa:
    def __init__(self, empresa, briefing):
        self.emp = empresa
        self.b = briefing or {}
        self.fotos = self.b.get("fotos") or {}
        semente = int(hashlib.sha256(str(empresa["cnpj"]).encode()).hexdigest(), 16)
        self.semente = semente
        self.nome = self.b.get("nome") or empresa["nome"]
        self.cor = cor_valida(self.b.get("cor"), CORES[semente % len(CORES)])
        self.fonte = FONTES.get(self.b.get("fonte")) or list(FONTES.values())[(semente >> 4) % len(FONTES)]
        composicao = self.b.get("composicao")
        if composicao not in COMPOSICOES:
            composicao = COMPOSICOES[(semente >> 8) % len(COMPOSICOES)]
        if composicao != "tipografica" and not self.fotos.get("abertura"):
            composicao = "tipografica"
        self.composicao = composicao
        self.ordem = ORDENS[(semente >> 12) % len(ORDENS)]
        self.raio = (14, 20, 28)[(semente >> 16) % 3]
        self.rotulo_tipo = (semente >> 20) % 3
        self.contador = 0
        self.whats = link_whatsapp(self.b.get("whatsapp"), self.nome)

    def rotulo(self, texto):
        self.contador += 1
        n = f"{self.contador + 1:02d}"
        if self.rotulo_tipo == 0:
            return f'<p class="rotulo mono">[{n}] // {e(texto)}</p>'
        if self.rotulo_tipo == 1:
            return f'<p class="rotulo pilula">{e(texto)}</p>'
        return f'<p class="rotulo linha">{e(texto)}</p>'

    def botao(self, texto="Marcar consulta", classe=""):
        destino = self.whats or "#contato"
        alvo = ' target="_blank" rel="noopener"' if self.whats else ""
        return f'<a class="botao {classe}" href="{e(destino)}"{alvo}>{e(texto)}<span aria-hidden="true">→</span></a>'

    def foto(self, papel, alt, classe=""):
        arquivo = self.fotos.get(papel)
        return f'<img class="{classe}" src="img/{e(arquivo)}" alt="{e(alt)}">' if arquivo else ""

    def abertura(self):
        frase = self.b.get("abertura")
        titulo = e(frase) if frase else e(ABERTURAS[(self.semente >> 24) % len(ABERTURAS)])
        selo = "" if frase else exemplo()
        apoio = self.b.get("apoio") or f"{self.emp.get('bairro_nome') or 'Goiânia'}, Goiânia. Conheça a clínica e fale direto com a equipe."
        especialidade = f'<p class="sobretitulo">{e(self.b.get("especialidade"))}</p>' if self.b.get("especialidade") else ""
        texto = f'{especialidade}<h1>{titulo}</h1>{selo}<p class="apoio">{e(apoio)}</p>{self.botao()}'
        if self.composicao == "cartao":
            return f'<section class="hero hero-cartao">{self.foto("abertura", "Foto da " + self.nome)}<div class="hero-texto">{texto}</div></section>'
        if self.composicao == "lado":
            return f'<section class="hero hero-lado grade"><div class="hero-texto">{texto}</div>{self.foto("abertura", "Foto da " + self.nome)}</section>'
        return f'<section class="hero hero-tipo grade"><div class="hero-texto">{texto}</div><p class="nome-gigante" aria-hidden="true">{e(self.nome)}</p></section>'

    def reconhece(self):
        itens = pares(self.b.get("situacoes"))
        selo = "" if itens else exemplo()
        itens = itens or list(SITUACOES)
        botoes = "".join(
            f'<button class="troca-item" data-i="{i}" aria-pressed="{"true" if i == 0 else "false"}">{e(t)}</button>'
            for i, (t, _) in enumerate(itens))
        paineis = "".join(
            f'<div class="troca-painel" data-i="{i}"{"" if i == 0 else " hidden"}><h3>{e(t)}</h3><p>{e(c)}</p></div>'
            for i, (t, c) in enumerate(itens))
        return f'''<section class="grade secao">{self.rotulo("Por que as pessoas procuram")}
<h2>Alguma dessas situações é a sua?</h2>{selo}
<div class="troca"><div class="troca-lista">{botoes}</div><div class="troca-area">{paineis}{self.foto("espaco", "Ambiente da " + self.nome)}</div></div></section>'''

    def metodo(self):
        itens = pares(self.b.get("passos"))
        selo = "" if itens else exemplo()
        itens = itens or list(PASSOS)
        cartoes = "".join(
            f'<article class="passo"><span class="mono">{i + 1:02d}</span><h3>{e(t)}</h3><p>{e(c)}</p></article>'
            for i, (t, c) in enumerate(itens))
        return f'''<section class="grade secao">{self.rotulo("Como funciona")}
<h2>O que acontece quando você chega</h2>{selo}<div class="passos">{cartoes}</div></section>'''

    def diferenca(self):
        itens = pares(self.b.get("diferencas"))
        if not itens:
            return ""
        cartoes = "".join(f'<article class="dif"><h3>{e(t)}</h3><p>{e(c)}</p></article>' for t, c in itens)
        return f'''<section class="grade secao">{self.rotulo("O que muda aqui")}
<h2>O que você encontra na {e(self.nome)}</h2><div class="difs">{cartoes}</div></section>'''

    def inscricao(self):
        nome = self.b.get("profissional")
        cro = self.b.get("cro")
        return (e(nome) if nome else confirmar("Nome do dentista"),
                f"CRO-GO {e(cro)}" if cro else confirmar("Número do CRO"))

    def quem(self):
        nome, cro = self.inscricao()
        bio = f'<p>{e(self.b.get("bio"))}</p>' if self.b.get("bio") else ""
        area = f'<p class="area">{e(self.b.get("especialidade"))}</p>' if self.b.get("especialidade") else ""
        foto = self.foto("equipe", f"Foto de {self.b.get('profissional') or 'quem atende'}")
        classe = "quem com-foto" if foto else "quem sem-foto"
        return f'''<section class="grade secao"><div class="{classe}">{foto}<div>{self.rotulo("Quem atende")}
<h2>Quem vai cuidar de você</h2><p class="profissional">{nome}<span>{cro}</span></p>{area}{bio}</div></div></section>'''

    def unica(self):
        texto = self.b.get("unico")
        bairro = self.emp.get("bairro_nome")
        titulo = "O que só a " + self.nome + " tem" if texto else (f"No {bairro}, perto de você" if bairro else "Em Goiânia, perto de você")
        corpo = e(texto) if texto else e(self.emp.get("endereco"))
        ano = self.emp.get("ano_abertura")
        numero = f'''<p class="numero"><b data-conta="{e(ano)}">{e(ano)}</b><span>ano de abertura da empresa</span></p>''' if ano else ""
        return f'''<section class="bloco-cor secao"><div class="grade">{self.rotulo("A clínica")}
<h2 class="acende">{e(titulo)}</h2><p class="acende-texto">{corpo}</p>{numero}</div></section>'''

    def primeiro(self):
        selo = "" if self.b.get("primeiro") else exemplo()
        texto = self.b.get("primeiro") or "Você chama, escolhe um horário e conta o que está sentindo. Na consulta, o dentista explica o que encontrou e os próximos passos."
        return f'''<section class="grade secao"><div class="primeiro">{self.rotulo("Primeiro passo")}
<h2>Como marcar sua consulta</h2>{selo}<p>{e(texto)}</p>{self.botao()}</div></section>'''

    def duvidas(self):
        itens = pares(self.b.get("faq"))
        itens.append(("Onde fica a clínica?", self.emp.get("endereco")))
        blocos = "".join(f'<details><summary>{e(p)}</summary><p>{e(r)}</p></details>' for p, r in itens)
        return f'''<section class="grade secao">{self.rotulo("Dúvidas")}<h2>Antes de chamar</h2><div class="faq">{blocos}</div></section>'''

    def contato(self):
        horario = e(self.b.get("horario")) if self.b.get("horario") else confirmar("Horário de atendimento")
        contato = e(self.b.get("whatsapp")) if self.b.get("whatsapp") else confirmar("WhatsApp da clínica")
        insta = f'<p>Instagram: {e(self.b.get("instagram"))}</p>' if self.b.get("instagram") else ""
        mapa = "https://www.google.com/maps/search/?api=1&query=" + e(f"{self.nome} {self.emp.get('endereco', '')}").replace(" ", "+")
        return f'''<section class="contato secao" id="contato"><div class="grade">{self.rotulo("Contato")}
<h2>Venha conhecer a {e(self.nome)}</h2><div class="contato-colunas"><div><p>{e(self.emp.get("endereco"))}</p>
<p><a href="{mapa}" target="_blank" rel="noopener">Ver no mapa</a></p></div><div><p>{horario}</p><p>{contato}</p>{insta}</div></div>{self.botao("Marcar consulta", "invertido")}</div></section>'''

    def rodape(self):
        nome, cro = self.inscricao()
        rt = self.b.get("responsavel") or self.b.get("profissional")
        rt_cro = self.b.get("cro_responsavel") or self.b.get("cro")
        responsavel = f"{e(rt)}, CRO-GO {e(rt_cro)}" if rt and rt_cro else confirmar("Responsável técnico e CRO")
        return f'''<footer class="grade rodape"><p><b>{e(self.nome)}</b> · CNPJ {e(self.emp.get("cnpj_formatado"))}</p>
<p>{nome} · {cro} · Cirurgião-dentista</p><p>Responsável técnico: {responsavel}</p><p>Proposta de site por {_autor()}. Esta página não é o site oficial da clínica.</p></footer>'''

    def css(self):
        cor = self.cor
        sobre_cor = "#ffffff" if luminancia(cor) < 0.45 else "#0a0a0a"
        return f''':root{{--cor:{cor};--sobre:{sobre_cor};--claro:{tom(cor, .95, .45)};--medio:{tom(cor, .88, .4)};--tinta:{tom(cor, .1, .3)};--suave:#5a6068;--raio:{self.raio}px;--x:clamp(20px,4vw,56px);--max:1240px}}
*{{box-sizing:border-box}}html{{scroll-behavior:smooth}}body{{margin:0;background:#fff;color:var(--tinta);font:17px/1.55 '{self.fonte}',sans-serif;-webkit-font-smoothing:antialiased}}
.grade{{width:100%;max-width:calc(var(--max) + var(--x)*2);margin:0 auto;padding-left:var(--x);padding-right:var(--x)}}
.mono{{font-family:'Geist Mono',monospace}}h1,h2,h3{{font-weight:500;margin:0}}h1{{font-size:clamp(38px,5.6vw,76px);line-height:1.04;letter-spacing:-.035em;max-width:15ch}}
h2{{font-size:clamp(30px,3.6vw,50px);line-height:1.08;letter-spacing:-.03em;max-width:20ch}}h3{{font-size:21px;letter-spacing:-.01em}}p{{margin:0}}img{{display:block;width:100%;object-fit:cover}}
.aviso-previa{{background:var(--tinta);color:#fff;font-size:13px;padding:8px var(--x);text-align:center}}.confirmar{{background:#fff1b8;color:#5c4a00;padding:1px 7px;border-radius:6px;font-size:.88em}}
.selo-exemplo{{display:inline-block;margin-top:12px;background:#fff1b8;color:#5c4a00;font-size:12.5px;padding:3px 9px;border-radius:99px}}
.topo{{display:flex;justify-content:space-between;align-items:center;gap:16px;padding-top:20px;padding-bottom:20px}}.marca{{font-weight:600;letter-spacing:-.02em;font-size:19px}}
.botao{{display:inline-flex;align-items:center;gap:12px;background:var(--cor);color:var(--sobre);padding:13px 22px;border-radius:99px;text-decoration:none;font-weight:500;font-size:16px;transition:transform .25s}}.botao:hover{{transform:translateY(-2px)}}.botao.invertido{{background:#fff;color:var(--tinta);margin-top:32px}}
.topo .botao{{padding:9px 17px;font-size:14px}}.hero{{margin-bottom:clamp(56px,8vw,110px)}}.hero .apoio{{margin:18px 0 26px;max-width:46ch;font-size:19px}}.sobretitulo{{font-weight:500;color:var(--cor);margin-bottom:14px}}
.hero-cartao{{position:relative;margin-left:12px;margin-right:12px;border-radius:calc(var(--raio) + 6px);overflow:hidden;min-height:min(86vh,780px);display:flex;align-items:flex-end;color:#fff;background:var(--tinta)}}.hero-cartao img{{position:absolute;inset:0;height:100%;opacity:.72}}.hero-cartao .hero-texto{{position:relative;padding:clamp(24px,5vw,64px)}}.hero-cartao .sobretitulo{{color:#fff}}
.hero-lado{{display:grid;grid-template-columns:minmax(0,6fr) minmax(0,5fr);gap:clamp(24px,5vw,72px);align-items:center;padding-top:24px}}.hero-lado img{{border-radius:var(--raio);aspect-ratio:4/5}}
.hero-tipo{{padding-top:clamp(32px,6vw,80px);overflow:hidden}}.nome-gigante{{margin-top:clamp(32px,5vw,72px);font-size:clamp(46px,11vw,170px);line-height:.95;letter-spacing:-.05em;font-weight:500;color:var(--medio);overflow-wrap:anywhere}}
.secao{{padding-top:clamp(56px,8vw,110px);padding-bottom:clamp(56px,8vw,110px)}}.rotulo{{font-size:13px;margin-bottom:18px;color:var(--suave)}}.rotulo.mono{{letter-spacing:.06em;text-transform:uppercase}}.rotulo.pilula{{display:inline-block;background:var(--claro);color:var(--cor);padding:4px 12px;border-radius:99px;font-weight:500}}.rotulo.linha{{border-top:1px solid var(--medio);padding-top:12px;font-weight:500}}
.troca{{display:grid;grid-template-columns:minmax(0,5fr) minmax(0,7fr);gap:24px;background:var(--claro);border-radius:var(--raio);padding:clamp(20px,3vw,40px);margin-top:32px}}.troca-lista{{display:flex;flex-direction:column;gap:2px}}.troca-item{{all:unset;cursor:pointer;padding:12px 0;font-size:clamp(19px,2vw,24px);color:var(--suave);transition:color .25s,transform .25s}}.troca-item[aria-pressed=true]{{color:var(--tinta);transform:translateX(10px)}}.troca-item:focus-visible{{outline:2px solid var(--cor)}}.troca-area{{background:#fff;border-radius:calc(var(--raio) - 4px);padding:clamp(20px,3vw,40px);display:flex;flex-direction:column;justify-content:center;gap:18px}}.troca-area h3{{font-size:clamp(24px,2.6vw,34px);margin-bottom:12px;letter-spacing:-.02em}}.troca-area img{{border-radius:calc(var(--raio) - 8px);aspect-ratio:16/9}}
.passos{{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:12px;margin-top:32px}}.passo{{border:1px solid var(--medio);border-radius:var(--raio);padding:26px;transition:background .5s,color .5s,border-color .5s}}.passo .mono{{color:var(--cor);font-size:13px}}.passo h3{{margin:44px 0 8px}}.passo p{{color:var(--suave)}}.passo.ativo{{background:var(--cor);border-color:var(--cor);color:var(--sobre)}}.passo.ativo p,.passo.ativo .mono{{color:inherit}}
.difs{{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px;margin-top:32px}}.dif{{background:var(--claro);border-radius:var(--raio);padding:26px}}.dif p{{margin-top:8px;color:var(--suave)}}
.quem{{display:grid;gap:clamp(24px,5vw,72px);align-items:center}}.quem.com-foto{{grid-template-columns:minmax(0,5fr) minmax(0,6fr)}}.quem img{{border-radius:var(--raio);aspect-ratio:4/5}}.profissional{{margin-top:22px;font-size:22px;display:flex;flex-wrap:wrap;gap:6px 16px;align-items:baseline}}.profissional span{{font-size:15px;color:var(--suave)}}.area{{color:var(--cor);font-weight:500;margin-top:8px}}.quem p+p{{margin-top:10px}}
.bloco-cor{{background:var(--cor);color:var(--sobre)}}.bloco-cor .rotulo{{color:inherit;background:transparent;padding-left:0;border-color:currentColor}}.acende-texto{{margin-top:20px;font-size:clamp(19px,2vw,24px);max-width:46ch}}.numero{{margin-top:44px;display:flex;align-items:baseline;gap:14px;flex-wrap:wrap}}.numero b{{font-size:clamp(46px,6vw,84px);font-weight:500;letter-spacing:-.04em;line-height:1}}
.primeiro{{background:var(--claro);border-radius:var(--raio);padding:clamp(28px,5vw,64px)}}.primeiro p:not(.rotulo){{max-width:56ch;margin:18px 0 26px}}
.faq{{margin-top:32px;border-top:1px solid var(--medio)}}details{{border-bottom:1px solid var(--medio);padding:18px 0}}summary{{cursor:pointer;font-size:19px;font-weight:500}}details p{{margin-top:10px;color:var(--suave);max-width:62ch}}
.contato{{background:var(--tinta);color:#fff}}.contato .rotulo{{color:#fff;background:transparent;padding-left:0}}.contato a:not(.botao){{color:inherit}}.contato-colunas{{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:24px;margin-top:32px}}.contato-colunas p+p{{margin-top:8px}}
.rodape{{padding-top:32px;padding-bottom:90px;font-size:14px;color:var(--suave)}}.rodape p+p{{margin-top:4px}}.barra-celular{{display:none}}
.revela{{opacity:0;transform:translateY(20px);transition:opacity .7s,transform .7s}}.revela.visto{{opacity:1;transform:none}}
@media (max-width:760px){{.hero-lado,.troca,.quem.com-foto{{grid-template-columns:1fr}}.topo .botao{{display:none}}.barra-celular{{display:block;position:fixed;left:12px;right:12px;bottom:12px;z-index:5}}.barra-celular .botao{{display:flex;justify-content:center}}}}
@media (prefers-reduced-motion:reduce){{*{{animation:none!important;transition:none!important;scroll-behavior:auto!important}}.revela{{opacity:1;transform:none}}}}'''

    def js(self):
        return """document.querySelectorAll('.troca').forEach(function(t){var b=t.querySelectorAll('.troca-item'),p=t.querySelectorAll('.troca-painel');b.forEach(function(x){x.addEventListener('click',function(){b.forEach(function(y){y.setAttribute('aria-pressed',y===x)});p.forEach(function(y){y.hidden=y.dataset.i!==x.dataset.i})})})});
var calmo=matchMedia('(prefers-reduced-motion: reduce)').matches;
var ver=new IntersectionObserver(function(es){es.forEach(function(en){if(en.isIntersecting){en.target.classList.add('visto');ver.unobserve(en.target)}})},{threshold:.12});
document.querySelectorAll('.secao').forEach(function(s){s.classList.add('revela');ver.observe(s)});
if(!calmo){var ps=document.querySelectorAll('.passo'),i=0;if(ps.length){ps[0].classList.add('ativo');setInterval(function(){ps[i].classList.remove('ativo');i=(i+1)%ps.length;ps[i].classList.add('ativo')},2400)}}"""

    def renderizar(self):
        secoes = "\n".join(getattr(self, nome)() for nome in self.ordem)
        fonte = self.fonte.replace(" ", "+")
        return f'''<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow"><title>{e(self.nome)} · Prévia</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?family={fonte}:wght@400;500;600&family=Geist+Mono:wght@400&display=swap" rel="stylesheet">
<style>{self.css()}</style></head><body><div class="aviso-previa">Este é um site de exemplo, feito por {_autor()}. Se aprovarem, montamos a versão completa e mais elaborada. Os itens em amarelo precisam ser confirmados.</div>
<header class="grade topo"><span class="marca">{e(self.nome)}</span>{self.botao()}</header>
{self.abertura()}{secoes}{self.contato()}{self.rodape()}<div class="barra-celular">{self.botao()}</div><script>{self.js()}</script></body></html>'''


def pendencias(briefing):
    """O que ainda falta para a prévia parecer feita para aquela clínica."""
    b = briefing or {}
    faltas = []
    for campo, texto in (("abertura", "frase de abertura"), ("profissional", "nome do dentista"), ("cro", "número do CRO"),
                         ("responsavel", "responsável técnico"), ("whatsapp", "WhatsApp"), ("horario", "horário"),
                         ("cor", "cor da marca"), ("unico", "o que só ela tem"), ("diferencas", "diferenças")):
        if not b.get(campo):
            faltas.append(texto)
    if not (b.get("fotos") or {}).get("abertura"):
        faltas.append("foto de abertura")
    return faltas


def gerar(empresa, briefing):
    return Previa(empresa, briefing).renderizar()
