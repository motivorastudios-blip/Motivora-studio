const { contextBridge, shell } = require("electron");

contextBridge.exposeInMainWorld("motivora", {
  openExternal: (url) => {
    if (!url || typeof url !== "string") return;
    try {
      new URL(url);
      shell.openExternal(url);
    } catch (error) {
      // Ignore invalid URLs
    }
  },
});





