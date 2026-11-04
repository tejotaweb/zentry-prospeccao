"""Espaço separado por conta (04/11/2026, etapa 2).

Cada conta liberada (que não é administradora) tem a própria pasta em dados/contas/<id>/ e o próprio processo do painel
(o mesmo servidor.py, com PROSPECCAO_CONTA). O painel principal confere o login e repassa os pedidos da pessoa para o
processo dela, que só enxerga a pasta dela. A chave do Outscraper e o contador de uso são os do administrador (links), porque é
ele quem paga a busca; por isso a busca gasta créditos que ele libera.
"""
import http.client
import json
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

PRIMEIRA_PORTA = 4501
PASSA = ("Content-Type", "Location", "Cache-Control", "Content-Disposition", "X-Robots-Tag")


class Espacos:
    def __init__(self, dados: Path, servidor: Path):
        self.dados = dados
        self.base = dados / "contas"
        self.base.mkdir(parents=True, exist_ok=True)
        self.servidor = servidor
        self.portas_arq = dados / "contas-portas.json"
        self.processos = {}
        self.trava = threading.Lock()

    def pasta(self, id_):
        return self.base / id_

    def _porta(self, id_):
        try:
            portas = json.loads(self.portas_arq.read_text())
        except (OSError, ValueError):
            portas = {}
        if id_ not in portas:
            portas[id_] = max([PRIMEIRA_PORTA - 1, *portas.values()]) + 1
            self.portas_arq.write_text(json.dumps(portas))
        return portas[id_]

    @staticmethod
    def _responde(porta):
        try:
            with socket.create_connection(("127.0.0.1", porta), timeout=0.5):
                return True
        except OSError:
            return False

    def garantir(self, conta):
        """Cria a pasta da conta (na primeira vez) e liga o processo dela se não estiver rodando."""
        id_ = conta["id"]
        with self.trava:
            pasta = self.pasta(id_)
            if not pasta.exists():
                pasta.mkdir(parents=True)
                (pasta / "config.json").write_text(json.dumps({"perfil": {"nome": conta.get("nome", "")}}, ensure_ascii=False))
            for nome in ("chave-outscraper.txt", "outscraper-uso.json"):  # a busca é paga pelo administrador: mesma chave e mesmo contador
                alvo, link = self.dados / nome, pasta / nome
                if alvo.exists() and not link.exists():
                    link.symlink_to(alvo)
            porta = self._porta(id_)
            proc = self.processos.get(id_)
            if proc and proc.poll() is None and self._responde(porta):
                return porta
            if not self._responde(porta):
                log = open(self.dados / "logs" / f"conta-{id_}.log", "a")
                env = {**os.environ, "PROSPECCAO_DADOS": str(pasta), "PROSPECCAO_PORTA": str(porta), "PROSPECCAO_CONTA": id_,
                       "PROSPECCAO_MARCA": conta.get("nome", ""), "PYTHONUNBUFFERED": "1"}
                self.processos[id_] = subprocess.Popen([sys.executable, str(self.servidor)], env=env, stdout=log, stderr=log, cwd=str(self.servidor.parent.parent))
                for _ in range(60):
                    if self._responde(porta):
                        break
                    time.sleep(0.2)
            return porta

    def repassar(self, porta, metodo, caminho, corpo=b"", cabecalhos=None):
        """Faz o pedido no processo da conta e devolve (código, cabeçalhos, corpo)."""
        con = http.client.HTTPConnection("127.0.0.1", porta, timeout=600)
        ch = {k: v for k, v in (cabecalhos or {}).items() if k.lower() in ("content-type", "accept", "range")}
        con.request(metodo, caminho, body=corpo or None, headers=ch)
        r = con.getresponse()
        dados = r.read()
        saida = [(k, v) for k, v in r.getheaders() if k in PASSA]
        con.close()
        return r.status, saida, dados

    def desligar(self, id_):
        proc = self.processos.pop(id_, None)
        if proc and proc.poll() is None:
            proc.terminate()
