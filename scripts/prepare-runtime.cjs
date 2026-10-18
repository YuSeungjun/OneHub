const fs = require("node:fs");
const path = require("node:path");

if (Number(process.versions.node.split(".")[0]) < 22) {
  throw new Error(
    "Node.js 22 or newer is required for YouTube JavaScript challenges.",
  );
}
const destination = path.join(__dirname, "../build/runtime");
fs.mkdirSync(destination, { recursive: true });
fs.copyFileSync(
  process.execPath,
  path.join(destination, process.platform === "win32" ? "node.exe" : "node"),
);
// Native builds bundle the same supported Node runtime used to build the app.
console.log(
  `Bundled Node ${process.versions.node} (${process.platform}/${process.arch})`,
);
