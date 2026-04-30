document.addEventListener('DOMContentLoaded', function() {
  document.querySelectorAll('.expandable-trigger').forEach(function(el) {
    el.addEventListener('click', function() {
      this.parentElement.classList.toggle('expanded');
    });
  });
});
