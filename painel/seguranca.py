"""Segurança e contas do painel no ar (04/11/2026).

- Quem chega pela internet (túnel da Cloudflare) precisa estar logado em tudo, inclusive nas prévias.
- Quem usa no próprio Mac (localhost, sem os cabeçalhos da Cloudflare) segue entrando direto: é assim que o Claude
  altera o sistema e marca as conversas.
- Contas: qualquer pessoa pode se cadastrar (e-mail e senha, ou Google). A conta nasce "pendente" e só entra depois que
  o administrador  libera. A conta criada no próprio Mac (localhost/criar-senha) já nasce administradora.
- Senha guardada só como hash PBKDF2 (310 mil voltas, sal próprio). Ninguém lê a senha, nem o Claude.
- Sessão: código aleatório num cookie HttpOnly + Secure + SameSite=Lax; no arquivo fica só o hash dele. Vale 30 dias.
- Tentativas: no máximo 5 logins errados e 5 cadastros a cada 15 minutos por IP.
"""
import hashlib
import hmac
import json
import re
import secrets
import threading
import time
from pathlib import Path

VOLTAS = 310_000
DURACAO = 30 * 86400
COOKIE = "zentry_sessao"
MAX_ERROS, JANELA = 5, 15 * 60
EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,190}\.[a-z]{2,}$", re.I)

_trava = threading.Lock()
_tentativas = {}


class ErroConta(ValueError):
    pass


