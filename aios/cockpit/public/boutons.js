/* Cockpit — l'habit des boutons de Parler.
   (04/11, 19:30, Ahmed : « Les boutons dans l'interface, tu peux mettre des icônes au lieu de "Ma voix", "Conversation",
   "Télépathie", etc. ? Un truc plus cool et parlant, et mieux agencé et organisé ») Chaque bouton .ico porte son icône SVG en
   ligne (dans parler.html) et son nom dans <span class="lib"> : caché à l'œil, lu par le lecteur d'écran, et dans l'aria-label.
   parler.js écrit encore le texte de quelques boutons avec textContent (Pause → Reprendre, « Sa voix (coupée) », « Micro coupé »,
   « 🎧 Il entend le téléphone », « 👁 Écran »…), ce qui effacerait l'icône : un MutationObserver la remet aussitôt (avant que
   l'écran ne se redessine), range le nouveau texte dans .lib et dans l'aria-label, sans l'émoji de tête. Un texte sans mots
   (« 🎧⚠ ») garde le nom d'origine ; l'alerte se voit par data-oreille (parler.html). Chargé AVANT parler.js. Aucune requête. */
(() => {
  const icones = new WeakMap();                                   // bouton → ses <svg> d'origine
  const estSvg = (n) => n && n.nodeType === 1 && String(n.tagName).toLowerCase() === 'svg';
  const estLib = (n) => n && n.nodeType === 1 && n.classList && n.classList.contains('lib');
  // ce qui se lit : sans les émojis ni les symboles de tête (🎧, 👁), ni ceux de queue (⚠)
  const nettoyer = (t) => String(t == null ? '' : t)
    .replace(/^[^\p{L}\p{N}(«"]+/u, '')
    .replace(/[\s\p{Extended_Pictographic}️‍]+$/u, '')
    .trim();

  // remet l'icône si parler.js l'a effacée ; rien à faire si le bouton est déjà rangé (dont notre propre geste)
  function ranger(b) {
    const svgs = icones.get(b);
    if (!svgs) return false;
    const enfants = [...b.childNodes];
    const lib = enfants.find(estLib);
    const intrus = enfants.filter(n => !estSvg(n) && n !== lib && !(n.nodeType === 3 && !n.textContent.trim()));
    if (!intrus.length && lib && enfants.filter(estSvg).length === svgs.length) return false;
    const brut = intrus.map(n => n.textContent).join(' ').trim();
    const texte = nettoyer(brut) || (lib && nettoyer(lib.textContent)) || b.dataset.nom || '';
    const span = document.createElement('span');
    span.className = 'lib';
    span.textContent = texte;
    b.replaceChildren(...svgs.map(s => s.cloneNode(true)), span);
    if (texte) b.setAttribute('aria-label', texte);
    return true;
  }

  function habiller(b) {
    if (icones.has(b)) return false;
    const svgs = [...b.children].filter(estSvg);
    if (!svgs.length) return false;
    icones.set(b, svgs.map(s => s.cloneNode(true)));
    b.dataset.nom = b.getAttribute('aria-label') || nettoyer(b.textContent);
    ranger(b);
    new MutationObserver(() => ranger(b)).observe(b, { childList: true, characterData: true, subtree: true });
    return true;
  }

  for (const b of document.querySelectorAll('.ico')) habiller(b);
  window.BoutonsIcones = { nettoyer, ranger, habiller };
})();
