const workerUrl = document.currentScript?.dataset.workerUrl;

if (workerUrl && "serviceWorker" in navigator) {
  const registerWorker = () => {
    navigator.serviceWorker.register(workerUrl).catch(() => {
      // The app remains usable without offline support.
    });
  };

  if (document.readyState === "complete") {
    registerWorker();
  } else {
    window.addEventListener("load", registerWorker, { once: true });
  }
}
