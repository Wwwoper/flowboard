/*
 * Small native HTML5 drag-and-drop adapter used by Flowboard.
 * It exposes the Sortable.create/onEnd contract needed by this UI and deliberately
 * has no runtime CDN dependency. The official SortableJS build can replace this file.
 */
(function () {
  "use strict";

  class NativeSortable {
    constructor(element, options) {
      this.element = element;
      this.options = options || {};
      this.dragged = null;
      this.origin = null;
      this.oldIndex = -1;
      this.onDragStart = this.onDragStart.bind(this);
      this.onDragOver = this.onDragOver.bind(this);
      this.onDrop = this.onDrop.bind(this);
      this.onDragEnd = this.onDragEnd.bind(this);
      element.addEventListener("dragstart", this.onDragStart);
      element.addEventListener("dragover", this.onDragOver);
      element.addEventListener("drop", this.onDrop);
      element.addEventListener("dragend", this.onDragEnd);
    }

    indexOf(item, container) {
      return Array.from(container.querySelectorAll(this.options.draggable || ".task-card")).indexOf(item);
    }

    onDragStart(event) {
      const item = event.target.closest(this.options.draggable || ".task-card");
      if (!item || !this.element.contains(item)) return;
      if (event.target.closest("button, a, input, select, textarea")) {
        event.preventDefault();
        return;
      }
      this.dragged = item;
      this.origin = this.element;
      this.oldIndex = this.indexOf(item, this.element);
      if (typeof this.options.onStart === "function") {
        this.options.onStart({ item, from: this.element, oldIndex: this.oldIndex });
      }
      window.__flowboardDragging = item;
      item.classList.add("dragging");
      event.dataTransfer.effectAllowed = "move";
      try { event.dataTransfer.setData("text/plain", item.dataset.taskId || ""); } catch (_) { /* Safari fallback */ }
    }

    onDragOver(event) {
      const item = window.__flowboardDragging;
      if (!item) return;
      const targetList = event.target.closest(".task-list");
      if (!targetList || !document.body.contains(targetList)) return;
      event.preventDefault();
      event.dataTransfer.dropEffect = "move";
      document.querySelectorAll(".board-column.is-drop-target").forEach((node) => node.classList.remove("is-drop-target"));
      const column = targetList.closest(".board-column");
      if (column) column.classList.add("is-drop-target");

      const siblings = Array.from(targetList.querySelectorAll(this.options.draggable || ".task-card"))
        .filter((node) => node !== item);
      let afterNode = null;
      for (const sibling of siblings) {
        const rect = sibling.getBoundingClientRect();
        if (event.clientY < rect.top + rect.height / 2) {
          afterNode = sibling;
          break;
        }
      }
      if (afterNode) targetList.insertBefore(item, afterNode);
      else targetList.appendChild(item);
    }

    onDrop(event) {
      if (!window.__flowboardDragging) return;
      const targetList = event.target.closest(".task-list");
      if (!targetList) return;
      event.preventDefault();
      const item = window.__flowboardDragging;
      const from = this.origin;
      const to = targetList;
      const newIndex = this.indexOf(item, to);
      const oldIndex = this.oldIndex;
      const callback = this.options.onEnd;
      this.clearDragState();
      if (typeof callback === "function") callback({ item, from, to, oldIndex, newIndex });
    }

    onDragEnd() {
      this.clearDragState();
    }

    clearDragState() {
      if (window.__flowboardDragging) window.__flowboardDragging.classList.remove("dragging");
      window.__flowboardDragging = null;
      document.querySelectorAll(".board-column.is-drop-target").forEach((node) => node.classList.remove("is-drop-target"));
      this.dragged = null;
      this.origin = null;
      this.oldIndex = -1;
    }

    destroy() {
      this.element.removeEventListener("dragstart", this.onDragStart);
      this.element.removeEventListener("dragover", this.onDragOver);
      this.element.removeEventListener("drop", this.onDrop);
      this.element.removeEventListener("dragend", this.onDragEnd);
    }
  }

  window.Sortable = { create: (element, options) => new NativeSortable(element, options) };
})();
