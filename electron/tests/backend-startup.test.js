const assert = require("node:assert/strict");
const { EventEmitter } = require("node:events");
const { PassThrough } = require("node:stream");
const { test } = require("node:test");
const { waitForBackendPort, startupErrorMessage } = require("../backend-startup");

function childProcess() {
  const child = new EventEmitter();
  child.stdout = new PassThrough();
  return child;
}

test("a slow cold start can report its port after the old 30 second limit", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const child = childProcess();
  const ready = waitForBackendPort(child);
  t.mock.timers.tick(40000);
  child.stdout.write("ONEHUB_");
  child.stdout.write("PORT=45678\r\n");
  assert.equal(await ready, "http://127.0.0.1:45678");
  assert.equal(child.listenerCount("exit"), 0);
  t.mock.timers.tick(90000);
});

test("a backend that never starts times out and releases its listeners", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const child = childProcess();
  const rejected = assert.rejects(waitForBackendPort(child), /시작 시간이 초과/);
  t.mock.timers.tick(90000);
  await rejected;
  assert.equal(child.listenerCount("error"), 0);
  assert.equal(child.listenerCount("exit"), 0);
  assert.equal(child.stdout.listenerCount("data"), 0);
});

test("early process exit is reported immediately", async () => {
  const child = childProcess();
  const rejected = assert.rejects(waitForBackendPort(child), /종료되었습니다 \(7\)/);
  child.emit("exit", 7);
  await rejected;
});

test("spawn failure keeps the actual error", async () => {
  const child = childProcess();
  const failure = new Error("spawn ENOENT");
  const rejected = assert.rejects(waitForBackendPort(child), failure);
  child.emit("error", failure);
  await rejected;
});

test("log output and invalid ports cannot pass the readiness handshake", async () => {
  const child = childProcess();
  const lines = [];
  const ready = waitForBackendPort(child, { log: (line) => lines.push(line) });
  child.stdout.write("Loading\nONEHUB_PORT=0\nONEHUB_PORT=99999\nONEHUB_PORT=12345\n");
  assert.equal(await ready, "http://127.0.0.1:12345");
  assert.deepEqual(lines, ["Loading", "ONEHUB_PORT=0", "ONEHUB_PORT=99999"]);
});

test("installed app errors show a log path without developer commands", () => {
  const message = startupErrorMessage(new Error("시작 실패"), {
    packaged: true,
    logPath: "C:\\Users\\user\\onehub_debug.log",
  });
  assert.match(message, /시작 실패/);
  assert.match(message, /OneHub 설치 파일/);
  assert.match(message, /onehub_debug\.log/);
  assert.doesNotMatch(message, /uv sync/);
  assert.match(startupErrorMessage(new Error("test"), { packaged: false }), /uv sync/);
});
