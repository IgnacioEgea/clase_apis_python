(() => {
  const MAX_ITEMS = 3;

  // Las listas largas se recortan para que el ejemplo se lea de un vistazo.
  function shorten(value) {
    if (Array.isArray(value)) {
      const items = value.slice(0, MAX_ITEMS).map(shorten);
      if (value.length > MAX_ITEMS) items.push(`… y ${value.length - MAX_ITEMS} más`);
      return items;
    }
    if (value && typeof value === "object") {
      return Object.fromEntries(
        Object.entries(value).map(([key, item]) => [key, shorten(item)])
      );
    }
    return value;
  }

  function absoluteUrl(path) {
    return new URL(path, window.location.href).toString();
  }

  document.querySelectorAll(".doc-example").forEach((example) => {
    const url = example.dataset.url;
    const status = example.querySelector(".doc-example-status");
    const output = example.querySelector(".doc-example-output");
    const tryButton = example.querySelector(".doc-try");
    const copyButton = example.querySelector(".doc-copy");

    tryButton?.addEventListener("click", async () => {
      tryButton.disabled = true;
      status.textContent = "Consultando…";
      output.hidden = true;
      output.replaceChildren();
      const start = performance.now();
      try {
        const response = await fetch(url);
        const ms = Math.round(performance.now() - start);
        status.textContent = `HTTP ${response.status} · ${ms} ms`;
        if (example.dataset.format === "Imagen") {
          const image = document.createElement("img");
          image.alt = "Portada devuelta por la API";
          image.src = URL.createObjectURL(await response.blob());
          output.append(image);
        } else {
          const data = await response.json();
          output.textContent = JSON.stringify(shorten(data), null, 2);
        }
        output.hidden = false;
      } catch {
        status.textContent = "No se pudo conectar con la API.";
      } finally {
        tryButton.disabled = false;
      }
    });

    copyButton.addEventListener("click", async () => {
      const command = `curl "${absoluteUrl(url)}"`;
      try {
        await navigator.clipboard.writeText(command);
        status.textContent = "Comando copiado.";
      } catch {
        status.textContent = command;
      }
    });
  });
})();
