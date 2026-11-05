/* (06/11, capture d'Ahmed, page Téléphone : « Le cockpit ne répond pas : erreur 403 ») le jeton de la page change à chaque relance du
   cockpit ; une page restée ouverte gardait l'ancien et tout lui était refusé jusqu'à ce qu'on la recharge. Comme Parler (23/10) : sur un
   refus 403 d'une demande qui porte le jeton, la page redemande sa propre adresse, y reprend le nouveau jeton, et réessaie une fois. */
(() => {
  const f = window.fetch.bind(window);
  let enCours = null;
  const renouveler = () => enCours || (enCours = f(location.pathname, { cache: 'no-store' })
    .then(r => r.text())
    .then((t) => {
      const m = t.match(/<meta name="cockpit-jeton" content="([0-9a-f]{20,200})">/), meta = document.querySelector('meta[name="cockpit-jeton"]');
      if (!m || !meta || meta.content === m[1]) return false;
      meta.content = m[1];
      return true;
    })
    .catch(() => false)
    .finally(() => setTimeout(() => { enCours = null; }, 2000)));
  window.fetch = async (url, o = {}) => {
    let r = await f(url, o);
    const h = o && o.headers;
    if (r.status === 403 && h && !(h instanceof Headers) && h['X-Jeton'] !== undefined && !(o.signal && o.signal.aborted) && await renouveler()) {
      const meta = document.querySelector('meta[name="cockpit-jeton"]');
      r = await f(url, { ...o, headers: { ...h, 'X-Jeton': meta ? meta.content : '' } });
    }
    return r;
  };
})();
