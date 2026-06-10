document.addEventListener("DOMContentLoaded", function () {
  var navToggle = document.getElementById("nav-toggle");
  var navLinks = document.querySelector(".nav-links");

  if (navToggle && navLinks) {
    navToggle.addEventListener("click", function () {
      navLinks.classList.toggle("show");
    });
  }

  var btnTanya = document.getElementById("btn-tanya-sekarang");
  if (btnTanya) {
    btnTanya.addEventListener("click", function () {
      var toggle = document.getElementById("rag-widget-toggle");
      var box = document.getElementById("rag-widget-box");
      if (toggle && box && box.getAttribute("data-open") !== "true") {
        toggle.click();
      }
    });
  }
});
