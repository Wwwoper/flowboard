(() => {
  "use strict";

  const SELECTOR = "#project-filter, #tag-filter, [data-column-filter], [data-column-sort], #task-status, #task-type, #task-project";
  const instances = new Map();
  let nextId = 1;
  let openInstance = null;

  function labelFor(select) {
    return select.getAttribute("aria-label")
      || select.closest("label")?.querySelector(".visually-hidden")?.textContent.trim()
      || select.labels?.[0]?.textContent.trim()
      || "Выбрать значение";
  }

  function selectedOption(select) {
    return select.selectedOptions?.[0] || select.options[select.selectedIndex] || null;
  }

  function availableOptions(instance) {
    return Array.from(instance.menu.querySelectorAll("[role=option]:not(:disabled)"));
  }

  function close(instance, restoreFocus = false) {
    if (!instance) return;
    instance.menu.hidden = true;
    instance.menu.classList.remove("opens-up", "align-right");
    instance.trigger.setAttribute("aria-expanded", "false");
    instance.wrapper.classList.remove("is-open");
    if (openInstance === instance) openInstance = null;
    instance.trigger.removeAttribute("aria-activedescendant");
    if (restoreFocus) instance.trigger.focus();
  }

  function closeAll(except = null) {
    instances.forEach((instance) => {
      if (instance !== except) close(instance);
    });
  }

  function syncValue(instance) {
    const selected = selectedOption(instance.select);
    const valueLabel = selected?.textContent.trim() || "Выбрать значение";
    if (instance.valueLabel.textContent !== valueLabel) instance.valueLabel.textContent = valueLabel;
    instance.trigger.setAttribute("aria-label", `${instance.label}: ${valueLabel}`);
    instance.trigger.setAttribute("aria-valuetext", valueLabel);
    instance.trigger.disabled = instance.select.disabled;
    instance.menu.querySelectorAll("[role=option]").forEach((item) => {
      const isSelected = item.dataset.value === instance.select.value;
      item.setAttribute("aria-selected", String(isSelected));
      item.classList.toggle("is-selected", isSelected);
    });
    if (instance.select.id === "task-type") {
      instance.wrapper.classList.remove("task-type-bug", "task-type-feature", "task-type-docs", "task-type-refactor");
      if (["bug", "feature", "docs", "refactor"].includes(instance.select.value)) {
        instance.wrapper.classList.add(`task-type-${instance.select.value}`);
      }
    }
  }

  function renderOptions(instance) {
    instance.menu.replaceChildren();
    Array.from(instance.select.options).forEach((option) => {
      if (option.hidden) return;
      const item = document.createElement("button");
      item.type = "button";
      item.className = "theme-select-option";
      if (instance.select.id === "task-type" && ["bug", "feature", "docs", "refactor"].includes(option.value)) {
        item.classList.add(`task-type-${option.value}`);
      }
      item.id = `${instance.menu.id}-option-${instance.menu.children.length}`;
      item.setAttribute("role", "option");
      item.setAttribute("aria-selected", String(option.value === instance.select.value));
      item.tabIndex = -1;
      item.disabled = option.disabled;
      item.dataset.value = option.value;
      item.textContent = option.textContent.trim();
      item.addEventListener("click", () => {
        if (option.disabled) return;
        instance.select.value = option.value;
        instance.select.dispatchEvent(new Event("change", { bubbles: true }));
        syncValue(instance);
        close(instance, true);
      });
      instance.menu.appendChild(item);
    });
    syncValue(instance);
    if (openInstance === instance && !instance.menu.hidden) {
      const items = availableOptions(instance);
      const selectedIndex = items.findIndex((item) => item.dataset.value === instance.select.value);
      setActiveOption(instance, selectedIndex >= 0 ? selectedIndex : 0);
    }
  }

  function setActiveOption(instance, index) {
    const items = availableOptions(instance);
    if (!items.length) {
      instance.trigger.removeAttribute("aria-activedescendant");
      return;
    }
    const safeIndex = Math.max(0, Math.min(index, items.length - 1));
    items.forEach((item, itemIndex) => item.classList.toggle("is-active", itemIndex === safeIndex));
    instance.trigger.setAttribute("aria-activedescendant", items[safeIndex].id);
    instance.activeValue = items[safeIndex].dataset.value;
    items[safeIndex].scrollIntoView?.({ block: "nearest" });
  }

  function moveActiveOption(instance, step) {
    const items = availableOptions(instance);
    if (!items.length) return;
    const current = items.findIndex((item) => item.classList.contains("is-active"));
    const start = current < 0 ? 0 : current;
    setActiveOption(instance, (start + step + items.length) % items.length);
  }

  function chooseActiveOption(instance) {
    const active = instance.menu.querySelector('[role="option"].is-active:not(:disabled)');
    if (active) active.click();
  }

  function open(instance, direction = "first") {
    if (instance.select.disabled) return;
    closeAll(instance);
    renderOptions(instance);
    instance.menu.hidden = false;
    instance.trigger.setAttribute("aria-expanded", "true");
    instance.wrapper.classList.add("is-open");
    openInstance = instance;

    const rect = instance.trigger.getBoundingClientRect();
    const margin = 8;
    const availableWidth = Math.max(160, window.innerWidth - margin * 2);
    instance.menu.style.minWidth = `${Math.min(Math.max(rect.width, 190), availableWidth)}px`;
    instance.menu.style.maxWidth = `${availableWidth}px`;
    instance.menu.classList.remove("opens-up", "align-right");
    instance.menu.style.left = `${Math.max(margin, Math.min(rect.left, window.innerWidth - margin - 190))}px`;
    instance.menu.style.top = `${Math.min(rect.bottom + 5, Math.max(margin, window.innerHeight - 48))}px`;

    const menuRect = instance.menu.getBoundingClientRect();
    if (menuRect.right > window.innerWidth - margin) {
      instance.menu.style.left = `${Math.max(margin, window.innerWidth - menuRect.width - margin)}px`;
    }
    if (menuRect.bottom > window.innerHeight - margin) {
      instance.menu.classList.add("opens-up");
      instance.menu.style.top = `${Math.max(margin, rect.top - menuRect.height - 5)}px`;
    }

    const items = availableOptions(instance);
    const selectedIndex = items.findIndex((item) => item.dataset.value === instance.select.value);
    setActiveOption(instance, direction === "last" ? items.length - 1 : (selectedIndex >= 0 ? selectedIndex : 0));
  }

  function enhance(select) {
    if (select.dataset.themeSelectEnhanced === "true") return;
    select.dataset.themeSelectEnhanced = "true";

    const wrapper = document.createElement("span");
    wrapper.className = "theme-select";
    select.before(wrapper);
    wrapper.appendChild(select);
    select.classList.add("theme-select-native");
    select.tabIndex = -1;
    select.setAttribute("aria-hidden", "true");

    const trigger = document.createElement("button");
    trigger.type = "button";
    trigger.className = "theme-select-trigger";
    trigger.setAttribute("aria-haspopup", "listbox");
    trigger.setAttribute("aria-expanded", "false");
    trigger.setAttribute("aria-label", labelFor(select));
    const label = document.createElement("span");
    label.className = "theme-select-value";
    const chevron = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    chevron.setAttribute("viewBox", "0 0 16 16");
    chevron.setAttribute("width", "14");
    chevron.setAttribute("height", "14");
    chevron.setAttribute("aria-hidden", "true");
    chevron.classList.add("theme-select-chevron");
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("d", "m4 6 4 4 4-4");
    path.setAttribute("fill", "none");
    path.setAttribute("stroke", "currentColor");
    path.setAttribute("stroke-width", "1.6");
    path.setAttribute("stroke-linecap", "round");
    path.setAttribute("stroke-linejoin", "round");
    chevron.appendChild(path);
    trigger.append(label, chevron);
    wrapper.appendChild(trigger);

    const menu = document.createElement("div");
    menu.className = "theme-select-menu";
    menu.id = `theme-select-menu-${nextId++}`;
    menu.setAttribute("role", "listbox");
    menu.setAttribute("aria-label", labelFor(select));
    menu.hidden = true;
    document.body.appendChild(menu);
    trigger.setAttribute("aria-controls", menu.id);

    const instance = { select, wrapper, trigger, valueLabel: label, menu, label: labelFor(select) };
    instances.set(select, instance);
    trigger.addEventListener("click", () => {
      if (openInstance === instance && !menu.hidden) close(instance);
      else open(instance);
    });
    trigger.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && !menu.hidden) {
        event.preventDefault();
        close(instance);
      } else if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        event.preventDefault();
        if (menu.hidden) open(instance, event.key === "ArrowUp" ? "last" : "first");
        else moveActiveOption(instance, event.key === "ArrowUp" ? -1 : 1);
      } else if (["Enter", " "].includes(event.key)) {
        event.preventDefault();
        if (menu.hidden) open(instance);
        else chooseActiveOption(instance);
      } else if (event.key === "Home" && !menu.hidden) {
        event.preventDefault();
        setActiveOption(instance, 0);
      } else if (event.key === "End" && !menu.hidden) {
        event.preventDefault();
        setActiveOption(instance, availableOptions(instance).length - 1);
      }
    });
    menu.addEventListener("mousedown", (event) => {
      if (event.target.closest('[role="option"]')) event.preventDefault();
    });
    select.addEventListener("change", () => syncValue(instance));
    const observer = new MutationObserver(() => renderOptions(instance));
    observer.observe(select, { childList: true, subtree: true, attributes: true, attributeFilter: ["disabled", "hidden", "label", "value"] });
    instance.observer = observer;
    renderOptions(instance);
  }

  document.querySelectorAll(SELECTOR).forEach(enhance);

  document.addEventListener("click", (event) => {
    if (event.target.closest(".theme-select") || event.target.closest(".theme-select-menu")) return;
    closeAll();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && openInstance) close(openInstance, true);
  });
  document.addEventListener("scroll", (event) => {
    if (openInstance && !event.target.closest?.(".theme-select-menu")) close(openInstance);
  }, true);
  window.addEventListener("resize", () => closeAll());

  // App code updates option lists and selected values programmatically; mirror those updates.
  const documentObserver = new MutationObserver(() => {
    instances.forEach(syncValue);
  });
  documentObserver.observe(document.body, { childList: true, subtree: true });
})();
