const assert = require("node:assert/strict");
const { test } = require("node:test");
const { createClient } = require("../../app/static/api-client.js");

function response({ status = 200, body = "{}", contentType = "application/json", blob = null } = {}) {
  return {
    status,
    ok: status >= 200 && status < 300,
    headers: { get: (name) => name.toLowerCase() === "content-type" ? contentType : null },
    text: async () => body,
    blob: async () => blob ?? new Blob([body]),
  };
}

test("network failures become a safe, consistent API error", async () => {
  const client = createClient(async () => { throw new TypeError("Failed to fetch: private host details"); });
  await assert.rejects(client.request("/api/tasks"), (error) => {
    assert.equal(error.name, "ApiError");
    assert.equal(error.kind, "network");
    assert.match(error.message, /Проверьте подключение/);
    assert.doesNotMatch(error.message, /private host details/);
    return true;
  });
});

test("server errors never expose traceback or internal details", async () => {
  const client = createClient(async () => response({
    status: 500,
    body: JSON.stringify({ detail: "Traceback (most recent call last): /srv/app/main.py" }),
  }));
  await assert.rejects(client.request("/api/tasks"), (error) => {
    assert.equal(error.status, 500);
    assert.equal(error.message, "На сервере произошла ошибка. Попробуйте ещё раз.");
    assert.doesNotMatch(error.message, /Traceback|main\.py/);
    return true;
  });
});

test("validation details remain available to the user", async () => {
  const client = createClient(async () => response({
    status: 422,
    body: JSON.stringify({ detail: [{ loc: ["body", "name"], msg: "Укажите название" }] }),
  }));
  await assert.rejects(client.request("/api/worksets", { method: "POST" }), (error) => {
    assert.equal(error.status, 422);
    assert.equal(error.message, "Укажите название");
    return true;
  });
});

test("malformed JSON and empty successful responses are rejected", async () => {
  const malformed = createClient(async () => response({ body: "{broken" }));
  await assert.rejects(malformed.request("/api/tasks"), (error) => {
    assert.equal(error.kind, "invalid-response");
    assert.match(error.message, /некорректный ответ/);
    return true;
  });

  const empty = createClient(async () => response({ body: "  " }));
  await assert.rejects(empty.request("/api/tasks"), (error) => {
    assert.equal(error.kind, "empty-response");
    assert.match(error.message, /пустой ответ/);
    return true;
  });
});

test("204 responses are accepted without attempting to parse a body", async () => {
  const client = createClient(async () => response({ status: 204, body: "" }));
  assert.equal(await client.request("/api/tasks/1", { method: "DELETE" }), null);
});

test("blob requests share network and HTTP error handling", async () => {
  const expectedBlob = new Blob(["image"]);
  const success = createClient(async () => response({ contentType: "image/png", blob: expectedBlob }));
  assert.equal(await success.requestBlob("/api/files/1"), expectedBlob);

  const failure = createClient(async () => response({ status: 404, body: JSON.stringify({ detail: "Вложение не найдено" }) }));
  await assert.rejects(failure.requestBlob("/api/files/1"), (error) => {
    assert.equal(error.status, 404);
    assert.equal(error.message, "Вложение не найдено");
    return true;
  });
});

test("request options preserve headers and serialize JSON bodies", async () => {
  let captured;
  const client = createClient(async (url, options) => {
    captured = { url, options };
    return response({ body: JSON.stringify({ ok: true }) });
  });
  await client.request("/api/tasks", { method: "POST", headers: { "X-Test": "yes" }, body: { title: "Task" } });
  assert.equal(captured.url, "/api/tasks");
  assert.equal(captured.options.cache, "no-store");
  assert.equal(captured.options.headers["X-Test"], "yes");
  assert.equal(captured.options.headers["Content-Type"], "application/json");
  assert.equal(captured.options.body, JSON.stringify({ title: "Task" }));
});
