import { setupNavigation } from "./motion.js";

function setTheme(theme) {
  document.documentElement.dataset.theme = theme;
  document.querySelector("#theme-toggle")?.setAttribute(
    "aria-label",
    theme === "dark" ? "Switch to light theme" : "Switch to dark theme",
  );
}

try {
  setTheme(
    localStorage.getItem("qo-theme") ||
      (matchMedia("(prefers-color-scheme:dark)").matches ? "dark" : "light"),
  );
} catch {
  setTheme("light");
}

document.querySelector("#theme-toggle")?.addEventListener("click", () => {
  const theme =
    document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  setTheme(theme);
  try {
    localStorage.setItem("qo-theme", theme);
  } catch {}
});

const current = document.body.dataset.nav;
document.querySelector(`[data-page="${current}"]`)?.setAttribute("aria-current", "page");
setupNavigation();
