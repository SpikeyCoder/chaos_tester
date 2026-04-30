/* Header scroll effect */
(function() {
  var header = document.querySelector('header');
  var scrollThreshold = 20;
  function onScroll() {
    if (window.scrollY > scrollThreshold) {
      header.classList.add('scrolled');
    } else {
      header.classList.remove('scrolled');
    }
  }
  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();
})();

/* Scroll-reveal animation via IntersectionObserver
   F-01 FIX: Elements already in the viewport on page load are immediately
   made visible so above-the-fold content (hero, form, etc.) is never hidden. */
(function() {
  var elements = document.querySelectorAll('.fade-up');
  if (!elements.length) return;

  /* Immediately reveal any element already in or near the viewport */
  function revealIfVisible(el) {
    var rect = el.getBoundingClientRect();
    var inViewport = rect.top < (window.innerHeight || document.documentElement.clientHeight) + 50;
    if (inViewport) {
      el.classList.add('visible');
      return true;
    }
    return false;
  }

  /* First pass: show above-the-fold content right now */
  var belowFold = [];
  elements.forEach(function(el) {
    if (!revealIfVisible(el)) {
      belowFold.push(el);
    }
  });

  /* Observe only below-the-fold elements for scroll-reveal */
  if (belowFold.length && 'IntersectionObserver' in window) {
    var observer = new IntersectionObserver(function(entries) {
      entries.forEach(function(entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add('visible');
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.1, rootMargin: '0px 0px -40px 0px' });
    belowFold.forEach(function(el) { observer.observe(el); });
  } else if (!('IntersectionObserver' in window)) {
    /* Fallback: show everything */
    elements.forEach(function(el) { el.classList.add('visible'); });
  }
})();