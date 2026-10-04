/*
 * HomeServer Theme for CasaOS — v32
 * Made by jw-notes — https://github.com/jw-notes
 *
 * Adds theme/navigation controls, stores browser preferences, and tags
 * dynamically rendered CasaOS panels for styling. Also renames the page
 * and terminal title to HomeServer and removes promotional UI.
 * Load once alongside casaos-dark.css.
 *
 * Compatibility: targets CasaOS component classes and English UI labels.
 * Future CasaOS releases or other interface languages may require changes.
 * Unofficial community theme; not affiliated with CasaOS or IceWhale.
 */

(() => {
  "use strict";

  const BRAND = "HomeServer";
  const THEME_KEY = "homeserver-theme";
  const NAV_KEY = "homeserver-nav-collapsed";

  function removeCasaBranding() {
    document.querySelectorAll(".brand-bar, .contact-bar").forEach((el) => {
      el.remove();
    });
  }

  function getTheme() {
    return localStorage.getItem(THEME_KEY) === "light"
      ? "light"
      : "dark";
  }

  function setTheme(theme) {
    document.body.classList.toggle("hs-dark", theme === "dark");
    document.body.classList.toggle("hs-light", theme === "light");
    localStorage.setItem(THEME_KEY, theme);

    const button = document.getElementById("hs-theme-toggle");

    if (button) {
      const dark = theme === "dark";
      button.textContent = dark ? "☀" : "☾";
      button.title = dark
        ? "Switch to light mode"
        : "Switch to dark mode";
      button.setAttribute(
        "aria-label",
        dark ? "Switch to light mode" : "Switch to dark mode"
      );
    }
  }

  function setNavCollapsed(collapsed) {
    document.body.classList.toggle("hs-nav-collapsed", collapsed);
    localStorage.setItem(NAV_KEY, collapsed ? "1" : "0");

    const button = document.getElementById("hs-nav-toggle");

    if (button) {
      button.title = collapsed
        ? "Open top bar"
        : "Close top bar";
      button.setAttribute(
        "aria-label",
        collapsed ? "Open top bar" : "Close top bar"
      );
      button.setAttribute(
        "aria-expanded",
        collapsed ? "false" : "true"
      );
    }
  }

  function createToolbar(navbar) {
    if (!navbar || document.getElementById("hs-toolbar")) {
      return;
    }

    const toolbar = document.createElement("div");
    toolbar.id = "hs-toolbar";

    const navButton = document.createElement("button");
    navButton.id = "hs-nav-toggle";
    navButton.className = "hs-toolbar-button";
    navButton.type = "button";
    navButton.setAttribute("aria-label", "Toggle top bar");
    navButton.innerHTML =
      '<span class="hs-hamburger" aria-hidden="true"><span></span></span>';

    navButton.addEventListener("click", () => {
      setNavCollapsed(
        !document.body.classList.contains("hs-nav-collapsed")
      );
    });

    const themeButton = document.createElement("button");
    themeButton.id = "hs-theme-toggle";
    themeButton.className = "hs-toolbar-button";
    themeButton.type = "button";

    themeButton.addEventListener("click", () => {
      setTheme(
        document.body.classList.contains("hs-dark")
          ? "light"
          : "dark"
      );
    });

    toolbar.appendChild(navButton);
    toolbar.appendChild(themeButton);

    /*
     * toolbar is inserted INTO CasaOS' real top bar.
     * Because the top bar itself is left-aligned, all of the
     * original controls move together with the hamburger.
     */
    navbar.prepend(toolbar);

    setTheme(getTheme());
    setNavCollapsed(localStorage.getItem(NAV_KEY) === "1");
  }

  function clearRuntimeTags() {
    document.querySelectorAll(
      ".hs-settings-panel, .hs-terminal-shell"
    ).forEach((el) => {
      el.classList.remove(
        "hs-settings-panel",
        "hs-terminal-shell"
      );
    });
  }

  function tagSettingsPanel() {
    const candidates = document.querySelectorAll(
      ".dropdown-content, .modal-card, .modal-content, .animation-content, .box, .card"
    );

    candidates.forEach((el) => {
      const text = (el.innerText || "")
        .replace(/\s+/g, " ")
        .trim();

      /*
       * Dashboard Settings contains these controls in the targeted CasaOS interface.
       * Requiring two terms avoids tagging unrelated cards.
       */
      if (
        text.includes("Show Search Bar") &&
        (
          text.includes("Search Engine") ||
          text.includes("Language")
        )
      ) {
        el.classList.add("hs-settings-panel");
      }
    });
  }

  function tagTerminalShell() {
    /*
     * Find distinctive text inside Terminal & Logs.
     * The targeted interface exposes "Terminal & Logs" plus the SSH
     * username/port help text.
     */
    const all = document.querySelectorAll("body *");

    all.forEach((el) => {
      if (el.children.length > 12) return;

      const text = (el.innerText || "")
        .replace(/\s+/g, " ")
        .trim();

      const looksLikeTerminal =
        text.includes("Terminal & Logs") ||
        text.includes(
          "Please check if the username and port are correct"
        ) ||
        (
          text.includes("Terminal") &&
          text.includes("Logs") &&
          text.includes("Connect")
        );

      if (!looksLikeTerminal) return;

      /*
       * Mark the matched element and several ancestors.
       * The persistent white box is commonly one wrapper ABOVE
       * the visible login form, so multiple ancestor levels are tagged.
       */
      let node = el;

      for (let level = 0; level < 5 && node; level++) {
        if (
          node === document.body ||
          node.id === "app"
        ) {
          break;
        }

        node.classList.add("hs-terminal-shell");
        node = node.parentElement;
      }
    });
  }

  function tagDynamicPanels() {
    clearRuntimeTags();
    tagSettingsPanel();
    tagTerminalShell();
  }


  function tagAccountAndLogout() {
    document.querySelectorAll(".dropdown-content, .modal-card, .modal-content").forEach((panel) => {
      const text = (panel.innerText || "").replace(/\s+/g, " ").trim();

      if (text.includes("Logout")) {
        panel.classList.add("hs-account-panel");

        panel.querySelectorAll("a, button, .dropdown-item, [role='button']").forEach((el) => {
          if ((el.innerText || "").trim() === "Logout") {
            el.classList.add("hs-logout");
          }
        });
      }
    });
  }

  function tagSettingsInteractions() {
    document.querySelectorAll(".hs-settings-panel").forEach((panel) => {
      panel.querySelectorAll(
        "a, button, label, .field, .control, .switch, .checkbox, .select, select, .dropdown-item, [role='button'], [tabindex]"
      ).forEach((el) => {
        el.classList.add("hs-interactive-setting");
      });
    });
  }

  function tagTerminalDetails() {
    document.querySelectorAll(".hs-terminal-shell").forEach((shell) => {
      /*
       * Tag probable login form/card from inputs + Connect text.
       * Do not paint the whole shell; only the smallest useful wrapper.
       */
      shell.querySelectorAll("form, .box, .card, .modal-card-body, .field").forEach((el) => {
        const text = (el.innerText || "").replace(/\s+/g, " ").trim();
        const hasInput = !!el.querySelector("input, .input, select");
        if (
          hasInput &&
          (
            text.includes("Connect") ||
            text.includes("username") ||
            text.includes("Username") ||
            text.includes("Port")
          )
        ) {
          el.classList.add("hs-terminal-login-card");
        }
      });

      /*
       * Tag terminal/log display areas so they can remain transparent.
       */
      shell.querySelectorAll("iframe, pre, code, .terminal, .logs, [class*='terminal'], [class*='logs']").forEach((el) => {
        el.classList.add("hs-terminal-content");
      });
    });
  }


  function clearUnsavedTerminalLoginDefaults() {
    document.querySelectorAll("#terminal input").forEach((input) => {
      if (input.dataset.hsTerminalChecked === "1") return;
      input.dataset.hsTerminalChecked = "1";

      const key = ((input.name || "") + " " + (input.id || "") + " " + (input.placeholder || "")).toLowerCase();
      const isLoginField =
        key.includes("user") ||
        key.includes("host") ||
        key.includes("port") ||
        key.includes("password");

      if (!isLoginField) return;

      /*
       * Reset detected terminal login fields on their first processing pass.
       * Browser autofill may populate them again afterwards.
       * SSH default port is 22.
       */
      if (
        key.includes("port") ||
        input.type === "number"
      ) {
        input.value = "22";
      } else {
        input.value = "";
      }

      input.dispatchEvent(
        new Event("input", { bubbles: true })
      );
    });
  }

  function installPressedStateGuard() {
    if (document.documentElement.dataset.hsPressedGuard === "1") return;
    document.documentElement.dataset.hsPressedGuard = "1";

    document.addEventListener("pointerdown", (event) => {
      const target = event.target.closest(
        ".hs-settings-panel .hs-interactive-setting, .dropdown-content .dropdown-item"
      );
      if (!target) return;

      target.classList.add("hs-pressed");

      const clear = () => {
        target.classList.remove("hs-pressed");
        window.removeEventListener("pointerup", clear, true);
        window.removeEventListener("pointercancel", clear, true);
      };

      window.addEventListener("pointerup", clear, true);
      window.addEventListener("pointercancel", clear, true);
    }, true);
  }


  function buildCustomSettingsSelects() {
    /*
     * Upgrade the REAL CasaOS TopBar selects directly.
     * Search Engine and Language both use .set-select.
     */
    const selects = document.querySelectorAll(
      ".navbar.top-bar .set-select select, .hs-settings-panel select"
    );

    selects.forEach((select) => {
      if (select.dataset.hsCustomSelect === "1") return;

      select.dataset.hsCustomSelect = "1";

      const originalParent = select.parentElement;
      if (!originalParent) return;

      const wrapper = document.createElement("div");
      wrapper.className = "hs-custom-select";

      originalParent.insertBefore(wrapper, select);
      wrapper.appendChild(select);
      select.classList.add("hs-custom-select-native");

      const button = document.createElement("button");
      button.type = "button";
      button.className = "hs-custom-select-button";

      const menu = document.createElement("div");
      menu.className = "hs-custom-select-menu";
      menu.hidden = true;

      function syncButton() {
        const option = select.options[select.selectedIndex];
        button.textContent = option ? option.textContent.trim() : "";
      }

      function rebuildMenu() {
        menu.innerHTML = "";

        Array.from(select.options).forEach((option) => {
          const item = document.createElement("button");
          item.type = "button";
          item.className = "hs-custom-select-option";
          item.textContent = option.textContent.trim();

          if (option.value === select.value) {
            item.classList.add("is-selected");
          }

          item.addEventListener("click", (event) => {
            event.preventDefault();
            event.stopPropagation();

            select.value = option.value;

            select.dispatchEvent(
              new Event("input", { bubbles: true })
            );
            select.dispatchEvent(
              new Event("change", { bubbles: true })
            );

            syncButton();
            rebuildMenu();
            menu.hidden = true;
          });

          menu.appendChild(item);
        });
      }

      button.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();

        document
          .querySelectorAll(".hs-custom-select-menu")
          .forEach((other) => {
            if (other !== menu) other.hidden = true;
          });

        rebuildMenu();
        menu.hidden = !menu.hidden;
      });

      select.addEventListener("change", () => {
        syncButton();
        rebuildMenu();
      });

      wrapper.appendChild(button);
      wrapper.appendChild(menu);

      syncButton();
      rebuildMenu();
    });
  }

  function installCustomSelectCloser() {
    if (document.documentElement.dataset.hsSelectCloser === "1") return;
    document.documentElement.dataset.hsSelectCloser = "1";

    document.addEventListener("click", () => {
      document
        .querySelectorAll(".hs-custom-select-menu")
        .forEach((menu) => {
          menu.hidden = true;
        });
    });
  }


  function tagFloatingCards() {
    document.querySelectorAll(
      ".tooltip-content, .popper, [role='tooltip'], .dropdown-content, .notification, .message"
    ).forEach((el) => {
      const style = window.getComputedStyle(el);
      const positioned =
        style.position === "absolute" ||
        style.position === "fixed";

      if (positioned) {
        el.classList.add("hs-floating-card");
      }
    });
  }

  function tagStorePanels() {
    document.querySelectorAll(
      ".modal-card, .modal-content, .animation-content, .card, .box"
    ).forEach((el) => {
      const text = (el.innerText || "")
        .replace(/\s+/g, " ")
        .trim();

      const looksLikeStore =
        text.includes("App Store") ||
        text.includes("Install") && (
          text.includes("Description") ||
          text.includes("Version") ||
          text.includes("Developer")
        );

      if (!looksLikeStore) return;

      el.classList.add("hs-store-panel");

      el.querySelectorAll(
        ".content, .description, [class*='description'], .card, .box, .notification, .message"
      ).forEach((child) => {
        child.classList.add("hs-description-card");
      });
    });
  }





  function renameTerminalPanelTitle() {
    const BRAND = "HomeServer";

    const panels = document.querySelectorAll(
      ".terminal-modal, .modal:has(#terminal), .modal:has(#logs)"
    );

    panels.forEach((panel) => {
      const title =
        panel.querySelector(".modal-card-head .title") ||
        panel.querySelector(".modal-card-head h1") ||
        panel.querySelector(".modal-card-head h2") ||
        panel.querySelector(".modal-card-head h3");

      if (title && title.textContent.trim() === "CasaOS") {
        title.textContent = BRAND;
      }
    });
  }

  function apply() {
    document.title = BRAND;

    removeCasaBranding();

    const navbar =
      document.querySelector(".navbar.top-bar") ||
      document.querySelector(".top-bar.navbar");

    if (navbar) {
      createToolbar(navbar);
    }

    tagDynamicPanels();
    tagAccountAndLogout();
    tagSettingsInteractions();
    tagTerminalDetails();
    clearUnsavedTerminalLoginDefaults();
    buildCustomSettingsSelects();
    tagFloatingCards();
    tagStorePanels();
    installCustomSelectCloser();
    installPressedStateGuard();
    renameTerminalPanelTitle();

    setTheme(getTheme());
    setNavCollapsed(localStorage.getItem(NAV_KEY) === "1");
  }

  function start() {
    setTheme(getTheme());
    setNavCollapsed(localStorage.getItem(NAV_KEY) === "1");
    apply();

    let queued = false;

    const observer = new MutationObserver(() => {
      if (queued) return;

      queued = true;

      requestAnimationFrame(() => {
        queued = false;
        apply();
      });
    });

    observer.observe(document.body, {
      childList: true,
      subtree: true
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener(
      "DOMContentLoaded",
      start,
      { once: true }
    );
  } else {
    start();
  }
})();
