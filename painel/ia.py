"""Pesquisa e análise com o Claude Code do computador, pelo plano do administrador (sem API paga e sem Meta).

1. acha e analisa empresas para a lista;
2. faz a análise completa de uma empresa aprovada, a copy do site e os posts de exemplo.
"""
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
METODO = RAIZ / "metodo"
# Claude Code do computador: pesquisa pelo plano do administrador, sem gastar créditos da API
CLAUDE_CODE = os.environ.get("PROSPECCAO_CLAUDE_CODE") or shutil.which("claude") or str(Path.home() / ".local/bin/claude")
MODELO_RAPIDO = os.environ.get("PROSPECCAO_MODELO_RAPIDO", "sonnet")
# Sem conectores, plugins, skills nem Chrome: cada chamada carregava ~342 mil tokens só disso; assim fica ~3,5 mil (03/11)
LEVE = ["--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}', "--setting-sources", "project", "--disable-slash-commands", "--no-chrome"]
CLIENTES = []  # nomes dos seus clientes atuais: a pesquisa descarta quem já é cliente
TEXTO = {"type": "string"}
ESQUEMA_ANALISE = {
    "type": "object", "additionalProperties": False, "required": ["empresas"],
    "properties": {"empresas": {"type": "array", "items": {
        "type": "object", "additionalProperties": False,
        "required": ["nome", "bairro", "endereco", "telefone", "whatsapp", "google_maps", "site", "situacao_site", "site_nota", "site_problemas", "instagram", "instagram_ativo",
                     "nota", "avaliacoes", "rede_ou_franquia", "analise", "fontes"],
        "properties": {
            "nome": TEXTO, "bairro": TEXTO, "endereco": TEXTO, "telefone": TEXTO, "whatsapp": TEXTO, "google_maps": TEXTO, "site": TEXTO,
            "situacao_site": {"type": "string", "enum": ["sem site", "site fraco", "site bom"]},
            "site_nota": {"type": "integer", "minimum": 0, "maximum": 10}, "site_problemas": TEXTO,
            "instagram": TEXTO, "instagram_ativo": {"type": "string", "enum": ["sim", "não", "não deu para ver"]},
            "nota": TEXTO, "avaliacoes": TEXTO, "rede_ou_franquia": {"type": "boolean"}, "analise": TEXTO,
            "fontes": {"type": "array", "items": TEXTO},
        }}}},
}


# Pedido dele: "tem muito site que é ruim o layout que dá pra gente refazer". O site é julgado pelo DESENHO (print),
# no padrão de um web designer exigente, e não só pelo texto.
JULGAR_SITE = (
    "\n\nCOMO JULGAR O SITE: quando a empresa tiver \"print da página\", abra o arquivo com a ferramenta Read e olhe o desenho, "
    "como um web designer exigente que quer vender um site novo. Dê site_nota de 0 a 10. Nota 8 a 10 só para site atual, "
    "com visual próprio de agência, que você teria orgulho de mostrar e que seria difícil melhorar muito. Abaixo de 8 quando "
    "tiver qualquer um destes sinais: cara de modelo pronto (tema de Elementor, Wix, WordPress, construtor de site), grandes "
    "espaços vazios, foto com borda esfumaçada ou de banco de imagem, cabeçalho só com logo e sem menu, frase genérica "
    "(\"transformar sorrisos\", \"qualidade e excelência\"), botão pequeno ou escondido, sem prova (avaliações, antes e "
    "depois, casos), visual datado, texto pequeno ou sem contraste, página que não explica o serviço. Na dúvida, dê a nota "
    "menor. situacao_site: \"site bom\" só com nota 8 ou mais; \"site fraco\" abaixo; \"sem site\" com nota 0. "
    "Em site_problemas, escreva de 2 a 4 defeitos concretos que dá para mostrar ao dono, em linguagem simples, separados "
    "por \"; \" (ex.: \"metade da primeira tela é espaço vazio; o botão de agendar é pequeno\"). Se a velocidade no celular "
    "tiver nota abaixo de 50 ou o conteúdo principal demorar mais de 4 s, inclua isso como defeito, com o número medido. Sem site: deixe vazio.\n"
)


# receitas de abertura tiradas das referências dele (03/11: "o hero é o mais importante")
HERO_REGRAS = (
    "   - ABERTURA (HERO) É O MAIS IMPORTANTE: o dono bate o olho e já se interessa. Escolha UMA destas receitas das "
    "referências (a que ainda não apareceu nas prévias já montadas) e capriche: (A) Oralyn: texto à esquerda, foto "
    "grande em cartão à direita com 2 cartões sobrepostos (retrato do profissional com nome e destaque com ícone); "
    "(B) Dentora/Bienes/ADEMI: foto real cheia em cartão arredondado, menu em pílula dentro da foto, título embaixo em "
    "dois tons, chips de serviços e mini-cartões translúcidos com fotos e linha 01——02; (C) Meet Our Experts/"
    "GreenVision: título enorme centralizado com fotos reais soltas em cartões de tamanhos diferentes, pílulas com "
    "fatos reais e ícones em círculos ligados por linhas finas; (D) VivaChat: título à esquerda e duas colunas "
    "desencontradas de fotos altas que se mexem devagar; (E) Find Your Dream: foto em cartão com barra de agendamento "
    "flutuando na base (tratamento, dia, botão do WhatsApp). A abertura SEMPRE tem: 2 ou mais fotos reais, menu com "
    "logo, título de no máximo 3 linhas, subtítulo, botão principal em pílula com seta em círculo e um secundário, "
    "uma prova real (anos de clínica, registro, especialidade; nota do Google só marcada para confirmar), chips de "
    "serviço, uma animação de entrada e a primeira tela inteira preenchida, sem metade vazia. Nunca um bloco de cor "
    "só com texto. O conteúdo da abertura precisa aparecer mesmo sem a animação rodar.\n"
)


ESQUEMA_COPY = {
    "type": "object",
    "properties": {
        "titulos": {"type": "array", "minItems": 2, "maxItems": 3, "items": {"type": "array", "minItems": 2, "maxItems": 2, "items": TEXTO}},
        "subtitulo": TEXTO,
        "sobre": {"type": "array", "minItems": 2, "maxItems": 2, "items": TEXTO},
        "servicos": {"type": "array", "minItems": 3, "maxItems": 6, "items": {"type": "object", "properties": {
            "nome": TEXTO, "texto": TEXTO, "icone": {"type": "string", "enum": ["busca", "brilho", "dente", "alinha", "escudo", "coracao", "lista", "calendario", "conversa", "raio", "gota", "estrela", "check"]}},
            "required": ["nome", "texto", "icone"]}},
        "passos": {"type": "array", "minItems": 3, "maxItems": 3, "items": {"type": "object", "properties": {"titulo": TEXTO, "texto": TEXTO}, "required": ["titulo", "texto"]}},
        "faq": {"type": "array", "minItems": 4, "maxItems": 5, "items": {"type": "object", "properties": {"pergunta": TEXTO, "resposta": TEXTO}, "required": ["pergunta", "resposta"]}},
        "chamada": {"type": "array", "minItems": 2, "maxItems": 2, "items": TEXTO},
        "botao": TEXTO,
        "abre_whats": TEXTO,
    },
    "required": ["titulos", "subtitulo", "sobre", "servicos", "passos", "faq", "chamada", "botao", "abre_whats"],
}

PEDIDO_COPY = """Você escreve os textos do site de exemplo de uma empresa real. Use SÓ os fatos abaixo. Responda no formato pedido, sem ferramentas.

<fatos>
{fatos}
</fatos>

<texto-do-site-atual>
{site}
</texto-do-site-atual>

Regras:
- Português do Brasil simples, frases curtas, falando direto com o {cliente} ("você"). Tom calmo e seguro, sem exagero.
- A copy é desta empresa: use o nome, a especialidade real (pelas categorias do Google e pelo site), o bairro e a cidade. Nada genérico que serviria para qualquer {lugar}.
- Se o site atual existir, parta do que a empresa já diz (serviços, jeito de atender) e escreva melhor: mais claro, mais curto, focado no que o {cliente} ganha.
- NÃO invente: anos de experiência, números, prêmios, formação, equipamentos, convênios, preços, depoimentos, nomes de pessoas. Se não está nos fatos, não escreva.
- Saúde: sem promessa de resultado, sem "melhor", "garantido", "sem dor", antes/depois ou preço (regras do conselho profissional).
- Sem clichê de marketing: nada de "excelência", "qualidade e bom atendimento", "transforme", "sorriso dos sonhos", "venha conhecer".
- titulos: 2 ou 3 opções da abertura, cada uma em duas partes curtas [linha 1, linha 2], no máximo 7 palavras no total, afirmação seca.
- subtitulo: 1 ou 2 frases (até 30 palavras) com especialidade, bairro e cidade.
- sobre: [frase forte curta, continuação de 1 ou 2 frases].
- servicos: 3 a 6 serviços que a empresa realmente faz, cada um com texto de até 14 palavras.
- passos: como é o primeiro atendimento em 3 passos (o primeiro começa pelo WhatsApp).
- faq: 4 ou 5 dúvidas reais do {cliente} desse serviço; quando a resposta depende da empresa (convênio, preço), diga para confirmar pelo WhatsApp.
- chamada: [título curto do convite final, frase de apoio].
- botao: ação curta (até 3 palavras). abre_whats: primeira mensagem que o {cliente} manda no WhatsApp, em 1 frase."""


class ErroIA(Exception):
    pass


class IA:
    def __init__(self, dados):
        self.dados = Path(dados)
        self._plano = (False, 0)

    # ---------- 1. achar e analisar empresas pelo plano do Claude (Claude Code), sem gastar API ----------
    def plano_ligado(self):
        """Confere se o Claude Code deste computador está logado. Guarda a resposta por 1 minuto."""
        agora = time.time()
        if agora - self._plano[1] > 60:
            try:
                saida = subprocess.run([CLAUDE_CODE, "auth", "status"], capture_output=True, text=True, timeout=20,
                                       env=self._env_plano()).stdout
                self._plano = (bool(json.loads(saida).get("loggedIn")), agora)
            except (OSError, subprocess.SubprocessError, ValueError):
                self._plano = (False, agora)
        return self._plano[0]

    def _env_plano(self):
        # Sem a chave da API no ambiente, o Claude Code usa o login do plano, não os créditos
        # sem o CLAUDE.md do sistema (o pedido já leva o que precisa): ~16 mil tokens a menos por chamada
        return {**{k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}, "CLAUDE_CODE_DISABLE_CLAUDE_MDS": "1"}

    def entrar_no_plano(self):
        """Abre o Terminal com o login do Claude Code. Quem entra na conta é o dono do computador, no navegador."""
        self._plano = (False, 0)
        subprocess.run(["osascript", "-e", f'tell application "Terminal" to do script "{CLAUDE_CODE} auth login"',
                        "-e", 'tell application "Terminal" to activate'], timeout=20)

    def pesquisar_e_analisar(self, nicho, local, ja_na_lista, quantidade=15):
        """Acha as empresas e analisa cada uma pelos critérios da Conferência. Quem decide quem passa é o servidor."""
        if not self.plano_ligado():
            raise ErroIA("O Claude deste computador está deslogado. Clique em \"Entrar com meu plano\".")
        pasta = self.dados / "claude-code"
        pasta.mkdir(exist_ok=True)
        pedido = (
            "Você pesquisa e analisa empresas reais para um web designer que vende sites para donos de empresa. "
            "Use a busca na web e leia as páginas. Só registre o que encontrou em uma fonte; nunca invente telefone, nota, "
            "avaliação, endereço ou perfil. Campo sem informação fica vazio.\n\n"
            f"1. Encontre até {quantidade} empresas ativas de {nicho} em {local}, de preferência pequenas e médias.\n"
            f"   Pule estas, que já estão na lista dele: {', '.join(ja_na_lista[:200]) or 'nenhuma'}.\n"
            f"   Pule estas, que já são clientes dele: {', '.join(CLIENTES)}.\n"
            "2. Para cada uma, confira:\n"
            "   - nota e número de avaliações no Google (procure o nome + bairro; o Perfil da Empresa costuma aparecer nos "
            "resultados). Escreva só números, como 4,8 e 37. Não use nota de Doctoralia, Facebook ou outro site.\n"
            "   - site próprio: Instagram, WhatsApp, Linktree, Doctoralia ou agregador não contam. Se existir, abra e julgue: "
            "\"site bom\" se é atual, claro e bem feito; \"site fraco\" se é antigo, genérico, lento, quebrado, de modelo pronto "
            "ou não explica o serviço.\n"
            "   - Instagram da empresa (@): pesquise \"<nome> instagram\" e confira se o perfil é dela. Diga se parece ativo, com post nos últimos 3 meses; se não der para abrir o perfil, responda \"não deu para ver\".\n"
            "   - contatos: endereço completo, telefone, WhatsApp (o número que a própria empresa divulga como WhatsApp, com DDD) e o link do perfil dela no Google Maps (o link que abre o lugar, de google.com/maps ou maps.app.goo.gl; se não achar o link, deixe vazio).\n"
            "   - se é rede, franquia ou grupo grande com várias unidades.\n"
            "3. Em \"analise\", escreva em 1 ou 2 frases simples, em português, a chance de ela fechar um site: o que falta "
            "na presença dela na internet e por que um site novo ajudaria. Sem exagero."
        )
        saida = self._rodar_plano(pedido, ESQUEMA_ANALISE, pasta).get("empresas", [])
        return [{k: (v if k in ("fontes", "rede_ou_franquia") else str(v or "")) for k, v in e.items()}
                for e in saida if isinstance(e, dict)]

    def analisar_empresas(self, empresas, rapido=False):
        """Recebe empresas já achadas no Google Maps (nota e avaliações vêm de lá) e confere site, Instagram e WhatsApp."""
        if not self.plano_ligado():
            raise ErroIA("O Claude deste computador está deslogado. Clique em \"Entrar com meu plano\".")
        pasta = self.dados / "claude-code"
        pasta.mkdir(exist_ok=True)
        lista = "\n".join(f"- {e['nome']} | {e.get('endereco', '')} | telefone {e.get('telefone') or '?'} | site no Google: "
                          f"{e.get('site') or 'nenhum'}" + (f" (TESTEI E ESTÁ FORA DO AR: {e['site_defeito']})" if e.get("site_defeito") else "")
                          + (f" | site atual feito em {e['site_feito_em'][5:7]}/{e['site_feito_em'][:4]}" if e.get("site_feito_em") else "")
                          + (f" | print da página: {e['print_site']}" if e.get("print_site") else "")
                          + (f" | velocidade no celular (Lighthouse do Google): nota {e['site_velocidade']['nota']}/100, conteúdo principal em "
                             f"{e['site_velocidade']['carrega']}" if e.get("site_velocidade") else "")
                          for e in empresas)
        pedido = (
            "Você analisa empresas reais para um web designer que vende sites para donos de empresa. "
            "Use a busca na web e leia as páginas. Só registre o que encontrou em uma fonte; nunca invente telefone, "
            "endereço ou perfil." + JULGAR_SITE + "Campo sem informação fica vazio. Devolva uma entrada para CADA empresa abaixo, com o "
            "nome escrito exatamente igual. Deixe nota, avaliações e google_maps vazios: eles já vieram do Google Maps.\n\n"
            f"Empresas:\n{lista}\n\n"
            "Para cada uma, confira:\n"
            "- site próprio: Instagram, WhatsApp, Linktree, Doctoralia ou agregador não contam. Se existir, julgue pelas regras "
            "de nota acima. Se o site do Google não abrir (fora do ar, domínio sem dono), é \"site fraco\" e diga isso na análise. Se o site no Google for Instagram ou WhatsApp, é \"sem site\".\n"
            "- Instagram da empresa (@): pesquise \"<nome> instagram\" e confira se o perfil é dela. Diga se parece ativo, "
            "com post nos últimos 3 meses; se não der para abrir o perfil, responda \"não deu para ver\". Quando o site estiver "
            "fora do ar, capriche nessa busca: o Instagram e o WhatsApp são o único caminho para falar com ela.\n"
            "- WhatsApp: o número que a própria empresa divulga como WhatsApp, com DDD.\n"
            "- se é rede, franquia ou grupo grande com várias unidades.\n"
            "- Em \"analise\", escreva em 1 ou 2 frases simples, em português, a chance de ela fechar um site: o que falta "
            "na presença dela na internet e por que um site novo ajudaria. Se o site atual foi feito nos últimos 12 meses e "
            "é fraco, a oferta é otimizar o site (layout, velocidade, conteúdo), não um site do zero. Sem exagero."
        )
        return [{k: (v if k in ("fontes", "rede_ou_franquia", "site_nota") else str(v or "")) for k, v in e.items()}
                for e in self._rodar_plano(pedido, ESQUEMA_ANALISE, pasta, rapido).get("empresas", []) if isinstance(e, dict)]

    def procurar_contato(self, empresa):
        """Segunda busca, mais caprichada, só para achar o perfil e o contato certo de uma empresa (ex.: site fora do ar)."""
        if not self.plano_ligado():
            raise ErroIA("O Claude deste computador está deslogado. Clique em \"Entrar com meu plano\".")
        pasta = self.dados / "claude-code"
        pasta.mkdir(exist_ok=True)
        defeito = f"O site dela ({empresa.get('site')}) está fora do ar: {empresa['site_defeito']}. " if empresa.get("site_defeito") else ""
        pedido = (
            "Você acha o perfil e o contato certo de uma empresa real, para um web designer oferecer um site novo. "
            "Use a busca na web e leia as páginas. Só registre o que confirmou numa fonte; nunca invente @, número ou link. "
            "Campo sem informação fica vazio.\n\n"
            f"Empresa: {empresa.get('nome')} | {empresa.get('endereco', '')} | telefone no Google: {empresa.get('telefone') or '?'}\n{defeito}\n"
            "Procure com cuidado, tentando vários caminhos:\n"
            "- Instagram: pesquise \"<nome> instagram\", \"<nome> <bairro ou cidade> instagram\", o nome do dono ou do profissional "
            "responsável + instagram, e links no Facebook, Doctoralia, Linktree ou no próprio site antigo (versão em cache ou "
            "web.archive.org). Confira que o perfil é desta empresa (mesmo endereço, telefone ou nome) e diga se parece ativo "
            "(post nos últimos 3 meses) ou \"não deu para ver\".\n"
            "- WhatsApp: o número que a própria empresa divulga como WhatsApp, com DDD.\n"
            "- telefone: outro telefone atual, se o do Google parecer antigo.\n"
            "- Em \"analise\", 1 ou 2 frases simples: o que achou e como abordar, citando o defeito do site se houver."
        )
        esquema = {"type": "object", "additionalProperties": False,
                   "required": ["instagram", "instagram_ativo", "whatsapp", "telefone", "analise", "fontes"],
                   "properties": {"instagram": TEXTO, "instagram_ativo": {"type": "string", "enum": ["sim", "não", "não deu para ver"]},
                                  "whatsapp": TEXTO, "telefone": TEXTO, "analise": TEXTO, "fontes": {"type": "array", "items": TEXTO}}}
        r = self._rodar_plano(pedido, esquema, pasta, rapido=True, esforco="medium")
        return {k: (v if k == "fontes" else str(v or "")) for k, v in r.items()}

    def montar_layout(self, empresa, pasta_previa):
        """Monta a prévia do site (index.html) na pasta da empresa, a partir da análise e da copy dela.
        O Claude escreve só dentro dessa pasta; baixa as fotos reais com curl para img/."""
        if not self.plano_ligado():
            raise ErroIA("O Claude deste computador está deslogado.")
        pasta_previa = Path(pasta_previa)
        (pasta_previa / "img").mkdir(parents=True, exist_ok=True)
        usados = [f"- {d.name}: {(d / 'layout.md').read_text(encoding='utf-8')[:1200]}" for d in sorted(pasta_previa.parent.iterdir())
                  if d.is_dir() and d != pasta_previa and (d / "layout.md").exists()]
        site = (empresa.get("contatos") or {}).get("site") or empresa.get("site") or ""
        pedido = (
            "Você é o web designer dono deste painel, montando a PRÉVIA do site de uma empresa real para prospectar. "
            "É um site de exemplo para despertar interesse; se ela aprovar, o site definitivo vem depois.\n\n"
            "LEIA ANTES, com a ferramenta Read (caminhos absolutos):\n"
            f"- {METODO / 'METODO-SITES.md'} (o método: lógica da página, cópia, tipografia, grid, cor, animação, regras do ramo)\n"
            f"- {METODO / 'PROCESSO-PREVIA.md'} e {METODO / 'aprendizados-previas.md'} (o que ele já aprovou e reprovou)\n"
            f"- {METODO / 'layouts-usados.md'} (não repetir)\n"
            f"- {METODO / 'referencias' / 'REFERENCIAS.md'} e, para economizar, abra NO MÁXIMO 3 imagens dessa pasta: as da receita de abertura que escolher e uma para o miolo (o texto do REFERENCIAS.md já descreve todas)\n"
            f"- analise.md e copy.md desta pasta (o que a empresa é, as fotos, a paleta e o texto aprovado do site)\n\n"
            + (f"PRÉVIAS JÁ MONTADAS (não repita a composição delas):\n" + "\n".join(usados) + "\n\n" if usados else "")
            + f"EMPRESA: {json.dumps({k: empresa.get(k) for k in ('nome', 'bairro_nome', 'endereco', 'telefone', 'contatos', 'site_problemas', 'site_defeito', 'oferta')}, ensure_ascii=False)}\n"
            f"Site atual: {site or 'não tem'}\n\n"
            "FAÇA:\n"
            "1. FOTOS REAIS: ache fotos da própria empresa (site atual, Perfil da Empresa no Google, Instagram público, "
            "Doctoralia) e baixe as boas com `curl -L -o img/<nome>.jpg <url>`. Fora: paciente identificável, criança, "
            "procedimento, antes e depois, foto de banco de imagem, foto com texto por cima. Sem foto boa, a seção muda de "
            "desenho; nunca invente imagem nem gere rosto.\n"
            "2. PALETA: medida no logo e nos posts dela, nunca na cor de um móvel da foto. Nunca preto e lima.\n"
            "3. LAYOUT: escreva index.html completo e autossuficiente (CSS e JS dentro do arquivo, fontes do Google Fonts), "
            "com a copy de copy.md sem mudar o texto, seguindo o método e combinando as referências de um jeito que ainda "
            "não apareceu. Nível da Vivaz ou melhor, responsivo para celular, tablet e computador.\n"
            "   O administrador reprovou prévias \"sem vida: só a cor de fundo e a letra\". Ele quer aprovação logo de cara, então é "
            "OBRIGATÓRIO (confira cada item antes de terminar):\n"
            + HERO_REGRAS + 
            "   - IMAGEM: pelo menos 6 fotos reais espalhadas pela página (abertura, equipe, ambiente, serviços); use cada foto "
            "boa que achar, com recortes diferentes (cartão grande, miniatura dentro da frase, mosaico, foto que vaza a seção). "
            "Com poucas fotos, repita a mesma em recortes e tamanhos diferentes antes de deixar uma seção sem imagem.\n"
            "   - NENHUMA SEÇÃO SÓ COM FUNDO E TEXTO: toda seção tem um elemento visual (foto, ícone, cartão, número grande, "
            "selo, linha do tempo, mapa, grade de miniaturas).\n"
            "   - ÍCONES: um ícone em traço fino em cada serviço, passo, diferencial e contato (SVG inline no estilo Lucide, "
            "mesmo traço e tamanho em todos).\n"
            "   - INTERAÇÕES E ANIMAÇÕES (no mínimo 6, cada uma servindo para algo): elementos que entram ao rolar "
            "(IntersectionObserver), menu fixo que muda ao rolar com barra de leitura, abas ou lista que troca texto e foto, "
            "carrossel de fotos com setas, cartões que reagem ao mouse, números que contam, dúvidas que abrem com animação, "
            "faixa contínua com os serviços, botão do WhatsApp flutuante. Respeite prefers-reduced-motion.\n"
            "   - DETALHES: rótulos pequenos acima dos títulos, chips com serviços, selos (ex.: bairro, especialidade), "
            "divisórias finas, cartões com sombra suave, contornos e cantos de um só sistema, botões com seta em círculo.\n"
            "   - ALINHAMENTO: uma margem lateral só; títulos com text-wrap:balance e no máximo 3 linhas; parágrafos com "
            "largura de 60 a 70 caracteres; nada de palavra sozinha na última linha; espaçamento vertical regular entre seções.\n"
            "   Para ganhar tempo: leia só as imagens de referência e a Vivaz que precisar, escreva o arquivo de uma vez e "
            "corrija com Edit, sem reescrever tudo. "
            "Itens [CONFIRMAR] ficam marcados com <mark class=\"confirmar\">. Obrigatório: faixa no topo dizendo que é um "
            "site de exemplo feito por [nome do perfil] e que a versão completa vem depois da aprovação; rodapé \"Proposta de site "
            "por [nome do perfil]\"; <meta name=\"robots\" content=\"noindex, nofollow\">. Nada de depoimento, nota, número ou "
            "preço inventado; regras do conselho da profissão.\n"
            "4. Escreva layout.md com 5 a 8 linhas: paleta e fontes, como é a abertura, a ordem das seções, as interações e "
            "as fotos usadas (com a origem de cada uma).\n"
            "5. Releia o index.html e corrija: texto cortado, imagem quebrada, tudo alinhado na mesma margem.\n"
            "Só escreva arquivos dentro desta pasta. Responda no fim com um resumo curto do que fez."
        )
        try:
            r = subprocess.run(
                [CLAUDE_CODE, "-p", pedido, *LEVE, "--tools", "WebSearch,WebFetch,Read,Write,Edit,Bash",
                 "--allowedTools", "WebSearch,WebFetch,Read,Write,Edit,Bash(curl:*),Bash(ls:*),Bash(file:*),Bash(sips:*)",
                 "--no-session-persistence", "--output-format", "json", "--model", MODELO_RAPIDO, "--effort", "medium"],
                capture_output=True, text=True, timeout=3600, cwd=pasta_previa, env=self._env_plano())
        except subprocess.TimeoutExpired:
            raise ErroIA("O layout passou de 1 hora e foi interrompido.")
        try:
            saida = json.loads(r.stdout)
        except ValueError:
            raise ErroIA("O Claude não devolveu a resposta do layout.")
        if saida.get("is_error"):
            texto = str(saida.get("result", ""))
            if "limit" in texto.lower():
                raise ErroIA("O limite do seu plano do Claude acabou por agora. A fila continua depois.")
            raise ErroIA(f"O Claude deu erro no layout: {texto[:200]}")
        if not (pasta_previa / "index.html").exists():
            raise ErroIA("O Claude terminou sem escrever o index.html.")
        return str(saida.get("result", ""))[:1500]

    def refazer_abertura(self, pasta_previa):
        """Refaz só a abertura (hero) de uma prévia pronta com as receitas novas, sem mexer no resto da página."""
        if not self.plano_ligado():
            raise ErroIA("O Claude deste computador está deslogado.")
        pasta_previa = Path(pasta_previa)
        usados = [f"- {d.name}: {(d / 'layout.md').read_text(encoding='utf-8')[:600]}" for d in sorted(pasta_previa.parent.iterdir())
                  if d.is_dir() and d != pasta_previa and (d / "layout.md").exists()]
        pedido = (
            "Você é o web designer dono deste painel. Refaça SÓ A ABERTURA (hero, a primeira tela) do index.html desta pasta; o resto "
            "da página fica igual (mesma paleta, fontes e copy).\n"
            f"Olhe antes as imagens de referência em {METODO / 'referencias'} (as 13 .webp/.png) e leia "
            f"{METODO / 'referencias' / 'REFERENCIAS.md'}, layout.md e copy.md desta pasta. Fotos reais da empresa estão em img/.\n"
            + ("Aberturas de outras prévias (não repita a receita delas):\n" + "\n".join(usados) + "\n" if usados else "")
            + HERO_REGRAS
            + "Use todas as fotos boas de img/ que couberem (2 ou mais na abertura). Sem foto suficiente, baixe outras reais da "
            "empresa com curl (site atual, Google, Doctoralia). Mantenha a faixa de site de exemplo, o menu com links que "
            "funcionam e o noindex. Confira no celular. Atualize em layout.md a linha da abertura. Só escreva nesta pasta. "
            "No fim, responda em uma ou duas frases simples qual receita usou e o que mudou."
        )
        try:
            r = subprocess.run(
                [CLAUDE_CODE, "-p", pedido, *LEVE, "--tools", "WebSearch,WebFetch,Read,Grep,Write,Edit,Bash",
                 "--allowedTools", "WebSearch,WebFetch,Read,Grep,Write,Edit,Bash(curl:*),Bash(ls:*),Bash(sips:*)",
                 "--no-session-persistence", "--output-format", "json", "--effort", "medium"],
                capture_output=True, text=True, timeout=2400, cwd=pasta_previa, env=self._env_plano())
        except subprocess.TimeoutExpired:
            raise ErroIA("Refazer a abertura passou de 40 minutos e foi interrompido.")
        try:
            saida = json.loads(r.stdout)
        except ValueError:
            raise ErroIA("O Claude não devolveu a resposta.")
        if saida.get("is_error"):
            texto = str(saida.get("result", ""))
            raise ErroIA("O limite do seu plano do Claude acabou por agora." if "limit" in texto.lower() else f"O Claude deu erro: {texto[:200]}")
        return str(saida.get("result", ""))[:800]

    def ajustar_previa(self, pasta_previa, pedido_dele, imagens=()):
        """Aplica no index.html o ajuste que o administrador pediu na tela de Prévias, sem mexer no resto."""
        if not self.plano_ligado():
            raise ErroIA("O Claude deste computador está deslogado.")
        pasta_previa = Path(pasta_previa)
        pedido = (
            "Você é o administrador, web designer, fazendo um AJUSTE RÁPIDO na prévia de site desta pasta (index.html). "
            "Ele está esperando na tela: seja rápido. Não leia outros documentos; use Grep para achar o trecho certo no "
            "index.html, mude com Edit e pronto. Só leia copy.md se precisar de um texto, e só busque na web se ele pedir "
            "uma foto ou dado que não está na pasta.\n\n"
            f"O PEDIDO DELE, palavra por palavra: \"{pedido_dele}\"\n\n"
            + (f"Ele anexou {len(imagens)} print(s) mostrando ONDE e COMO mudar. Abra cada um com a ferramenta Read antes de "
               f"editar e ache na página o trecho que aparece no print: {', '.join(imagens)}\n\n" if imagens else "")
            + "Regras: altere só o que ele pediu e deixe o resto igual. Mexeu em texto aprovado só se ele pediu. Foto nova só real "
            "da empresa (baixe com curl para img/). Nada de dado inventado. Mantenha a faixa de site de exemplo, o rodapé da "
            "proposta e o noindex. Confira só o trecho mudado (inclusive no celular). "
            "Só escreva dentro desta pasta. No fim, responda em uma ou duas frases simples o que mudou."
        )
        try:
            # modelo rápido e esforço baixo: ajuste pontual não precisa de raciocínio longo (pedido dele: "tem que ser rápido")
            r = subprocess.run(
                [CLAUDE_CODE, "-p", pedido, *LEVE, "--tools", "WebSearch,WebFetch,Read,Grep,Write,Edit,Bash",
                 "--allowedTools", "WebSearch,WebFetch,Read,Grep,Write,Edit,Bash(curl:*),Bash(ls:*),Bash(sips:*)",
                 "--no-session-persistence", "--output-format", "json", "--model", MODELO_RAPIDO, "--effort", "low"],
                capture_output=True, text=True, timeout=1800, cwd=pasta_previa, env=self._env_plano())
        except subprocess.TimeoutExpired:
            raise ErroIA("O ajuste passou de 30 minutos e foi interrompido.")
        try:
            saida = json.loads(r.stdout)
        except ValueError:
            raise ErroIA("O Claude não devolveu a resposta do ajuste.")
        if saida.get("is_error"):
            texto = str(saida.get("result", ""))
            raise ErroIA("O limite do seu plano do Claude acabou por agora." if "limit" in texto.lower() else f"O Claude deu erro: {texto[:200]}")
        return str(saida.get("result", ""))[:800]

    def _rodar_plano(self, pedido, esquema, pasta, rapido=False, esforco="low"):
        # rápido: modelo mais leve, para a checagem de cada empresa (site, Instagram, WhatsApp)
        extra = ["--model", MODELO_RAPIDO, "--effort", esforco] if rapido else []
        try:
            r = subprocess.run(
                [CLAUDE_CODE, "-p", pedido, *LEVE, "--tools", "WebSearch,WebFetch,Read", "--allowedTools", "WebSearch,WebFetch,Read",
                 "--no-session-persistence", "--output-format", "json", "--json-schema", json.dumps(esquema), *extra],
                capture_output=True, text=True, timeout=1800, cwd=pasta, env=self._env_plano())
        except subprocess.TimeoutExpired:
            raise ErroIA("A pesquisa passou de 30 minutos e foi interrompida. Tente um bairro menor.")
        except OSError:
            raise ErroIA("Não achei o Claude Code neste computador.")
        try:
            saida = json.loads(r.stdout)
        except ValueError:
            raise ErroIA("O Claude não devolveu a resposta. Tente de novo.")
        if saida.get("is_error"):
            texto = str(saida.get("result", ""))
            if "authenticate" in texto.lower() or "login" in texto.lower():
                self._plano = (False, 0)
                raise ErroIA("O login do Claude venceu. Clique em \"Entrar com meu plano\".")
            if "limit" in texto.lower():
                raise ErroIA("O limite do seu plano do Claude acabou por agora. Tente mais tarde.")
            raise ErroIA(f"O Claude deu erro: {texto[:200]}")
        resultado = saida.get("structured_output")
        if not isinstance(resultado, dict):
            try:
                resultado = json.loads(saida.get("result", ""))
            except (ValueError, TypeError):
                raise ErroIA("A resposta veio num formato que não entendi. Tente de novo.")
        return resultado


    # ---------- copy própria da empresa para o modelo pronto: uma chamada curta, sem ferramentas ----------
    def copy_da_empresa(self, fatos, texto_site, pasta, cliente="cliente", lugar="empresa"):
        pedido = PEDIDO_COPY.format(fatos=json.dumps(fatos, ensure_ascii=False, indent=1), site=texto_site or "(a empresa não tem site)",
                                    cliente=cliente, lugar=lugar)
        try:
            r = subprocess.run(
                [CLAUDE_CODE, "-p", pedido, *LEVE, "--tools", "", "--no-session-persistence", "--output-format", "json",
                 "--json-schema", json.dumps(ESQUEMA_COPY), "--model", MODELO_RAPIDO, "--effort", "low"],
                capture_output=True, text=True, timeout=300, cwd=pasta, env=self._env_plano())
            saida = json.loads(r.stdout)
        except (subprocess.TimeoutExpired, OSError, ValueError):
            raise ErroIA("A copy da empresa não saiu agora. Ficou o texto padrão do nicho.")
        if saida.get("is_error"):
            texto = str(saida.get("result", ""))
            raise ErroIA("O limite do seu plano do Claude acabou por agora." if "limit" in texto.lower() else f"A copy deu erro: {texto[:150]}")
        resultado = saida.get("structured_output")
        if not isinstance(resultado, dict):
            raise ErroIA("A copy veio num formato que não entendi.")
        uso = saida.get("usage") or {}
        resultado["_gasto"] = {"entrada": uso.get("input_tokens", 0) + uso.get("cache_read_input_tokens", 0) + uso.get("cache_creation_input_tokens", 0),
                               "saida": uso.get("output_tokens", 0), "custo_usd": saida.get("total_cost_usd"), "segundos": round((saida.get("duration_ms") or 0) / 1000)}
        return resultado

    # ---------- 2. análise completa de uma empresa: prospecção, copy do site e posts de exemplo ----------
    def _contexto_metodo(self):
        partes = []
        for nome in ("METODO-SITES.md", "PROCESSO-PREVIA.md", "aprendizados-previas.md"):
            caminho = METODO / nome
            if caminho.exists():
                partes.append(f"<{nome}>\n{caminho.read_text(encoding='utf-8')}\n</{nome}>")
        for nome in ("analise", "copy"):
            exemplo = self.dados / "previas" / "vivaz" / f"{nome}.md"
            if exemplo.exists():
                partes.append(f"<exemplo-de-{nome}-aprovada>\n{exemplo.read_text(encoding='utf-8')}\n</exemplo-de-{nome}-aprovada>")
        return "\n\n".join(partes)

    def preparar_empresa(self, empresa, estado, com_posts=True, rapido=False):
        if not self.plano_ligado():
            raise ErroIA("O Claude deste computador está deslogado. Clique em \"Entrar com meu plano\" na Pesquisa com IA.")
        pasta = self.dados / "claude-code"
        pasta.mkdir(exist_ok=True)
        contatos = empresa.get("contatos") or {}
        site = estado.get("site_url") or contatos.get("site") or ""
        hoje = time.strftime("%d/%m/%Y")
        pedido = (
            "Você prepara o material de prospecção do administrador, web designer que vende SITES e POSTS PARA INSTAGRAM "
            "(social media) para donos de empresa. Siga à risca o método, o processo, os aprendizados e os exemplos aprovados "
            "abaixo. Nada inventado: cada informação tem fonte; o que faltar vira [CONFIRMAR]. Siga as regras do conselho da "
            "profissão (para dentistas, as do CFO no método). Nunca use foto de criança, de procedimento ou antes e depois. "
            "Escreva em português do Brasil, frases curtas, voz de quem fala com o dono do negócio.\n\n"
            f"{self._contexto_metodo()}\n\n"
            f"Empresa: {json.dumps(empresa, ensure_ascii=False)}\n"
            f"O que já foi conferido: {json.dumps(estado, ensure_ascii=False)}\n"
            f"Site atual: {site or 'não tem'}\n"
            f"Hoje é {hoje}.\n\n"
            "PESQUISE TUDO O QUE FOR PÚBLICO, com a busca na web e lendo as páginas:\n"
            "- Instagram: abra o perfil e procure os posts nos resultados de busca. Bio, seguidores, frequência, últimos posts, "
            "destaques, tom, o que tem mais engajamento, cores e logo. Se o Instagram bloquear a leitura, diga o que não deu "
            "para ver.\n"
            "- Site atual (se tiver): leia as páginas e liste o que melhorar no layout e na copy, ponto por ponto.\n"
            "- Google: Perfil da Empresa, endereço, horário, serviços, fotos citadas, notícias e menções.\n"
            "- CNPJ: ache o número e confira em https://brasilapi.com.br/api/cnpj/v1/<cnpj sem pontos> (razão social, "
            "abertura, situação, sócios).\n"
            "- Profissionais: nome, registro no conselho (CRO, OAB, CRP...), especialidades registradas, Doctoralia, LinkedIn.\n"
            "- Concorrentes do mesmo bairro que já têm site bom: 2 ou 3, com o link, para mostrar a comparação.\n\n"
            "ENTREGUE TRÊS DOCUMENTOS em Markdown:\n"
            "1. analise_md, no formato da análise aprovada: critérios com fonte; O ACHADO QUE MUDA A ABORDAGEM (o fato real "
            "que dá motivo para ela querer um site agora); o que a empresa é; dados com fonte e situação; presença na internet "
            "(site, Google, Instagram: o que tem e o que falta); concorrentes; visual e paleta medida nos posts e no logo; fotos "
            "que dá para usar e as que não; o que não entra; e um bloco 'Como abordar': o post real recente para reagir na "
            "primeira mensagem (link e data), qual serviço oferecer primeiro (site, posts ou os dois) e por quê.\n"
            "2. copy_md, no formato da copy aprovada: a copy do site de exemplo, seção por seção.\n"
            "3. posts_md: diagnóstico curto do Instagram dela (o que funciona, o que falta) e 3 POSTS DE EXEMPLO prontos para "
            "o web designer oferecer o serviço de social media, cada um com: formato (carrossel ou post único), objetivo, o texto "
            "de cada slide, a legenda curta e a direção visual (fotos reais do perfil, paleta da marca). Os posts falam com o "
            "cliente DELA, no tom dela, usam só fatos achados e respeitam as regras do conselho da profissão."
        )
        if not com_posts:
            # fila automática: posts estão pausados (pedido dele), então o terceiro documento fica vazio
            pedido += "\n\nNESTA VEZ NÃO FAÇA OS POSTS: devolva posts_md vazio. Capriche na análise e na copy do site."
        esquema = {
            "type": "object", "additionalProperties": False, "required": ["analise_md", "copy_md", "posts_md"],
            "properties": {"analise_md": TEXTO, "copy_md": TEXTO, "posts_md": TEXTO},
        }
        # na fila de prévias a análise roda no modelo rápido com esforço médio (pedido dele: "a gente está demorando muito")
        return self._rodar_plano(pedido, esquema, pasta, rapido, "medium")
