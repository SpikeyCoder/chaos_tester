document.addEventListener('DOMContentLoaded', function() {
  // Hamburger menu toggle
  var toggle = document.getElementById('navToggle');
  if (toggle) {
    toggle.addEventListener('click', function() {
      document.getElementById('mainNav').classList.toggle('open');
      var expanded = this.getAttribute('aria-expanded') === 'true';
      this.setAttribute('aria-expanded', expanded ? 'false' : 'true');
    });
  }

  // Smooth scroll for nav links with data-scroll-target
  document.querySelectorAll('[data-scroll-target]').forEach(function(link) {
    link.addEventListener('click', function(e) {
      if (window.location.pathname === '/') {
        e.preventDefault();
        var target = document.getElementById(this.getAttribute('data-scroll-target'));
        if (target) {
          target.scrollIntoView({ behavior: 'smooth' });
        }
      }
    });
  });

  // Header scroll shadow
  var header = document.querySelector('header');
  if (header) {
    window.addEventListener('scroll', function() {
      if (window.scrollY > 10) {
        header.classList.add('scrolled');
      } else {
        header.classList.remove('scrolled');
      }
    });
  }

  // Scroll reveal animations
  var observer = new IntersectionObserver(function(entries) {
    entries.forEach(function(entry) {
      if (entry.isIntersecting) {
        entry.target.classList.add('visible');
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.1 });

  document.querySelectorAll('.scroll-reveal').forEach(function(el) {
    observer.observe(el);
  });
});
