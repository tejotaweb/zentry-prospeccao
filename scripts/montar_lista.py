#!/usr/bin/env python3
"""Transforma o CSV filtrado da Receita em dados/lista.json, com o funil de cada filtro.

Uso: montar_lista.py <csv> <titulo do ramo> [quantidade]
Exemplo: montar_lista.py dados/dentistas-goiania-2026-10.csv "Dentistas · Goiânia" 50
"""
import csv
import json
import random
import re
import sys
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
EMPRESARIO_INDIVIDUAL = "2135"
ATIVA = "02"
MATRIZ = "1"
ANOS_MINIMOS = 3
REDES = re.compile(r"ODONTO\s*COMPANY|ORAL\s*SIN|SORRIDENTS|ODONTOCLINIC|DENTAL\s*CLEAN|AMOR\s*SAUDE|EMDOC|IMPLANTE\s*CENTER|ORTOPLAN|DONA\s*DENTISTA|SOU\s*SMILE|OI\s*DENTE", re.I)
MINUSCULAS = {"de", "da", "do", "das", "dos", "e"}
SIGLAS = {"LTDA", "ME", "EPP", "EIRELI", "SS", "S/S", "S/A", "SA"}


def bonito(texto):
    palavras = []
    for i, p in enumerate(str(texto).split()):
        if p.upper() in SIGLAS:
            palavras.append(p.upper())
        elif p.lower() in MINUSCULAS and i:
            palavras.append(p.lower())
        else:
            palavras.append(p.capitalize())
    return " ".join(palavras)


def sem_sufixo(razao):
    return re.sub(r"\s+(LTDA|EIRELI|ME|EPP|S/?S|S/?A)\.?(\s+(ME|EPP))?\.?$", "", razao.strip(), flags=re.I)


def data_receita(texto):
    try:
        return date(int(texto[:4]), int(texto[4:6]), int(texto[6:8]))
    except (ValueError, IndexError):
        return None


def anos_desde(inicio, hoje):
    return hoje.year - inicio.year - ((hoje.month, hoje.day) < (inicio.month, inicio.day))


def telefone(l):
    return f"({l['ddd1'].strip()}) {l['tel1'].strip()}" if l["ddd1"].strip() and l["tel1"].strip() else ""


def celular(l):
    return len(l["tel1"].strip()) == 9 and l["tel1"].strip().startswith("9")


def formatar_cnpj(c):
    return f"{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]}" if len(c) == 14 else c


def main():
    origem, titulo = sys.argv[1], sys.argv[2]
    quantidade = int(sys.argv[3]) if len(sys.argv) > 3 else 50
    hoje = date.today()
    with open(origem, encoding="utf-8", newline="") as f:
        todas = list(csv.DictReader(f))

    funil = [{"nome": "Na base da Receita", "qtd": len(todas)}]

    def filtro(nome, regra, linhas):
        ficam = [l for l in linhas if regra(l)]
        funil.append({"nome": nome, "qtd": len(ficam)})
        return ficam

    resto = filtro("Ativas", lambda l: l["situacao"] == ATIVA, todas)
    resto = filtro("Só a sede, sem filial", lambda l: l["matriz_filial"] == MATRIZ, resto)
    resto = filtro("Tira empresário individual", lambda l: l["natureza"] != EMPRESARIO_INDIVIDUAL, resto)

    def idade_ok(l):
        inicio = data_receita(l["data_inicio"])
        return inicio is not None and anos_desde(inicio, hoje) >= ANOS_MINIMOS

    resto = filtro(f"Com {ANOS_MINIMOS} anos ou mais", idade_ok, resto)
    resto = filtro("Tira grandes redes", lambda l: not REDES.search(f"{l['nome_fantasia']} {l['razao_social']}"), resto)

    # Sorteio com semente fixa: a lista não muda entre uma rodada e outra.
    # Quem tem nome fantasia e celular vem primeiro, porque é mais fácil de achar e de falar.
    random.Random(2026).shuffle(resto)
    resto.sort(key=lambda l: (not l["nome_fantasia"].strip(), not celular(l)))
    escolhidas = resto[:quantidade]
    funil.append({"nome": "Separadas para conferir", "qtd": len(escolhidas)})

    empresas = []
    for l in escolhidas:
        cnpj = l["cnpj_basico"] + l["ordem"] + l["dv"]
        inicio = data_receita(l["data_inicio"])
        razao = bonito(l["razao_social"])
        nome = bonito(l["nome_fantasia"]) if l["nome_fantasia"].strip() else bonito(sem_sufixo(l["razao_social"]))
        bairro = bonito(l["bairro"])
        partes = [bonito(f"{l['tipo_logradouro']} {l['logradouro']}"), l["numero"].strip(), bonito(l["complemento"]), bairro]
        endereco = ", ".join(p for p in partes if p) + ", Goiânia - GO"
        empresas.append({
            "cnpj": cnpj, "cnpj_formatado": formatar_cnpj(cnpj), "nome": nome, "razao": razao,
            "natureza": l["natureza_nome"], "bairro_nome": bairro, "endereco": endereco, "telefone": telefone(l),
            "anos": anos_desde(inicio, hoje), "ano_abertura": inicio.year,
        })

    saida = {
        "rotulo": titulo, "titulo": "Painel de prospecção", "funil": funil, "empresas": empresas,
        "fonte": f"Fonte: base aberta de CNPJ da Receita Federal, {Path(origem).stem[-7:]}. O telefone pode ser o do contador. Confira antes de usar.",
    }
    destino = RAIZ / "dados" / "lista.json"
    destino.write_text(json.dumps(saida, ensure_ascii=False, indent=1), encoding="utf-8")
    for etapa in funil:
        print(f"{etapa['qtd']:>6}  {etapa['nome']}")
    print("Salvo em", destino)


if __name__ == "__main__":
    main()
