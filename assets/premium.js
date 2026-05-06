/* UAE Premium Numbers — premium scroll reveal + micro-interactions
   Adds .is-visible to elements with .reveal as they enter viewport.
   Marks plan/pricing cards and section headings as reveal targets if they
   don't already have the class — zero-config enhancement. */
(function () {
  'use strict';

  if (typeof window === 'undefined' || !('IntersectionObserver' in window)) return;

  const SELECTORS = [
    '.section-heading',
    '.plan-card',
    '.pricing-card',
    '.intent-btn',
    'section h2',
    'section h3',
    '.trust-badges > div > div',
    '[data-reveal]'
  ];

  function autoTagReveal() {
    SELECTORS.forEach(function (sel) {
      document.querySelectorAll(sel).forEach(function (el) {
        if (!el.classList.contains('reveal')) el.classList.add('reveal');
      });
    });
  }

  const observer = new IntersectionObserver(function (entries) {
    entries.forEach(function (entry) {
      if (entry.isIntersecting) {
        entry.target.classList.add('is-visible');
        observer.unobserve(entry.target);
      }
    });
  }, {
    threshold: 0.12,
    rootMargin: '0px 0px -40px 0px'
  });

  function init() {
    autoTagReveal();
    document.querySelectorAll('.reveal').forEach(function (el) {
      observer.observe(el);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
