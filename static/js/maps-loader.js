/* ── Google Maps API Loader ────────────────────────────────── */
(function() {
  var apiKey = '{{ config.get("GOOGLE_PLACES_API_KEY", "YOUR_GOOGLE_PLACES_API_KEY") }}';
  if (apiKey && apiKey !== 'YOUR_GOOGLE_PLACES_API_KEY') {
    var s = document.createElement('script');
    s.src = 'https://maps.googleapis.com/maps/api/js?key=' + apiKey + '&libraries=places';
    s.async = true;
    s.defer = true;
    document.head.appendChild(s);
  }
})();