class Seguranca:
    def __init__(self, dados: Path):
        self.usuarios_arq = dados / "usuarios.json"
        self.sessoes_arq = dados / "sessoes.json"

    # ---------- arquivos ----------
    def _ler(self, arq, padrao):
        try:
            return json.loads(arq.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return padrao

    def _gravar(self, arq, dados):
        tmp = arq.with_suffix(".tmp")
        tmp.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.chmod(0o600)
        tmp.replace(arq)

    def _contas(self):
        return self._ler(self.usuarios_arq, {"usuarios": []}).get("usuarios", [])

    def _salvar_contas(self, contas):
        self._gravar(self.usuarios_arq, {"usuarios": contas})

    @staticmethod
    def publico(c):
        """O que pode aparecer na tela (nunca o hash)."""
        saida = {k: c.get(k, "") for k in ("id", "email", "nome", "metodo", "status", "papel", "criado_em", "aprovado_em", "ultimo_acesso")}
        saida["creditos"] = int(c.get("creditos", 0) or 0)
        return saida

    # ---------- senha ----------
    @staticmethod
    def _hash(senha, sal):
        return hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), bytes.fromhex(sal), VOLTAS).hex()

    @staticmethod
    def _conferir_email(email):
        email = str(email or "").strip().lower()
        if not EMAIL.match(email):
            raise ErroConta("Digite um e-mail válido.")
        return email

    @staticmethod
    def _conferir_senha(senha):
        if len(senha or "") < 10:
            raise ErroConta("A senha precisa ter pelo menos 10 caracteres.")
        if len(senha) > 200:
            raise ErroConta("Senha comprida demais.")

    def tem_admin(self):
        return any(c.get("papel") == "admin" and c.get("status") == "ativo" for c in self._contas())

    def por_id(self, id_):
        return next((c for c in self._contas() if c["id"] == id_), None)

    def por_email(self, email):
        email = str(email or "").strip().lower()
        return next((c for c in self._contas() if c.get("email") == email), None)

    def listar(self):
        return [self.publico(c) for c in sorted(self._contas(), key=lambda c: c.get("criado_em", ""), reverse=True)]

    def _nova(self, email, nome, metodo, status, papel, senha=None, google_sub=""):
        c = {"id": secrets.token_hex(8), "email": email, "nome": str(nome or "").strip()[:80] or email.split("@")[0], "metodo": metodo,
             "status": status, "papel": papel, "criado_em": time.strftime("%Y-%m-%d %H:%M"), "aprovado_em": "", "google_sub": google_sub}
        if status == "ativo":
            c["aprovado_em"] = c["criado_em"]
        if senha is not None:
            c["sal"] = secrets.token_hex(16)
            c["hash"] = self._hash(senha, c["sal"])
        return c

    def criar_admin(self, email, senha, nome=""):
        """Só pelo próprio Mac. Se o e-mail já existe, vira administrador e troca a senha."""
        email = self._conferir_email(email)
        self._conferir_senha(senha)
        with _trava:
            contas = self._contas()
            atual = next((c for c in contas if c.get("email") == email), None)
            if atual:
                atual.update({"sal": secrets.token_hex(16), "papel": "admin", "status": "ativo", "metodo": atual.get("metodo") or "senha"})
                atual["hash"] = self._hash(senha, atual["sal"])
                conta = atual
            else:
                conta = self._nova(email, nome, "senha", "ativo", "admin", senha)
                contas.append(conta)
            self._salvar_contas(contas)
            self._derrubar_sessoes(conta["id"])
        return self.publico(conta)

    def cadastrar(self, email, senha, nome):
        """Cadastro aberto: nasce pendente, espera o administrador liberar."""
        email = self._conferir_email(email)
        self._conferir_senha(senha)
        if len(str(nome or "").strip()) < 2:
            raise ErroConta("Digite o seu nome.")
        with _trava:
            contas = self._contas()
            if any(c.get("email") == email for c in contas):
                raise ErroConta("Já existe uma conta com esse e-mail. Use \"Entrar\".")
            conta = self._nova(email, nome, "senha", "pendente", "usuario", senha)
            contas.append(conta)
            self._salvar_contas(contas)
        return self.publico(conta)

    def entrar_google(self, email, nome, sub):
        """Conta do Google: acha pela identificação do Google ou pelo e-mail; se não existe, cria pendente."""
        email = self._conferir_email(email)
        with _trava:
            contas = self._contas()
            conta = next((c for c in contas if sub and c.get("google_sub") == sub), None) or next((c for c in contas if c.get("email") == email), None)
            nova = conta is None
            if nova:
                conta = self._nova(email, nome, "google", "pendente", "usuario", None, sub)
                contas.append(conta)
            elif not conta.get("google_sub"):
                conta["google_sub"] = sub
            self._salvar_contas(contas)
        return self.publico(conta), nova

    def conferir(self, email, senha):
        """Devolve a conta se a senha bate (qualquer status; quem chama decide se deixa entrar)."""
        email = str(email or "").strip().lower()
        conta = self.por_email(email)
        if conta and conta.get("hash"):
            if hmac.compare_digest(conta["hash"], self._hash(senha or "", conta["sal"])):
                return conta
            return None
        self._hash(senha or "", "00" * 16)  # mesmo tempo de resposta quando a conta não existe
        return None

    def mudar(self, id_, acao):
        with _trava:
            contas = self._contas()
            conta = next((c for c in contas if c["id"] == id_), None)
            if not conta:
                raise ErroConta("Conta não encontrada.")
            if acao == "aprovar":
                conta["status"], conta["aprovado_em"] = "ativo", time.strftime("%Y-%m-%d %H:%M")
            elif acao in ("recusar", "bloquear"):
                if conta.get("papel") == "admin" and sum(1 for c in contas if c.get("papel") == "admin" and c.get("status") == "ativo") <= 1:
                    raise ErroConta("Não dá para bloquear o único administrador.")
                conta["status"] = "recusado" if acao == "recusar" else "bloqueado"
                self._derrubar_sessoes(id_)
            elif acao == "remover":
                if conta.get("papel") == "admin":
                    raise ErroConta("Administrador não pode ser removido por aqui.")
                contas = [c for c in contas if c["id"] != id_]
                self._derrubar_sessoes(id_)
            else:
                raise ErroConta("Ação desconhecida.")
            self._salvar_contas(contas)
        return self.publico(conta)

    # ---------- créditos: 1 crédito = 1 empresa pesquisada (o administrador não gasta) ----------
    def creditar(self, id_, quantidade, motivo):
        """Soma (ou tira, se negativo) créditos. Devolve o saldo novo."""
        with _trava:
            contas = self._contas()
            conta = next((c for c in contas if c["id"] == id_), None)
            if not conta:
                raise ErroConta("Conta não encontrada.")
            saldo = max(0, int(conta.get("creditos", 0) or 0) + int(quantidade))
            conta["creditos"] = saldo
            conta.setdefault("extrato", []).append({"quando": time.strftime("%Y-%m-%d %H:%M"), "quantidade": int(quantidade), "motivo": motivo, "saldo": saldo})
            conta["extrato"] = conta["extrato"][-200:]
            self._salvar_contas(contas)
        return saldo

    def debitar(self, id_, quantidade, motivo):
        """Tira créditos só se tiver saldo. Devolve True se tirou."""
        with _trava:
            contas = self._contas()
            conta = next((c for c in contas if c["id"] == id_), None)
            saldo = int((conta or {}).get("creditos", 0) or 0)
            if not conta or saldo < quantidade:
                return False
            conta["creditos"] = saldo - quantidade
            conta.setdefault("extrato", []).append({"quando": time.strftime("%Y-%m-%d %H:%M"), "quantidade": -quantidade, "motivo": motivo, "saldo": saldo - quantidade})
            conta["extrato"] = conta["extrato"][-200:]
            self._salvar_contas(contas)
        return True

    def marcar_acesso(self, id_):
        with _trava:
            contas = self._contas()
            for c in contas:
                if c["id"] == id_:
                    c["ultimo_acesso"] = time.strftime("%Y-%m-%d %H:%M")
            self._salvar_contas(contas)

    # ---------- tentativas ----------
    def bloqueado(self, chave):
        agora = time.time()
        with _trava:
            _tentativas[chave] = [t for t in _tentativas.get(chave, []) if agora - t < JANELA]
            return len(_tentativas[chave]) >= MAX_ERROS

    def errou(self, chave):
        with _trava:
            _tentativas.setdefault(chave, []).append(time.time())

    # ---------- sessão ----------
    def abrir_sessao(self, id_):
        token = secrets.token_urlsafe(32)
        with _trava:
            sessoes = {k: v for k, v in self._ler(self.sessoes_arq, {}).items() if v.get("expira", 0) > time.time()}
            sessoes[hashlib.sha256(token.encode()).hexdigest()] = {"conta": id_, "expira": time.time() + DURACAO}
            self._gravar(self.sessoes_arq, sessoes)
        self.marcar_acesso(id_)
        return token

    def _derrubar_sessoes(self, id_):
        sessoes = self._ler(self.sessoes_arq, {})
        self._gravar(self.sessoes_arq, {k: v for k, v in sessoes.items() if v.get("conta") != id_})

    def fechar_sessao(self, token):
        if not token:
            return
        with _trava:
            sessoes = self._ler(self.sessoes_arq, {})
            sessoes.pop(hashlib.sha256(token.encode()).hexdigest(), None)
            self._gravar(self.sessoes_arq, sessoes)

    def conta_da_sessao(self, token):
        """A conta dona da sessão, só se ainda estiver ativa."""
        if not token:
            return None
        s = self._ler(self.sessoes_arq, {}).get(hashlib.sha256(token.encode()).hexdigest())
        if not s or s.get("expira", 0) <= time.time():
            return None
        conta = self.por_id(s.get("conta"))
        return conta if conta and conta.get("status") == "ativo" else None

    @staticmethod
    def cookie(token, apagar=False, nome=COOKIE, duracao=DURACAO):
        if apagar:
            return f"{nome}=; Path=/; Max-Age=0; HttpOnly; Secure; SameSite=Lax"
        return f"{nome}={token}; Path=/; Max-Age={duracao}; HttpOnly; Secure; SameSite=Lax"

    @staticmethod
    def do_cookie(cabecalho, nome=COOKIE):
        for parte in str(cabecalho or "").split(";"):
            n, _, valor = parte.strip().partition("=")
            if n == nome:
                return valor
        return ""
