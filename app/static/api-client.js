(() => {
  "use strict";

  const root = typeof window !== "undefined" ? window : globalThis;
  const SERVER_ERROR_MESSAGE = "На сервере произошла ошибка. Попробуйте ещё раз.";
  const NETWORK_ERROR_MESSAGE = "Не удалось связаться с сервером. Проверьте подключение и повторите попытку.";
  const INVALID_RESPONSE_MESSAGE = "Сервер вернул некорректный ответ. Попробуйте ещё раз.";
  const EMPTY_RESPONSE_MESSAGE = "Сервер вернул пустой ответ. Попробуйте ещё раз.";

  class ApiError extends Error {
    constructor(message, { status = null, kind = "api" } = {}) {
      super(message);
      this.name = "ApiError";
      this.status = status;
      this.kind = kind;
    }
  }

  function fallbackMessage(status) {
    if (status >= 500) return SERVER_ERROR_MESSAGE;
    if (status === 401) return "Срок действия сеанса истёк. Обновите страницу и повторите попытку.";
    if (status === 403) return "Недостаточно прав для выполнения операции.";
    if (status === 404) return "Запрошенные данные не найдены.";
    if (status === 409) return "Не удалось выполнить действие: данные могли измениться. Обновите страницу.";
    if (status === 413) return "Размер файла превышает допустимый предел.";
    if (status === 422) return "Проверьте введённые данные и попробуйте ещё раз.";
    if (status === 429) return "Слишком много запросов. Подождите немного и повторите попытку.";
    return "Не удалось выполнить запрос. Попробуйте ещё раз.";
  }

  function isSafeMessage(value) {
    return typeof value === "string"
      && value.trim().length > 0
      && value.length <= 500
      && !/(?:traceback|stack trace|internal server error|\bexception\b|\b(sqlite|sqlalchemy|operationalerror|integrityerror)\b|\bfile\s+["']|(?:^|\s)at\s+\S+\s*\()/i.test(value);
  }

  function messageFromPayload(payload, status) {
    if (status >= 500) return SERVER_ERROR_MESSAGE;
    const detail = payload && typeof payload === "object" && !Array.isArray(payload)
      ? (payload.detail ?? payload.message)
      : payload;
    if (Array.isArray(detail)) {
      const messages = detail
        .map((entry) => typeof entry === "string" ? entry : entry?.msg || entry?.message || "")
        .filter((message) => typeof message === "string" && message.trim());
      const combined = messages.join("; ");
      return isSafeMessage(combined) ? combined : fallbackMessage(status);
    }
    if (isSafeMessage(detail)) return detail.trim();
    return fallbackMessage(status);
  }

  async function readPayload(response) {
    let text;
    try {
      text = await response.text();
    } catch {
      throw new ApiError(INVALID_RESPONSE_MESSAGE, { status: response.status, kind: "invalid-response" });
    }
    if (!text.trim()) return { empty: true, data: null };

    const contentType = response.headers?.get?.("content-type") || "";
    const looksLikeJson = contentType.includes("application/json") || /^[\s]*[\[{]/.test(text);
    if (!looksLikeJson) return { empty: false, data: text };
    try {
      return { empty: false, data: JSON.parse(text) };
    } catch {
      return { empty: false, invalidJson: true, data: null };
    }
  }

  function createClient(fetchImpl) {
    const send = fetchImpl || ((...args) => root.fetch(...args));

    async function fetchResponse(url, options) {
      try {
        return await send(url, options);
      } catch (error) {
        if (error?.name === "AbortError") {
          throw new ApiError("Запрос отменён.", { kind: "aborted" });
        }
        throw new ApiError(NETWORK_ERROR_MESSAGE, { kind: "network" });
      }
    }

    function requestOptions(options = {}) {
      const request = {
        ...options,
        cache: "no-store",
        headers: { ...(options.headers || {}) },
      };
      const isFormData = typeof FormData !== "undefined" && request.body instanceof FormData;
      if (request.body && !isFormData && typeof request.body !== "string") {
        request.headers["Content-Type"] = "application/json";
        request.body = JSON.stringify(request.body);
      }
      return request;
    }

    async function request(url, options = {}) {
      const response = await fetchResponse(url, requestOptions(options));
      if (response.status === 204) return null;

      const payload = await readPayload(response);
      if (!response.ok) {
        throw new ApiError(messageFromPayload(payload.invalidJson ? null : payload.data, response.status), {
          status: response.status,
          kind: "http",
        });
      }
      if (payload.invalidJson) {
        throw new ApiError(INVALID_RESPONSE_MESSAGE, { status: response.status, kind: "invalid-response" });
      }
      if (payload.empty) {
        throw new ApiError(EMPTY_RESPONSE_MESSAGE, { status: response.status, kind: "empty-response" });
      }
      return payload.data;
    }

    async function requestBlob(url, options = {}) {
      const response = await fetchResponse(url, requestOptions(options));
      if (!response.ok) {
        const payload = await readPayload(response);
        throw new ApiError(messageFromPayload(payload.invalidJson ? null : payload.data, response.status), {
          status: response.status,
          kind: "http",
        });
      }
      if (response.status === 204) {
        throw new ApiError(EMPTY_RESPONSE_MESSAGE, { status: response.status, kind: "empty-response" });
      }
      try {
        return await response.blob();
      } catch {
        throw new ApiError(INVALID_RESPONSE_MESSAGE, { status: response.status, kind: "invalid-response" });
      }
    }

    return Object.freeze({ request, requestBlob });
  }

  const apiClient = Object.freeze({ ApiError, createClient });
  root.FlowboardApi = apiClient;
  if (typeof module !== "undefined" && module.exports) module.exports = apiClient;
})();
