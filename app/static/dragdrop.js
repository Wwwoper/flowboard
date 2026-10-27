/*
 * Small native HTML5 drag-and-drop adapter used by Flowboard.
 * It exposes the Sortable.create/onEnd contract needed by this UI and deliberately
 * has no runtime CDN dependency. The official SortableJS build can replace this file.
 */
(function () {
  "use strict";

  // The draggable card can be moved in the DOM while a native drag is active.
  // Route board-wide drag events by pointer coordinates instead of event.target,
  // which may still refer to the moving card in its previous column.
  const sortablesByList = new WeakMap();
  const boardListeners = new WeakMap();
  let activeSortable = null;

  function findColumnAtPoint(board, clientX, clientY) {
    for (const column of board.querySelectorAll(".board-column")) {
      const rect = column.getBoundingClientRect();
      if (clientX < rect.left || clientX > rect.right || clientY < rect.top || clientY > rect.bottom) continue;
      const list = column.querySelector(".task-list");
      const sortable = list ? sortablesByList.get(list) : null;
      return list && sortable ? { column, list, sortable } : null;
    }
    return null;
  }

  function installBoardDragRouter(board) {
    if (!board || boardListeners.has(board)) return;
    const onDragOver = (event) => {
      if (!window.__flowboardDragging) return;
      const destination = findColumnAtPoint(board, event.clientX, event.clientY);
      if (!destination) return;
      destination.sortable.onDragOver(event, destination.column, destination.list);
    };
    const onDrop = (event) => {
      if (!window.__flowboardDragging) return;
      const destination = findColumnAtPoint(board, event.clientX, event.clientY);
      if (!destination) return;
      destination.sortable.onDrop(event, destination.column, destination.list);
    };
    board.addEventListener("dragover", onDragOver);
    board.addEventListener("drop", onDrop);
    boardListeners.set(board, { onDragOver, onDrop });
  }

  class NativeSortable {
    constructor(element, options) {
      this.element = element;
      this.options = options || {};
      this.dragged = null;
      this.origin = null;
      this.oldIndex = -1;
      this.board = element.closest(".board");
      this.onDragStart = this.onDragStart.bind(this);
      this.onDragEnd = this.onDragEnd.bind(this);
      sortablesByList.set(element, this);
      element.addEventListener("dragstart", this.onDragStart);
      element.addEventListener("dragend", this.onDragEnd);
      installBoardDragRouter(this.board);
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
      activeSortable = this;
      // The drop event is handled by the destination list's adapter instance.
      // Keep the source list outside either instance so cross-column drops retain it.
      window.__flowboardDragOrigin = this.element;
      this.oldIndex = this.indexOf(item, this.element);
      if (typeof this.options.onStart === "function") {
        this.options.onStart({ item, from: this.element, oldIndex: this.oldIndex });
      }
      window.__flowboardDragging = item;
      item.classList.add("dragging");
      event.dataTransfer.effectAllowed = "move";
      try { event.dataTransfer.setData("text/plain", item.dataset.taskId || ""); } catch (_) { /* Safari fallback */ }
    }

    onDragOver(event, targetColumn, targetList) {
      const item = window.__flowboardDragging;
      if (!item || !targetColumn || !targetList) return;
      if (!targetColumn.contains(targetList) || !document.body.contains(targetList)) return;
      event.preventDefault();
      if (event.dataTransfer) event.dataTransfer.dropEffect = "move";
      document.querySelectorAll(".board-column.is-drop-target").forEach((node) => node.classList.remove("is-drop-target"));
      targetColumn.classList.add("is-drop-target");

      // Scroll only the destination list when the pointer is near its edges.
      const listRect = targetList.getBoundingClientRect();
      const pointerWithinList = event.clientY >= listRect.top && event.clientY <= listRect.bottom;
      if (pointerWithinList && targetList.scrollHeight > targetList.clientHeight + 1) {
        const edgeThreshold = Math.min(56, Math.max(24, targetList.clientHeight * 0.12));
        const distanceFromTop = event.clientY - listRect.top;
        const distanceFromBottom = listRect.bottom - event.clientY;
        if (distanceFromTop < edgeThreshold && targetList.scrollTop > 0) {
          const intensity = Math.min(1, (edgeThreshold - distanceFromTop) / edgeThreshold);
          targetList.scrollTop -= Math.max(4, Math.round(14 * intensity));
        } else if (
          distanceFromBottom < edgeThreshold
          && targetList.scrollTop + targetList.clientHeight < targetList.scrollHeight - 1
        ) {
          const intensity = Math.min(1, (edgeThreshold - distanceFromBottom) / edgeThreshold);
          targetList.scrollTop += Math.max(4, Math.round(14 * intensity));
        }
      }

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

    onDrop(event, targetColumn, targetList) {
      if (!window.__flowboardDragging || !targetColumn || !targetList) return;
      if (!targetColumn.contains(targetList) || !document.body.contains(targetList)) return;
      event.preventDefault();
      const item = window.__flowboardDragging;
      const from = window.__flowboardDragOrigin || activeSortable?.element || this.origin;
      const to = targetList;
      const newIndex = this.indexOf(item, to);
      // oldIndex belongs to the source adapter, not the destination adapter.
      const oldIndex = activeSortable ? activeSortable.oldIndex : -1;
      const callback = this.options.onEnd;
      this.clearDragState();
      if (typeof callback === "function") callback({ item, from, to, oldIndex, newIndex });
    }

    onDragEnd() {
      this.clearDragState();
    }

    clearDragState() {
      const item = window.__flowboardDragging || this.dragged;
      if (item) item.classList.remove("dragging");
      window.__flowboardDragging = null;
      window.__flowboardDragOrigin = null;
      document.querySelectorAll(".board-column.is-drop-target").forEach((node) => node.classList.remove("is-drop-target"));
      if (activeSortable) {
        activeSortable.dragged = null;
        activeSortable.origin = null;
        activeSortable.oldIndex = -1;
      }
      this.dragged = null;
      this.origin = null;
      this.oldIndex = -1;
      activeSortable = null;
    }

    destroy() {
      this.element.removeEventListener("dragstart", this.onDragStart);
      this.element.removeEventListener("dragend", this.onDragEnd);
      sortablesByList.delete(this.element);
    }
  }

  window.Sortable = { create: (element, options) => new NativeSortable(element, options) };
})();
