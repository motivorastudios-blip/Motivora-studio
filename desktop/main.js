const { app, BrowserWindow, dialog, shell } = require("electron");
const path = require("path");
const { spawn } = require("child_process");
const http = require("http");

const ROOT_DIR = path.resolve(__dirname, "..");
const SERVER_SCRIPT = path.join(ROOT_DIR, "server.py");
const SERVER_PORT = process.env.MOTIVORA_SERVER_PORT || "8888";
const SERVER_URL = process.env.MOTIVORA_SERVER_URL || `http://127.0.0.1:${SERVER_PORT}`;

let pythonProcess = null;
let mainWindow = null;

function waitForServer(retries = 60, intervalMs = 500) {
  return new Promise((resolve, reject) => {
    const attempt = (remaining) => {
      const request = http.get(`${SERVER_URL}/status/ping`, () => {
        request.destroy();
        resolve();
      });
      request.on("error", () => {
        request.destroy();
        if (remaining <= 0) {
          reject(new Error("Local server did not respond in time."));
        } else {
          setTimeout(() => attempt(remaining - 1), intervalMs);
        }
      });
    };
    attempt(retries);
  });
}

function startPythonServer() {
  if (process.env.SKIP_PY_SERVER) {
    return Promise.resolve();
  }

  return new Promise((resolve, reject) => {
    const pythonCmd =
      process.env.MOTIVORA_PYTHON ||
      (process.platform === "win32" ? "python" : "python3");

    pythonProcess = spawn(pythonCmd, [SERVER_SCRIPT], {
      cwd: ROOT_DIR,
      env: {
        ...process.env,
        FLASK_ENV: "production",
      },
      stdio: "inherit",
    });

    pythonProcess.on("error", (error) => {
      reject(error);
    });

    pythonProcess.on("exit", (code) => {
      if (!mainWindow && code !== 0) {
        reject(
          new Error(`Python server exited before startup (code ${code}).`)
        );
      }
    });

    waitForServer()
      .then(resolve)
      .catch((error) => reject(error));
  });
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 840,
    minWidth: 1100,
    minHeight: 720,
    title: "Motivora Studio",
    backgroundColor: "#f7f4ef",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  const url = new URL(`${SERVER_URL}/render`);
  url.searchParams.set("desktop", "1");
  mainWindow.loadURL(url.toString());

  mainWindow.on("closed", () => {
    mainWindow = null;
  });
}

async function bootstrap() {
  try {
    await startPythonServer();
    createWindow();
  } catch (error) {
    dialog.showErrorBox(
      "Motivora Studio - Startup error",
      [
        "We couldn’t start the local render service.",
        "",
        error.message || error.toString(),
        "",
        "Check that Python 3 and Blender are installed, then relaunch Motivora Studio.",
      ].join("\n")
    );
    app.quit();
  }
}

function cleanup() {
  if (pythonProcess && !pythonProcess.killed) {
    pythonProcess.kill();
  }
}

app.on("ready", bootstrap);

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    cleanup();
    app.quit();
  }
});

app.on("before-quit", cleanup);

app.on("activate", () => {
  if (mainWindow === null) {
    createWindow();
  }
});

app.setAboutPanelOptions({
  applicationName: "Motivora Studio",
  applicationVersion: app.getVersion(),
  website: "https://motivora.studio",
  credits: "Built with Blender automation and a lot of hustle.",
});

