(function () {
  var btn = document.getElementById("badge-copy");
  var ta = document.getElementById("badge-embed");
  if (!btn || !ta) return;
  btn.addEventListener("click", function () {
    ta.select();
    var done = function () { btn.textContent = "Copied!"; setTimeout(function () { btn.textContent = "Copy code"; }, 2000); };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(ta.value).then(done, function () { try { document.execCommand("copy"); done(); } catch (e) {} });
    } else { try { document.execCommand("copy"); done(); } catch (e) {} }
  });
})();
