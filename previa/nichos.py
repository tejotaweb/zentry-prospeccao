"""Texto-base de cada nicho para os modelos de prévia.

Só texto que vale para qualquer empresa do ramo (explica o serviço, como é o atendimento, dúvidas comuns).
Nada sobre a empresa em si: o que é dela (nome, profissional, registro, serviços, horário) vem dos dados
ou fica [CONFIRMAR]. Sem preço, sem promessa de resultado, sem "grátis" (regras dos conselhos).
"""
import re
import unicodedata

NICHOS = {
    "dentista": {
        "nome": "Odontologia", "lugar": "consultório", "cliente": "paciente", "conselho": "CRO-GO",
        "profissao": "Cirurgião-dentista", "cor": "#1F6F78",
        "botao": "Agendar avaliação", "botao2": "Ver tratamentos", "abre_whats": "Olá! Vi o site e quero agendar uma avaliação.",
        "titulos": [
            ("Dentista que explica", "antes de tratar."),
            ("Seu sorriso cuidado", "com calma e clareza."),
            ("Odontologia sem pressa,", "do exame ao cuidado."),
            ("Cuidar do sorriso começa", "por entender você."),
            ("Você entende o tratamento", "antes de decidir."),
        ],
        "subtitulo": "Consultório no {bairro}, em Goiânia. Você conta o que sente, o dentista examina e explica cada opção antes de qualquer decisão.",
        "sobre": ("Aqui, a consulta começa pela conversa.", " Você entende o que está acontecendo com o seu sorriso, vê as opções e decide junto com quem vai cuidar de você, sem pressa e sem surpresa."),
        "servicos": [
            ("Consulta e avaliação", "Exame completo da boca e conversa sobre o que você sente e espera.", "busca"),
            ("Limpeza e prevenção", "Remoção de placa e tártaro e orientação para cuidar em casa.", "brilho"),
            ("Restaurações", "Tratamento de cáries e reparo de dentes lascados ou desgastados.", "dente"),
            ("Ortodontia", "Aparelhos para alinhar os dentes e corrigir a mordida.", "alinha"),
            ("Clareamento", "Clareamento acompanhado pelo dentista, com avaliação antes.", "sol"),
            ("Implantes e próteses", "Reposição de dentes perdidos, planejada depois do exame.", "escudo"),
        ],
        "subtipos": [
            ("invisalign", ("Alinhadores invisíveis", "Alinhadores transparentes para alinhar os dentes, planejados depois da avaliação.", "alinha")),
            ("alinhador", ("Alinhadores invisíveis", "Alinhadores transparentes para alinhar os dentes, planejados depois da avaliação.", "alinha")),
            ("clareamento", ("Clareamento", "Clareamento dental indicado depois da avaliação do seu caso.", "brilho")),
            ("ortodont", ("Ortodontia", "Aparelhos para alinhar os dentes e corrigir a mordida.", "alinha")),
            ("endodont", ("Tratamento de canal", "Tratamento da polpa do dente para aliviar a dor e manter o dente.", "dente")),
            ("periodont", ("Periodontia", "Cuidado da gengiva e dos tecidos que sustentam os dentes.", "escudo")),
            ("implant", ("Implantes", "Reposição de dentes perdidos, planejada depois do exame.", "escudo")),
            ("pediatr", ("Odontopediatria", "Atendimento para crianças, com paciência e linguagem delas.", "coracao")),
            ("odontopediat", ("Odontopediatria", "Atendimento para crianças, com paciência e linguagem delas.", "coracao")),
            ("cosmét", ("Estética do sorriso", "Clareamento, facetas e ajustes de forma e cor dos dentes.", "brilho")),
            ("estét", ("Estética do sorriso", "Clareamento, facetas e ajustes de forma e cor dos dentes.", "brilho")),
            ("prótes", ("Próteses", "Coroas, pontes e próteses para devolver a mastigação.", "dente")),
            ("cirurgi", ("Cirurgias", "Extrações e pequenas cirurgias, com avaliação antes.", "bisturi")),
            ("emergên", ("Urgência", "Atendimento para dor, inchaço ou dente quebrado.", "relogio")),
            ("clínica odontológica", ("Clínica geral", "Consulta, limpeza, restaurações e prevenção.", "busca")),
            ("dentista", ("Clínica geral", "Consulta, limpeza, restaurações e prevenção.", "busca")),
        ],
        "situacoes": [
            ("Dor ao mastigar", "Incômodo ao mastigar tem várias causas. A consulta ajuda a entender a sua.", "raio"),
            ("Sensibilidade", "Sentir o frio, o quente ou o doce é um motivo comum para procurar o dentista.", "gota"),
            ("Gengiva sangrando", "Sangramento ao escovar merece atenção, mesmo quando não dói.", "escudo"),
            ("Faz tempo que não vou", "Muita gente adia a consulta. Dá para retomar o cuidado a partir de hoje.", "calendario"),
        ],
        "passos": [
            ("Você chama", "Pelo WhatsApp, conta o que sente e escolhe o melhor horário.", "conversa"),
            ("Avaliação", "O dentista examina com calma e mostra o que encontrou.", "busca"),
            ("Plano claro", "Você entende cada opção e o tempo de cada etapa antes de decidir.", "lista"),
        ],
        "faq": [
            ("Preciso estar com dor para marcar?", "Não. A consulta de rotina ajuda a achar problemas no começo, quando o cuidado é mais simples."),
            ("Como funciona a primeira consulta?", "Você conta o que sente, o dentista examina e explica o que encontrou e quais são as opções."),
            ("Atendem convênio?", "Confirme pelo WhatsApp quais convênios e formas de atendimento o consultório aceita."),
            ("Quanto tempo dura a avaliação?", "Depende do caso. Ao marcar, a equipe informa o tempo reservado para você."),
        ],
        "chamada": ("Marque sua avaliação", "Chame no WhatsApp, conte o que você sente e escolha o melhor horário."),
        "regra": "CFO 118/2012 e 196/2019: nome e CRO do responsável, sem preço, sem 'grátis', sem promessa, sem antes e depois.",
        "faixa": ["Prevenção", "Avaliação", "Restaurações", "Ortodontia", "Clareamento", "Implantes"],
        "etapas": ["Avaliação", "Planejamento", "Tratamento", "Acompanhamento"],
    },
    "nutricionista": {
        "nome": "Nutrição", "lugar": "consultório", "cliente": "paciente", "conselho": "CRN-1",
        "profissao": "Nutricionista", "cor": "#5B7F4E",
        "botao": "Agendar consulta", "botao2": "Como funciona", "abre_whats": "Olá! Vi o site e quero agendar uma consulta.",
        "titulos": [
            ("Comer bem sem viver", "de dieta."),
            ("Um plano alimentar", "que cabe na sua rotina."),
            ("Nutrição que começa", "pela sua história."),
            ("Menos regra,", "mais constância."),
        ],
        "subtitulo": "Atendimento de nutrição no {bairro}, em Goiânia. Plano montado a partir da sua rotina, dos seus exames e do que você gosta de comer.",
        "sobre": ("Cada plano começa pela sua rotina.", " A consulta olha para o que você come hoje, seus horários, seus exames e o seu objetivo, e monta um caminho que dá para seguir na vida real."),
        "servicos": [
            ("Consulta nutricional", "Conversa completa sobre rotina, histórico, exames e objetivo.", "conversa"),
            ("Plano alimentar", "Cardápio feito para a sua rotina, com opções e substituições.", "lista"),
            ("Avaliação corporal", "Medidas acompanhadas ao longo do tempo, para ajustar o plano.", "regua"),
            ("Retornos", "Acompanhamento para ajustar o plano conforme a sua evolução.", "calendario"),
            ("Atendimento online", "Consulta por vídeo, com o mesmo cuidado do presencial.", "video"),
        ],
        "subtipos": [],
        "situacoes": [
            ("Já tentei várias dietas", "Dieta pronta não conhece a sua rotina. O plano parte do seu dia a dia.", "repete"),
            ("Não tenho tempo", "O cardápio considera seus horários, o trabalho e o que dá para preparar.", "relogio"),
            ("Exames alterados", "Colesterol, glicose e outros exames entram no planejamento.", "atividade"),
            ("Quero mais disposição", "A alimentação tem papel na energia do dia. A consulta avalia o seu caso.", "sol"),
        ],
        "passos": [
            ("Primeira conversa", "Você conta sua rotina, histórico e objetivo.", "conversa"),
            ("Plano para você", "O plano alimentar é montado para o seu dia a dia.", "lista"),
            ("Acompanhamento", "Nos retornos, o plano é ajustado conforme a evolução.", "atividade"),
        ],
        "faq": [
            ("Preciso levar exames?", "Se tiver exames recentes, leve. Eles ajudam a montar o plano."),
            ("O atendimento é online também?", "Confirme pelo WhatsApp se há atendimento online e como funciona."),
            ("Vou ter que cortar tudo o que gosto?", "O plano considera o que você gosta de comer e a sua rotina."),
            ("De quanto em quanto tempo são os retornos?", "Depende do objetivo. A frequência é combinada na consulta."),
        ],
        "chamada": ("Agende sua consulta", "Chame no WhatsApp e escolha o melhor horário para começar."),
        "regra": "CFN 599/2018: CRN obrigatório, sem promessa de resultado, sem antes e depois, sem preço.",
        "faixa": ["Plano alimentar", "Rotina", "Exames", "Acompanhamento", "Consulta online"],
        "etapas": ["Conversa", "Avaliação", "Plano", "Retorno"],
    },
    "advogado": {
        "nome": "Advocacia", "lugar": "escritório", "cliente": "cliente", "conselho": "OAB/GO",
        "profissao": "Advogado(a)", "cor": "#2E3A59",
        "botao": "Falar com o escritório", "botao2": "Áreas de atuação", "abre_whats": "Olá! Vi o site e gostaria de falar com o escritório.",
        "titulos": [
            ("Orientação jurídica", "em linguagem clara."),
            ("Você entende o seu caso", "antes de decidir."),
            ("Advocacia próxima,", "do primeiro contato ao fim."),
        ],
        "subtitulo": "Escritório no {bairro}, em Goiânia. Atendimento com explicação clara de cada etapa do seu caso.",
        "sobre": ("Cada caso começa por uma boa conversa.", " O escritório escuta, analisa os documentos e explica as possibilidades em linguagem simples, para você decidir com segurança."),
        "servicos": [
            ("Consultoria", "Análise do caso e orientação sobre os caminhos possíveis.", "conversa"),
            ("Contratos", "Elaboração e revisão de contratos.", "documento"),
            ("Família", "Divórcio, guarda, pensão e inventário.", "coracao"),
            ("Trabalhista", "Orientação a trabalhadores e empresas.", "maleta"),
            ("Cível", "Indenizações, cobranças e direito do consumidor.", "balanca"),
        ],
        "subtipos": [],
        "situacoes": [
            ("Recebi uma notificação", "Antes de responder, vale entender o que ela pede e os prazos.", "documento"),
            ("Vou assinar um contrato", "Uma revisão antes de assinar evita dor de cabeça depois.", "caneta"),
            ("Questão de família", "Divórcio, guarda e inventário pedem cuidado e conversa.", "coracao"),
            ("Problema no trabalho", "Entender seus direitos é o primeiro passo.", "maleta"),
        ],
        "passos": [
            ("Primeiro contato", "Você explica a situação pelo WhatsApp ou por telefone.", "conversa"),
            ("Análise", "O escritório analisa os documentos e o caso.", "busca"),
            ("Orientação", "Você recebe os caminhos possíveis e decide como seguir.", "lista"),
        ],
        "faq": [
            ("Como funciona o primeiro atendimento?", "Você explica a situação e o escritório orienta sobre os próximos passos."),
            ("Atendem online?", "Confirme pelo WhatsApp se há atendimento online."),
            ("Quais documentos levar?", "Leve o que tiver sobre o caso. O escritório orienta o que mais for preciso."),
        ],
        "chamada": ("Fale com o escritório", "Explique sua situação e receba a orientação sobre os próximos passos."),
        "regra": "Provimento OAB 205/2021: sem promessa de resultado, sem preço, sem captação ostensiva; OAB visível.",
        "faixa": ["Consultoria", "Contratos", "Família", "Trabalhista", "Cível"],
        "etapas": ["Contato", "Análise", "Orientação", "Acompanhamento"],
    },
    "estetica": {
        "nome": "Estética", "lugar": "clínica", "cliente": "cliente", "conselho": "",
        "profissao": "Profissional de estética", "cor": "#9A6B5B",
        "botao": "Agendar avaliação", "botao2": "Ver procedimentos", "abre_whats": "Olá! Vi o site e quero agendar uma avaliação.",
        "titulos": [
            ("Cuidado com a pele", "feito com avaliação."),
            ("Estética com indicação,", "não com moda."),
            ("O procedimento certo", "começa na avaliação."),
        ],
        "subtitulo": "Clínica de estética no {bairro}, em Goiânia. Cada procedimento é indicado depois de uma avaliação do seu caso.",
        "sobre": ("Antes do procedimento, a avaliação.", " A profissional entende sua pele, seu histórico e o que você espera, e indica o que faz sentido para você."),
        "servicos": [
            ("Avaliação", "Análise da pele e conversa sobre o que você procura.", "busca"),
            ("Limpeza de pele", "Higienização profunda e cuidado com a pele do rosto.", "gota"),
            ("Tratamentos faciais", "Protocolos indicados depois da avaliação.", "brilho"),
            ("Tratamentos corporais", "Procedimentos para o corpo, com acompanhamento.", "atividade"),
        ],
        "subtipos": [],
        "situacoes": [
            ("Manchas na pele", "Existem várias causas. A avaliação indica o cuidado certo.", "sol"),
            ("Pele oleosa", "O tratamento depende do tipo de pele e da rotina.", "gota"),
            ("Primeira vez", "A avaliação explica cada etapa antes de começar.", "conversa"),
            ("Rotina corrida", "Os horários são combinados para caber no seu dia.", "relogio"),
        ],
        "passos": [
            ("Avaliação", "Conversa e análise do seu caso.", "busca"),
            ("Indicação", "Você recebe a indicação do que faz sentido.", "lista"),
            ("Acompanhamento", "As sessões são acompanhadas de perto.", "atividade"),
        ],
        "faq": [
            ("Preciso de avaliação antes?", "Sim. É nela que o procedimento é indicado."),
            ("Quantas sessões são necessárias?", "Depende do caso. A quantidade é combinada na avaliação."),
            ("Como agendar?", "Chame no WhatsApp e escolha o melhor horário."),
        ],
        "chamada": ("Agende sua avaliação", "Chame no WhatsApp e escolha o melhor horário."),
        "regra": "Sem promessa de resultado, sem antes e depois, sem preço; registro do responsável quando houver.",
        "faixa": ["Avaliação", "Pele", "Facial", "Corporal", "Bem-estar"],
        "etapas": ["Avaliação", "Indicação", "Sessões", "Retorno"],
    },
    "psicologo": {
        "nome": "Psicologia", "lugar": "consultório", "cliente": "paciente", "conselho": "CRP-09",
        "profissao": "Psicólogo(a)", "cor": "#5E6B8C",
        "botao": "Agendar sessão", "botao2": "Como funciona", "abre_whats": "Olá! Vi o site e gostaria de agendar uma sessão.",
        "titulos": [
            ("Um lugar para falar", "com calma."),
            ("Terapia no seu tempo,", "com escuta de verdade."),
            ("Cuidar da mente", "também é rotina."),
        ],
        "subtitulo": "Atendimento psicológico no {bairro}, em Goiânia, presencial ou online. Um espaço seguro e sigiloso para você.",
        "sobre": ("A primeira sessão é uma conversa.", " Você conta o que te trouxe até aqui e, juntos, vocês entendem como seguir. Tudo com sigilo e no seu ritmo."),
        "servicos": [
            ("Psicoterapia individual", "Sessões para adultos, com escuta e acolhimento.", "conversa"),
            ("Atendimento online", "Sessões por vídeo, com o mesmo sigilo do presencial.", "video"),
            ("Ansiedade e estresse", "Acompanhamento para lidar com a rotina e as preocupações.", "atividade"),
            ("Orientação", "Apoio em momentos de mudança e decisão.", "bussola"),
        ],
        "subtipos": [],
        "situacoes": [
            ("Ansiedade", "Preocupação constante merece atenção e cuidado.", "atividade"),
            ("Cansaço", "Quando a rotina pesa, falar ajuda a organizar.", "lua"),
            ("Mudanças", "Fases novas trazem dúvidas. A terapia ajuda a atravessar.", "bussola"),
            ("Relacionamentos", "Família, trabalho e relações também cabem na sessão.", "coracao"),
        ],
        "passos": [
            ("Contato", "Você chama e escolhe o horário.", "conversa"),
            ("Primeira sessão", "Uma conversa para entender o que você procura.", "coracao"),
            ("Acompanhamento", "As sessões seguem no ritmo combinado.", "calendario"),
        ],
        "faq": [
            ("A sessão é sigilosa?", "Sim. O sigilo é parte do código de ética da psicologia."),
            ("Atende online?", "Confirme pelo WhatsApp se há atendimento online."),
            ("Quanto tempo dura cada sessão?", "Em geral, cerca de 50 minutos. Confirme ao agendar."),
        ],
        "chamada": ("Agende sua primeira sessão", "Chame no WhatsApp e escolha o melhor horário."),
        "regra": "CFP 03/2007 e 11/2018: CRP visível, sem promessa de cura ou resultado, sem preço.",
        "faixa": ["Psicoterapia", "Escuta", "Sigilo", "Presencial", "Online"],
        "etapas": ["Contato", "Acolhimento", "Sessões", "Acompanhamento"],
    },
    "generico": {
        "nome": "Atendimento", "lugar": "empresa", "cliente": "cliente", "conselho": "",
        "profissao": "Responsável", "cor": "#33507A",
        "botao": "Falar no WhatsApp", "botao2": "Ver serviços", "abre_whats": "Olá! Vi o site e gostaria de mais informações.",
        "titulos": [("Atendimento próximo,", "do primeiro contato ao fim."), ("Você entende o serviço", "antes de contratar.")],
        "subtitulo": "No {bairro}, em Goiânia. Fale direto com a equipe e tire suas dúvidas.",
        "sobre": ("Cada atendimento começa por entender você.", " A equipe escuta o que você precisa e explica cada etapa do serviço."),
        "servicos": [],
        "subtipos": [],
        "situacoes": [],
        "passos": [
            ("Você chama", "Conta o que precisa pelo WhatsApp.", "conversa"),
            ("Conversa", "A equipe entende o seu caso.", "busca"),
            ("Atendimento", "Você recebe o serviço combinado.", "check"),
        ],
        "faq": [("Como faço para começar?", "Chame no WhatsApp e conte o que precisa.")],
        "chamada": ("Fale com a gente", "Chame no WhatsApp e tire suas dúvidas."),
        "regra": "Sem preço, sem promessa, sem dado inventado.",
        "faixa": ["Atendimento", "Qualidade", "Goiânia"],
        "etapas": ["Contato", "Conversa", "Serviço", "Retorno"],
    },
}


