"""E-mail automático e "Entrar com Google" (04/11/2026).

E-mail: pelo Gmail dele (SMTP com "senha de app" do Google; ele mesmo cria e coloca em Configurações → Acesso).
Google: login OAuth oficial (código de autorização). Ele cria o "ID do cliente" no Google Cloud e coloca em Configurações.
As chaves ficam em dados/chaves/ com permissão só do dono (600) e nunca voltam para a tela.
"""
import json
import smtplib
import ssl
import urllib.parse
import urllib.request
from email.message import EmailMessage
from email.utils import formataddr
from pathlib import Path

import os
ENDERECO = os.environ.get("PROSPECCAO_ENDERECO", "http://localhost:4400")


def _ctx():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


class ContasWeb:
    def __init__(self, dados: Path):
        self.pasta = dados / "chaves"
        self.pasta.mkdir(parents=True, exist_ok=True)
        self.pasta.chmod(0o700)

    def _ler(self, nome):
        try:
            return json.loads((self.pasta / nome).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def _gravar(self, nome, dados):
        arq = self.pasta / nome
        arq.touch(mode=0o600)
        arq.chmod(0o600)
        arq.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")

    # ---------- estado (para a tela, sem segredo) ----------
    def situacao(self):
        e, g = self._ler("email.json"), self._ler("google.json")
        return {"email_ligado": bool(e.get("remetente") and e.get("senha_app")), "email_remetente": e.get("remetente", ""),
                "email_avisos": e.get("avisos", ""), "google_ligado": bool(g.get("client_id") and g.get("client_secret")),
                "google_client_id": g.get("client_id", ""), "endereco": ENDERECO}

    def salvar(self, dados):
        """Só grava o que veio preenchido: campo de senha vazio mantém a senha que já estava."""
        e = self._ler("email.json")
        for campo in ("remetente", "senha_app", "avisos"):
            valor = str(dados.get("email_" + campo, "") or "").strip()
            if valor:
                e[campo] = valor.replace(" ", "") if campo == "senha_app" else valor
        if e:
            self._gravar("email.json", e)
        g = self._ler("google.json")
        for campo in ("client_id", "client_secret"):
            valor = str(dados.get("google_" + campo, "") or "").strip()
            if valor:
                g[campo] = valor
        if g:
            self._gravar("google.json", g)
        return self.situacao()

    # ---------- e-mail ----------
    def enviar(self, para, assunto, texto, html=""):
        e = self._ler("email.json")
        if not (e.get("remetente") and e.get("senha_app")):
            return False
        msg = EmailMessage()
        msg["Subject"] = assunto
        msg["From"] = formataddr(("Zentry", e["remetente"]))
        msg["To"] = para
        msg.set_content(texto)
        if html:
            msg.add_alternative(html, subtype="html")
        try:
            with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=_ctx(), timeout=20) as s:
                s.login(e["remetente"], e["senha_app"])
                s.send_message(msg)
            return True
        except Exception as erro:
            print(f"e-mail para {para} não saiu: {erro}", flush=True)
            return False

    def avisos_para(self):
        e = self._ler("email.json")
        return e.get("avisos") or e.get("remetente") or ""

    @staticmethod
    def html(titulo, texto, botao="", link=""):
        bt = (f'<p style="margin:28px 0"><a href="{link}" style="background:#3b82f6;color:#fff;padding:13px 22px;border-radius:10px;'
              f'text-decoration:none;font-weight:600">{botao}</a></p>') if botao else ""
        return (f'<div style="font-family:Inter,Arial,sans-serif;max-width:520px;margin:0 auto;padding:32px 24px;color:#111">'
                f'<p style="font-weight:600;font-size:15px;margin:0 0 24px">Zentry</p><h1 style="font-size:22px;margin:0 0 12px">{titulo}</h1>'
                f'<p style="font-size:15px;line-height:1.6;color:#333">{texto}</p>{bt}'
                f'<p style="font-size:12px;color:#888;margin-top:32px">Zentry · prospecção de sites · {ENDERECO}</p></div>')

    # ---------- Google ----------
    def google_link(self, estado):
        g = self._ler("google.json")
        q = urllib.parse.urlencode({"client_id": g.get("client_id", ""), "redirect_uri": ENDERECO + "/auth/google/volta", "response_type": "code",
                                    "scope": "openid email profile", "state": estado, "prompt": "select_account"})
        return "https://accounts.google.com/o/oauth2/v2/auth?" + q

    def google_trocar(self, codigo):
        """Troca o código pelo token e confere no próprio Google. Devolve (email, nome, sub) ou levanta erro."""
        g = self._ler("google.json")
        corpo = urllib.parse.urlencode({"code": codigo, "client_id": g.get("client_id", ""), "client_secret": g.get("client_secret", ""),
                                        "redirect_uri": ENDERECO + "/auth/google/volta", "grant_type": "authorization_code"}).encode()
        with urllib.request.urlopen(urllib.request.Request("https://oauth2.googleapis.com/token", data=corpo), timeout=20, context=_ctx()) as r:
            token = json.load(r)
        with urllib.request.urlopen("https://oauth2.googleapis.com/tokeninfo?" + urllib.parse.urlencode({"id_token": token["id_token"]}),
                                    timeout=20, context=_ctx()) as r:
            info = json.load(r)
        if info.get("aud") != g.get("client_id") or str(info.get("email_verified")).lower() != "true" or info.get("iss") not in ("accounts.google.com", "https://accounts.google.com"):
            raise ValueError("O Google não confirmou essa conta.")
        return info["email"].lower(), info.get("name") or info.get("given_name") or "", info["sub"]
