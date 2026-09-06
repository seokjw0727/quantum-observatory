const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)");

export function setupNavigation() {
  const header = document.querySelector(".site-header");
  const nav = document.querySelector("#main-nav");
  const toggle = document.querySelector("#menu-toggle");
  const mobile = matchMedia("(max-width: 760px)");
  let open = false;
  function setOpen(next, restoreFocus = false) {
    open = next && mobile.matches;
    header.classList.toggle("menu-open", open);
    toggle.setAttribute("aria-expanded", String(open));
    toggle.setAttribute("aria-label", open ? "Close navigation" : "Open navigation");
    toggle.querySelector(".menu-label").textContent = open ? "Close" : "Menu";
    nav.inert = mobile.matches && !open;
    if (restoreFocus) toggle.focus();
  }
  header.classList.add("navigation-ready");
  setOpen(false);
  toggle.addEventListener("click", () => setOpen(!open));
  nav.addEventListener("click", (event) => {
    if (event.target.closest("a")) setOpen(false);
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && open) {
      event.preventDefault();
      setOpen(false, true);
    }
  });
  document.addEventListener("click", (event) => {
    if (open && !header.contains(event.target)) setOpen(false);
  });
  header.addEventListener("focusout", (event) => {
    if (open && !header.contains(event.relatedTarget)) setOpen(false);
  });
  mobile.addEventListener("change", () => {
    const focusInNav = nav.contains(document.activeElement);
    setOpen(false, mobile.matches && focusInNav);
    if (!mobile.matches && document.activeElement === toggle)
      nav.querySelector('[aria-current="page"]')?.focus();
  });
}

let observer;
export function revealPage(root) {
  observer?.disconnect();
  if (reducedMotion.matches || !("IntersectionObserver" in window)) return;
  observer = new IntersectionObserver((entries) => {
    for (const entry of entries) {
      if (!entry.isIntersecting) continue;
      entry.target.classList.remove("reveal-pending");
      entry.target.classList.add("revealed");
      observer.unobserve(entry.target);
    }
  }, { threshold: 0.06 });
  root.querySelectorAll(".page-heading, .stats, .analytics > .panel, .archive-card, .method-grid > *, .research-panel").forEach((element, index) => {
    element.style.setProperty("--reveal-delay", `${Math.min(index % 4, 3) * 45}ms`);
    element.classList.add("reveal-pending");
    observer.observe(element);
  });
}
reducedMotion.addEventListener("change", () => {
  if (reducedMotion.matches) {
    observer?.disconnect();
    document.querySelectorAll(".reveal-pending").forEach((el) => el.classList.remove("reveal-pending"));
  }
});

let closing = false;
export async function closeDetail(dialog) {
  if (!dialog.open || closing) return;
  closing = true;
  try {
    if (!reducedMotion.matches) {
      const mobile = matchMedia("(max-width: 760px)").matches;
      await dialog.animate([
        { opacity: 1, transform: "translate(0, 0)" },
        { opacity: 0, transform: mobile ? "translateY(24px)" : "translateX(48px)" },
      ], { duration: 180, easing: "cubic-bezier(.4,0,1,1)" }).finished;
    }
  } finally {
    dialog.close();
    closing = false;
  }
}