from nichos_extra import NICHOS_EXTRA, PISTAS_EXTRA  # noqa: E402

NICHOS.update(NICHOS_EXTRA)
# fim do título da abertura montado com os fatos ("Advocacia no Centro, em linguagem clara.")
for _chave, _tag in (("dentista", "com calma e clareza."), ("nutricionista", "no seu ritmo."), ("advogado", "em linguagem clara."),
                     ("estetica", "com calma e cuidado."), ("psicologo", "com escuta e cuidado."), ("generico", "do primeiro contato ao fim."),
                     ("contabilidade", "sem susto no fim do mês."), ("arquitetura", "do esboço à entrega."), ("personal", "no seu ritmo."),
                     ("fisioterapia", "com calma e clareza."), ("medico", "com tempo para ouvir você."), ("veterinario", "com calma e carinho.")):
    NICHOS[_chave].setdefault("tag", _tag)


def sem_acento(texto):
    return "".join(c for c in unicodedata.normalize("NFD", str(texto or "").lower()) if unicodedata.category(c) != "Mn")


def descobrir_nicho(empresa, maps=None):
    """O nicho da pesquisa às vezes está errado (nutricionistas gravadas como dentistas): o nome e o @ decidem antes."""
    pistas = sem_acento(" ".join(str(x or "") for x in (
        empresa.get("nome"), (empresa.get("contatos") or {}).get("instagram"), (empresa.get("dica") or {}).get("instagram"),
        (maps or {}).get("type"), (maps or {}).get("subtypes"))))
    nicho = sem_acento(empresa.get("nicho"))
    for chave, termos in (("nutricionista", r"nutri"), ("psicologo", r"psic"), ("advogado", r"advoc|advog|juridic|direito"),
                          ("dentista", r"odont|dentist|ortodon|sorriso|oral"), ("estetica", r"estetic|beleza|biomed|harmoniza")):
        if re.search(termos, pistas):
            return chave
    for chave, termos in PISTAS_EXTRA:
        if re.search(termos, pistas):
            return chave
    for chave, termos in PISTAS_EXTRA + [("nutricionista", r"nutri"), ("psicologo", r"psic"), ("advogado", r"advoc|advog"),
                          ("estetica", r"estetic"), ("dentista", r"odont|dent")]:
        if re.search(termos, nicho):
            return chave
    return "generico"
