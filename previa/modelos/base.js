/* Interações comuns dos modelos de prévia. Tudo funciona sem animação (prefers-reduced-motion). */
(function () {
  var doc = document.documentElement, calmo = matchMedia('(prefers-reduced-motion: reduce)').matches;
  doc.classList.add('js');

  // 1. entrada ao rolar
  var ver = 'IntersectionObserver' in window ? new IntersectionObserver(function (es) {
    es.forEach(function (en) { if (en.isIntersecting) { en.target.classList.add('visto'); ver.unobserve(en.target); } });
  }, { threshold: .12, rootMargin: '0px 0px -6% 0px' }) : null;
  document.querySelectorAll('[data-revela]').forEach(function (el) { ver ? ver.observe(el) : el.classList.add('visto'); });

  // 2. título entra palavra por palavra (o texto já está na página; só ganha a animação)
  if (!calmo) document.querySelectorAll('[data-palavras]').forEach(function (t) {
    var i = 0;
    (function quebra(no) {
      Array.prototype.slice.call(no.childNodes).forEach(function (n) {
        if (n.nodeType === 3 && n.textContent.trim()) {
          var frag = document.createDocumentFragment();
          n.textContent.split(/(\s+)/).forEach(function (p) {
            if (!p) return;
            if (/^\s+$/.test(p)) { frag.appendChild(document.createTextNode(p)); return; }
            var s = document.createElement('span'); s.className = 'palavra'; s.textContent = p;
            s.style.animationDelay = (0.15 + i++ * 0.07) + 's'; frag.appendChild(s);
          });
          n.parentNode.replaceChild(frag, n);
        } else if (n.nodeType === 1 && !n.classList.contains('palavra') && n.tagName !== 'MARK') quebra(n);
      });
    })(t);
  });

  // garantia: se a animação não rodar (aba escondida, navegador lento), o título aparece assim mesmo
  setTimeout(function () { doc.classList.add('palavras-ok'); }, 2600);

  // 3. menu que muda ao rolar, barra de leitura e item ativo
  var menu = document.querySelector('.menu'), barra = menu && menu.querySelector('.leitura');
  var links = menu ? Array.prototype.slice.call(menu.querySelectorAll('nav a[href^="#"]')) : [];
  var whats = document.querySelector('.whats');
  function rolar() {
    var y = scrollY, alto = doc.scrollHeight - innerHeight;
    if (menu) menu.classList.toggle('rolou', y > 40);
    if (barra) barra.style.width = (alto > 0 ? y / alto * 100 : 0) + '%';
    if (whats) whats.classList.toggle('mostra', y > innerHeight * .55);
    var atual = null;
    links.forEach(function (a) { var s = document.querySelector(a.getAttribute('href')); if (s && s.getBoundingClientRect().top < innerHeight * .4) atual = a; });
    links.forEach(function (a) { a.classList.toggle('ativo', a === (atual || links[0])); });
    document.querySelectorAll('[data-paralaxe]').forEach(function (el) {
      if (calmo) return;
      var r = el.getBoundingClientRect(), f = parseFloat(el.dataset.paralaxe) || .08;
      el.style.transform = 'translate3d(0,' + ((r.top + r.height / 2 - innerHeight / 2) * -f).toFixed(1) + 'px,0)';
    });
  }
  addEventListener('scroll', rolar, { passive: true }); rolar();

  // 4. números que contam
  var contar = 'IntersectionObserver' in window ? new IntersectionObserver(function (es) {
    es.forEach(function (en) {
      if (!en.isIntersecting) return; contar.unobserve(en.target);
      var el = en.target, alvo = parseFloat(el.dataset.conta), casas = (el.dataset.conta.split(/[.,]/)[1] || '').length, t0 = null;
      if (calmo || !alvo) return;
      function passo(t) {
        t0 = t0 || t; var p = Math.min(1, (t - t0) / 1600), v = alvo * (1 - Math.pow(1 - p, 3));
        el.textContent = v.toFixed(casas).replace('.', ',') + (el.dataset.sufixo || '');
        if (p < 1) requestAnimationFrame(passo);
      }
      requestAnimationFrame(passo);
    });
  }, { threshold: .5 }) : null;
  document.querySelectorAll('[data-conta]').forEach(function (el) { contar && contar.observe(el); });

  // 5. abas com indicador que desliza
  document.querySelectorAll('[data-abas]').forEach(function (caixa) {
    var bs = caixa.querySelectorAll('.abas-lista button'), ps = caixa.querySelectorAll('.abas-painel'), ind = caixa.querySelector('.indicador');
    function liga(i) {
      bs.forEach(function (b, j) { b.classList.toggle('ativo', i === j); b.setAttribute('aria-selected', i === j); });
      ps.forEach(function (p, j) { p.classList.toggle('ativo', i === j); });
      if (ind) { ind.style.top = bs[i].offsetTop + 'px'; ind.style.height = bs[i].offsetHeight + 'px'; }
    }
    bs.forEach(function (b, i) { b.addEventListener('click', function () { liga(i); }); });
    liga(0); addEventListener('resize', function () { liga([].indexOf.call(bs, caixa.querySelector('.abas-lista .ativo'))); });
  });

  // 6. lista numerada que troca a foto ao lado
  document.querySelectorAll('[data-lista-troca]').forEach(function (caixa) {
    var itens = caixa.querySelectorAll('li'), fotos = caixa.querySelectorAll('.palco img'), leg = caixa.querySelector('.palco .legenda b');
    function liga(i) {
      itens.forEach(function (li, j) { li.classList.toggle('ativo', i === j); });
      fotos.forEach(function (f, j) { f.classList.toggle('ativa', j === i % fotos.length); });
      if (leg) leg.textContent = itens[i].querySelector('h3').textContent;
    }
    itens.forEach(function (li, i) { li.querySelector('button').addEventListener('click', function () { liga(i); }); });
    liga(0);
  });

  // 7. carrossel com setas
  document.querySelectorAll('[data-carrossel]').forEach(function (bloco) {
    var trilho = bloco.querySelector('.carrossel');
    bloco.querySelectorAll('[data-dir]').forEach(function (b) {
      b.addEventListener('click', function () {
        var c = trilho.firstElementChild; trilho.scrollBy({ left: (c ? c.offsetWidth + 16 : 320) * +b.dataset.dir, behavior: calmo ? 'auto' : 'smooth' });
      });
    });
  });

  // 8. dúvidas que abrem com animação
  document.querySelectorAll('.pergunta button').forEach(function (b) {
    b.addEventListener('click', function () {
      var p = b.parentNode, aberta = p.classList.toggle('aberta'); b.setAttribute('aria-expanded', aberta);
    });
  });

  // 9. passos que se acendem em sequência
  document.querySelectorAll('[data-passos]').forEach(function (caixa) {
    var ps = caixa.querySelectorAll('.passo'), i = 0, rodando = null;
    if (!ps.length) return;
    function acende() { ps.forEach(function (p, j) { p.classList.toggle('ativo', j === i); }); i = (i + 1) % ps.length; }
    var obs = new IntersectionObserver(function (es) {
      es.forEach(function (en) {
        if (en.isIntersecting && !rodando) { acende(); if (!calmo) rodando = setInterval(acende, 3400); }
        else if (!en.isIntersecting && rodando) { clearInterval(rodando); rodando = null; }
      });
    }, { threshold: .3 });
    obs.observe(caixa);
  });

  // 10. cartões que reagem ao mouse
  if (!calmo && matchMedia('(hover:hover)').matches) document.querySelectorAll('[data-inclina]').forEach(function (c) {
    c.addEventListener('mousemove', function (ev) {
      var r = c.getBoundingClientRect(), x = (ev.clientX - r.left) / r.width - .5, y = (ev.clientY - r.top) / r.height - .5;
      c.style.transform = 'perspective(900px) rotateY(' + (x * 6) + 'deg) rotateX(' + (-y * 6) + 'deg) translateY(-4px)';
    });
    c.addEventListener('mouseleave', function () { c.style.transform = ''; });
  });

  // 11. fotos da abertura que trocam sozinhas (receita B) com linha 01——02
  document.querySelectorAll('[data-slides]').forEach(function (caixa) {
    var fs = caixa.querySelectorAll('.slide'), mini = caixa.querySelectorAll('[data-vai]'), cont = caixa.querySelector('[data-contador]'), i = 0, t;
    if (fs.length < 2) return;
    function vai(n) {
      i = (n + fs.length) % fs.length;
      fs.forEach(function (f, j) { f.classList.toggle('ativa', j === i); });
      mini.forEach(function (m, j) { m.classList.toggle('ativo', j === i); });
      if (cont) cont.textContent = ('0' + (i + 1)).slice(-2);
      clearTimeout(t); if (!calmo) t = setTimeout(function () { vai(i + 1); }, 5200);
    }
    mini.forEach(function (m) { m.addEventListener('click', function () { vai(+m.dataset.vai); }); });
    caixa.querySelectorAll('[data-passa]').forEach(function (b) { b.addEventListener('click', function () { vai(i + +b.dataset.passa); }); });
    vai(0);
  });

  // 12. barra de agendamento: monta a mensagem e abre o WhatsApp
  document.querySelectorAll('[data-agenda]').forEach(function (form) {
    form.addEventListener('submit', function (ev) {
      ev.preventDefault();
      var dados = new FormData(form), partes = [];
      dados.forEach(function (v, k) { if (v) partes.push(k + ': ' + v); });
      var texto = form.dataset.abre + (partes.length ? '\n' + partes.join('\n') : '');
      var destino = form.dataset.agenda;
      if (destino) open(destino + '?text=' + encodeURIComponent(texto), '_blank', 'noopener');
      else location.hash = '#contato';
    });
  });

  // 13. menu do celular
  var abre = document.querySelector('.menu-celular'), gaveta = document.querySelector('.gaveta');
  if (abre && gaveta) {
    abre.addEventListener('click', function () { var a = gaveta.classList.toggle('aberta'); abre.setAttribute('aria-expanded', a); });
    gaveta.querySelectorAll('a').forEach(function (a) { a.addEventListener('click', function () { gaveta.classList.remove('aberta'); }); });
  }

  // 14. horário: destaca o dia de hoje
  var hoje = ['domingo', 'segunda', 'terça', 'quarta', 'quinta', 'sexta', 'sábado'][new Date().getDay()];
  document.querySelectorAll('.horario [data-dia]').forEach(function (d) { if (d.dataset.dia.indexOf(hoje) === 0) d.classList.add('hoje'); });
})();
