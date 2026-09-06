const motionAllowed = () => !matchMedia("(prefers-reduced-motion: reduce)").matches;
let opened = null;

// One shared set of outside/viewport listeners, including after page re-renders.
document.addEventListener("pointerdown", (event) => {
  if (opened && !opened.contains(event.target)) opened.close();
});
document.addEventListener("scroll", (event) => {
  if (opened && !opened.contains(event.target)) opened.position();
}, true);
window.addEventListener("resize", () => opened?.position());

export function enhanceSelects(root) {
  opened?.close(true);
  root.querySelectorAll("select.select:not([data-enhanced])").forEach((select) => {
    select.dataset.enhanced = "true";
    const field = document.createElement("div");
    field.className = "select-field";
    const trigger = document.createElement("button");
    trigger.type = "button";
    trigger.id = `${select.id}-trigger`;
    trigger.className = "select select-trigger";
    trigger.setAttribute("role", "combobox");
    trigger.setAttribute("aria-haspopup", "listbox");
    trigger.setAttribute("aria-expanded", "false");
    trigger.setAttribute("aria-autocomplete", "none");
    const value = document.createElement("span");
    value.className = "select-value";
    const arrow = document.createElement("span");
    arrow.className = "select-arrow";
    arrow.setAttribute("aria-hidden", "true");
    trigger.append(value, arrow);
    select.before(field);
    field.append(select, trigger);
    const labels = [...select.labels];
    labels.forEach((label) => {
      label.id ||= `${select.id}-label`;
      label.htmlFor = trigger.id;
    });
    trigger.setAttribute("aria-labelledby", labels.map((label) => label.id).join(" ") || trigger.id);
    select.hidden = true;
    const sync = () => {
      value.textContent = select.selectedOptions[0]?.textContent || "Select";
      trigger.disabled = select.disabled;
    };
    sync();
    select.addEventListener("change", sync);
    let menu = null, active = select.selectedIndex, typeahead = "", typedAt = 0;

    function highlight(index) {
      const options = [...select.options];
      active = Math.max(0, Math.min(index, options.length - 1));
      if (!menu) return;
      [...menu.children].forEach((option, i) => option.classList.toggle("is-active", i === active));
      const option = menu.children[active];
      trigger.setAttribute("aria-activedescendant", option.id);
      // Scroll the options only; never move the page when opening a picker.
      if (option.offsetTop < menu.scrollTop) menu.scrollTop = option.offsetTop;
      else if (option.offsetTop + option.offsetHeight > menu.scrollTop + menu.clientHeight)
        menu.scrollTop = option.offsetTop + option.offsetHeight - menu.clientHeight;
    }
    function position() {
      if (!menu || !trigger.isConnected) return close(true);
      const rect = trigger.getBoundingClientRect();
      const viewport = window.visualViewport;
      const left = viewport?.offsetLeft || 0, top = viewport?.offsetTop || 0;
      const width = viewport?.width || innerWidth, height = viewport?.height || innerHeight;
      if (rect.bottom < top || rect.top > top + height) return close();
      const below = top + height - rect.bottom - 12;
      const above = rect.top - top - 12;
      const upwards = below < 220 && above > below;
      menu.style.width = `${Math.min(Math.max(rect.width, 220), width - 24)}px`;
      menu.style.maxHeight = `${Math.max(80, Math.min(320, upwards ? above : below))}px`;
      menu.style.left = `${Math.max(left + 12, Math.min(rect.left, left + width - menu.offsetWidth - 12))}px`;
      menu.style.top = `${upwards ? rect.top - menu.offsetHeight - 6 : rect.bottom + 6}px`;
      menu.style.transformOrigin = upwards ? "bottom center" : "top center";
    }
    function close(immediate = false) {
      if (!menu) return;
      const leaving = menu;
      menu = null;
      if (opened?.trigger === trigger) opened = null;
      trigger.setAttribute("aria-expanded", "false");
      trigger.removeAttribute("aria-activedescendant");
      trigger.removeAttribute("aria-controls");
      field.classList.remove("is-open");
      leaving.inert = true;
      leaving.removeAttribute("id");
      leaving.querySelectorAll("[id]").forEach((item) => item.removeAttribute("id"));
      leaving.style.pointerEvents = "none";
      if (!immediate && motionAllowed()) {
        leaving.animate([{ opacity: 1, transform: "scale(1)" }, { opacity: 0, transform: "scale(.97) translateY(-4px)" }],
          { duration: 140, easing: "ease-in" }).finished.then(() => leaving.remove(), () => leaving.remove());
      } else leaving.remove();
    }
    function choose(index) {
      if (select.options[index]?.disabled) return;
      const changed = select.selectedIndex !== index;
      select.selectedIndex = index;
      sync();
      close();
      if (changed) {
        select.dispatchEvent(new Event("change", { bubbles: true }));
        // The week control rebuilds the page, so restore its replacement's focus.
        document.getElementById(trigger.id)?.focus({ preventScroll: true });
      }
    }
    function open() {
      if (menu || trigger.disabled) return;
      opened?.close(true);
      menu = document.createElement("div");
      menu.id = `${select.id}-options`;
      menu.className = "select-menu";
      menu.setAttribute("role", "listbox");
      menu.setAttribute("aria-labelledby", trigger.getAttribute("aria-labelledby"));
      menu.setAttribute("popover", "manual");
      [...select.options].forEach((option, index) => {
        const item = document.createElement("div");
        item.className = "select-option";
        item.id = `${select.id}-option-${index}`;
        item.setAttribute("role", "option");
        item.setAttribute("aria-selected", String(index === select.selectedIndex));
        item.setAttribute("aria-disabled", String(option.disabled));
        item.textContent = option.textContent;
        item.addEventListener("mousedown", (event) => event.preventDefault());
        item.addEventListener("click", () => choose(index));
        menu.append(item);
      });
      document.body.append(menu);
      menu.showPopover?.();
      trigger.setAttribute("aria-controls", menu.id);
      trigger.setAttribute("aria-expanded", "true");
      field.classList.add("is-open");
      opened = { trigger, close, position, contains: (node) => field.contains(node) || menu?.contains(node) };
      position();
      highlight(select.selectedIndex);
      if (motionAllowed()) menu.animate([
        { opacity: 0, transform: "scale(.97) translateY(-6px)" },
        { opacity: 1, transform: "scale(1) translateY(0)" },
      ], { duration: 220, easing: "cubic-bezier(.2,.65,.3,1)" });
    }
    trigger.addEventListener("click", () => menu ? close() : open());
    trigger.addEventListener("blur", (event) => {
      if (!menu?.contains(event.relatedTarget)) close();
    });
    trigger.addEventListener("keydown", (event) => {
      if (event.key === "Tab") return close();
      if (event.key === "Escape") {
        if (menu) { event.preventDefault(); event.stopPropagation(); close(); }
        return;
      }
      if (["ArrowDown", "ArrowUp", "Home", "End", "Enter", " "].includes(event.key)) {
        event.preventDefault();
        if (!menu) return open();
        if (event.key === "Enter" || event.key === " ") return choose(active);
        const next = event.key === "Home" ? 0 : event.key === "End" ? select.length - 1 : active + (event.key === "ArrowDown" ? 1 : -1);
        highlight(next);
      } else if (event.key.length === 1 && !event.ctrlKey && !event.metaKey && !event.altKey) {
        event.preventDefault();
        const now = performance.now();
        typeahead = now - typedAt > 700 ? event.key : typeahead + event.key;
        typedAt = now;
        open();
        const index = [...select.options].findIndex((option) => option.textContent.trim().toLowerCase().startsWith(typeahead.toLowerCase()));
        if (index >= 0) highlight(index);
      }
    });
  });
}
