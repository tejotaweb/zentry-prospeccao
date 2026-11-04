#!/usr/bin/env python3
"""Lê a base aberta de CNPJ da Receita, sem guardar os arquivos inteiros depois de lidos,
e salva só os estabelecimentos de um ramo (CNAE principal) em uma cidade.

Uso: filtrar_receita.py <mes AAAA-MM> <cnae> <cidade> <arquivo de saida.csv>
Exemplo: filtrar_receita.py 2026-10 8630504 GOIANIA dados/dentistas-goiania.csv
"""
import csv
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

COMPARTILHAMENTO = "YggdBLfdninEJX9"  # link público da Receita, não é senha
BASE = "https://arquivos.receitafederal.gov.br/public.php/webdav"
TENTATIVAS = 30

ESTAB = ["cnpj_basico", "ordem", "dv", "matriz_filial", "nome_fantasia", "situacao",
         "data_situacao", "motivo", "cidade_exterior", "pais", "data_inicio", "cnae",
         "cnae_secundario", "tipo_logradouro", "logradouro", "numero", "complemento",
         "bairro", "cep", "uf", "municipio", "ddd1", "tel1", "ddd2", "tel2", "ddd_fax",
         "fax", "email", "situacao_especial", "data_situacao_especial"]


def linhas(mes, arquivo):
    """Baixa um zip para uma pasta temporária, devolve as linhas do CSV de dentro dele
    e apaga o zip no fim. Alguns zips passam de 4 GB abertos, então o funzip não serve."""
    url = f"{BASE}/{mes}/{arquivo}"
    with tempfile.TemporaryDirectory(prefix="receita-") as pasta:
        destino = os.path.join(pasta, arquivo)
        for tentativa in range(1, TENTATIVAS + 1):
            baixou = subprocess.run(["curl", "-sS", "--fail", "--retry", "5", "--retry-all-errors",
                                     "-C", "-", "-u", f"{COMPARTILHAMENTO}:", "-o", destino, url]).returncode == 0
            if baixou:
                break
            print(f"{arquivo}: falha na tentativa {tentativa} de {TENTATIVAS}, esperando 60 s", flush=True)
            time.sleep(60)
        else:
            raise SystemExit(f"Não consegui baixar {arquivo}. O progresso ficou salvo: rode de novo.")
        with zipfile.ZipFile(destino) as z:
            with z.open(z.namelist()[0]) as bruto:
                texto = io.TextIOWrapper(bruto, encoding="latin-1", newline="")
                yield from csv.reader(texto, delimiter=";", quotechar='"')


def main():
    mes, cnae, cidade, saida = sys.argv[1:5]

    nome_cnae = next((r[1] for r in linhas(mes, "Cnaes.zip") if r[0] == cnae), None)
    municipio = next((r[0] for r in linhas(mes, "Municipios.zip") if r[1] == cidade), None)
    if not nome_cnae or not municipio:
        raise SystemExit(f"Não achei o CNAE {cnae} ou a cidade {cidade}")
    print(f"CNAE {cnae}: {nome_cnae} | {cidade}: código {municipio}", flush=True)

    # Cada arquivo lido fica salvo em uma pasta parcial: se a internet cair, recomeça de onde parou.
    parcial = Path(saida).parent / f"parcial-{mes}-{cnae}-{cidade}"
    parcial.mkdir(parents=True, exist_ok=True)

    def com_progresso(nome, ler):
        guardado = parcial / f"{nome}.json"
        if guardado.exists():
            return json.loads(guardado.read_text(encoding="utf-8"))
        resultado = ler()
        temporario = guardado.with_suffix(".tmp")
        temporario.write_text(json.dumps(resultado, ensure_ascii=False), encoding="utf-8")
        os.replace(temporario, guardado)
        return resultado

    achados = []
    for n in range(10):
        achados += com_progresso(f"Estabelecimentos{n}", lambda: [
            dict(zip(ESTAB, r)) for r in linhas(mes, f"Estabelecimentos{n}.zip")
            if r[20] == municipio and r[11] == cnae])
        print(f"Estabelecimentos{n}: {len(achados)} achados", flush=True)

    basicos = {a["cnpj_basico"] for a in achados}
    empresas = {}
    for n in range(10):
        empresas.update(com_progresso(f"Empresas{n}", lambda: {
            r[0]: {"razao_social": r[1], "natureza": r[2], "porte": r[5]}
            for r in linhas(mes, f"Empresas{n}.zip") if r[0] in basicos}))
        print(f"Empresas{n}: {len(empresas)} de {len(basicos)} encontradas", flush=True)

    naturezas = {r[0]: r[1] for r in linhas(mes, "Naturezas.zip")}
    campos = ESTAB + ["razao_social", "natureza", "natureza_nome", "porte"]
    with open(saida, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        for a in achados:
            e = empresas.get(a["cnpj_basico"], {})
            w.writerow({**a, **e, "natureza_nome": naturezas.get(e.get("natureza"), "")})
    print(f"Pronto: {len(achados)} estabelecimentos em {saida}", flush=True)


if __name__ == "__main__":
    main()
