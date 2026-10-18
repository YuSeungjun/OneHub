const { createInterface } = require("node:readline");

function waitForBackendPort(child, { timeoutMs = 90000, log = () => {} } = {}) {
  return new Promise((resolve, reject) => {
    const lines = createInterface({ input: child.stdout });
    const finish = (error, url) => {
      clearTimeout(timeout);
      child.removeListener("error", onError);
      child.removeListener("exit", onExit);
      lines.removeListener("line", onLine);
      lines.close();
      if (error) reject(error);
      else resolve(url);
    };
    const onError = (error) => finish(error);
    const onExit = (code) =>
      finish(new Error(`백엔드가 시작 중 종료되었습니다 (${code}).`));
    const onLine = (line) => {
      const match = /^ONEHUB_PORT=(\d+)$/.exec(line.trim());
      const port = Number(match?.[1]);
      if (Number.isInteger(port) && port > 0 && port <= 65535)
        finish(null, `http://127.0.0.1:${port}`);
      else log(line);
    };
    const timeout = setTimeout(
      () => finish(new Error("다운로드 서비스 시작 시간이 초과되었습니다.")),
      timeoutMs,
    );
    child.once("error", onError);
    child.once("exit", onExit);
    lines.on("line", onLine);
  });
}

function startupErrorMessage(error, { packaged, logPath }) {
  const advice = packaged
    ? "OneHub 설치 파일로 다시 설치해 주세요. 문제가 계속되면 아래 로그를 확인해 주세요."
    : "개발 환경에서는 먼저 uv sync를 실행해 주세요.";
  return `${error.message}\n\n${advice}\n\n로그: ${logPath}`;
}

module.exports = { waitForBackendPort, startupErrorMessage };
