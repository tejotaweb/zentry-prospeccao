# Como fazer uma prévia

Decisão de 31/10/2026: cada prévia é feita para a empresa, com análise do perfil, copy própria, fotos e informações dela. É só uma prévia para despertar interesse. Se a pessoa aprovar, o layout definitivo é criado depois.

Este processo substitui o formulário e o gerador automático (`previa/gerar.py`) como caminho principal.

## Dois caminhos (decisão dele em 02/11/2026)
- **A empresa já tem site:** estudar o site atual e listar o que melhorar no layout e na copy, com print de cada ponto. A prévia é um layout melhor, com a copy alinhada ao trabalho real dela. A análise compara o antes e o depois.
- **A empresa não tem site:** estudar o perfil inteiro e montar um site com layout sofisticado.
- **Nos dois casos:** é um site de exemplo, e isso fica claro na própria página. Se ela aprovar, o web designer monta um site mais elaborado.
- **Estilo:** seguir as referências de layout dele (`metodo/referencias/REFERENCIAS.md`), variando de uma empresa para outra.

## Automático para as aprovadas (decisão dele em 02/11/2026)
Toda empresa aprovada na pesquisa entra numa fila que faz análise, copy e layout sozinha (ver CLAUDE.md). O veredito dele vem depois, na tela de Prévias, antes de a prévia ir para alguém.

## Ordem, uma peça por vez, esperando o veredito (treino e ajustes à mão)
1. **Análise:** ler o perfil público do Instagram, a bio, os destaques e os posts recentes. Anotar serviços, especialidades, equipe, CRO, endereço, horário, tom, cores, logo e fotos boas. Cada informação com a fonte.
2. **Copy:** escrever seção por seção, usando só o que a análise achou. O que faltar fica marcado para confirmar.
3. **Fotos:** escolher as melhores do perfil. Mostrar a seleção antes de usar.
4. **Layout:** montar a prévia, seguindo `METODO-SITES.md`, com um conceito visual próprio. Conferir no computador, tablet e celular.
5. **Veredito dele:** anotar em `aprendizados-previas.md`: data, o que foi mostrado, a frase dele e a regra.

## Fotos do perfil
- Fora: paciente identificável, procedimento sendo feito, antes e depois, foto com marca de terceiros, print com texto por cima.
- Prévia fica privada e fora do Google. As fotos são da clínica e ainda não têm autorização para ir ao ar: no site definitivo, pedir o aval dela.
- Nunca gerar rosto com IA para pessoa real.

## Dados
- Nada inventado: depoimento, número, formação e resultado só com fonte. Avaliação do Google só depois de validar com a clínica.
- Regras do CFO: ver a seção 10 de `METODO-SITES.md`.

## Regras de layout que ele já deu (detalhes em aprendizados-previas.md)
- Paleta: medir nos posts e no logo da empresa. Nunca tirar da foto do ambiente.
- Abertura: fundo de ponta a ponta, conteúdo no grid, altura generosa, nada colado na borda. Título nunca sobre rosto.
- Página preenchida: cartão grande sempre com conteúdo real ou recurso visual.
- Interações e animações em toda prévia.
- Foto real no lugar de desenho, sempre que o perfil tiver.
- Nada se repete: cada prévia tem layout próprio e precisa ser melhor que a anterior. Conferir `metodo/layouts-usados.md` antes de montar e atualizar depois.

## Antes de dar como pronta
- Tapando o nome e o logo, dá para reconhecer a clínica?
- Dá vontade de abrir no celular e mostrar para o sócio?
- Está no nível dos melhores sites do seu portfólio (a sua "régua")?
- Faixa no topo dizendo que é um site de exemplo e que a versão completa vem depois da aprovação.
- Rodapé com "Proposta de site por <nome do perfil>" e `noindex`.

## Regras automáticas da prévia (03/11/2026) — o sistema aplica sozinho em toda montagem

Abertura
- Modelo padrão B (o mais aprovado nos testes): foto cheia em cartão, título em 2 linhas, texto de apoio, 2 botões, cartão "conheça por dentro", etiquetas dos serviços e barra embaixo. Outros modelos só por "Trocar modelo".
- Título da abertura = frase curta do nicho (até 42 letras). Bairro, cidade e serviços vão no texto de apoio. Título longo ganha letra menor para caber em 2 linhas, sem recuo na 2ª linha.

Fotos (sem IA: Vision do Mac em `previa/bin/rosto` + cor dos pixels)
- Cada foto cortada "olha" para o maior rosto (object-position no rosto).
- Retrato de "quem atende" só com rosto inteiro e de tamanho médio; uma pessoa só tem prioridade.
- Ficam de fora: close cortado (rosto enorme ou batendo na borda), post/panfleto (5% ou mais da imagem com texto) e, em saúde e estética, foto de procedimento e antes e depois (40% ou mais de tom de pele/boca).
- O resumo da prévia diz quantas ficaram de fora.

Aprende com ele
- Enquadramento escolhido no editor (painel "Foto" → clicar no ponto) fica guardado na foto (`foco` em fotos.json) e vale em toda remontagem.
- No mesmo painel: trocar por outra foto da empresa (grade com todas as fotos baixadas) ou enviar do computador.
