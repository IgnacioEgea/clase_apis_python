(() => {
  const historyKey = "videojuegos-api-search-history";
  const favoritesKey = "videojuegos-api-favorites";
  const formatKey = "videojuegos-api-layout-format";
  const historyLimit = 8;
  const categoryCache = new Map();
  const form = document.getElementById("search-form");
  const input = document.getElementById("query");
  const yearSelect = document.getElementById("anio");
  const categorySelect = document.getElementById("categoria");
  const monthSelect = document.getElementById("mes");
  const genreSelect = document.getElementById("genero-filtro");
  const scoreSelect = document.getElementById("nota-min");
  const orderSelect = document.getElementById("orden");
  const submitButton = document.getElementById("search-button");
  const status = document.getElementById("search-status");
  const output = document.getElementById("json-output");
  const summary = document.getElementById("json-summary");
  const openJson = document.getElementById("open-json");
  const gameList = document.getElementById("game-list");
  const catalogMessage = document.getElementById("catalog-message");
  const catalogSummary = document.getElementById("catalog-summary");
  const activeFilters = document.getElementById("active-filters");
  const gameDetail = document.getElementById("game-detail");
  const catalogResults = document.getElementById("catalog-results");
  const backToListTop = document.getElementById("back-to-list-top");
  const detailImage = document.getElementById("detail-image");
  const coverSource = document.getElementById("cover-source");
  const coverHosts = {
    "store.steampowered.com": "Steam",
    "store.playstation.com": "PlayStation Store",
    "en.wikipedia.org": "Wikipedia",
    "www.3djuegos.com": "3DJuegos",
    "www.metacritic.com": "Metacritic",
    "www.igdb.com": "IGDB",
  };

  // La URL de cada portada lleva una huella de su origen: si cambiamos la
  // imagen de un juego, el navegador no reutiliza la versión antigua de su caché.
  function coverVersion(game) {
    let hash = 0;
    for (const char of String(game.imagen_url || "")) {
      hash = (hash * 31 + char.codePointAt(0)) >>> 0;
    }
    return hash.toString(36);
  }

  function describeCoverSource(game) {
    try {
      const host = new URL(game.fuente_imagen).hostname;
      return `Portada oficial · ${coverHosts[host] || host}`;
    } catch {
      return "Portada oficial";
    }
  }
  const gameCover = document.getElementById("game-cover");
  const coverZoom = document.getElementById("cover-zoom");
  const coverDialog = document.getElementById("cover-dialog");
  const zoomedImage = document.getElementById("zoomed-image");
  const historyList = document.getElementById("history-list");
  const historyEmpty = document.getElementById("history-empty");
  const historyMessage = document.getElementById("history-message");
  const favoritesList = document.getElementById("favorites-list");
  const favoritesEmpty = document.getElementById("favorites-empty");
  const favoritesMessage = document.getElementById("favorites-message");
  const favoriteToggle = document.getElementById("favorite-toggle");
  const footerFormat = document.querySelector(".footer-format");
  const formatSummary = footerFormat.querySelector("summary");
  const formatStatus = document.getElementById("format-status");
  const formatButtons = [...footerFormat.querySelectorAll("[data-layout-format]")];
  const formatNames = {
    automatico: "Adaptado a la pantalla",
    movil: "Móvil",
    tablet: "Tablet",
    escritorio: "Escritorio",
    portatil: "Portátil",
    panoramica: "Panorámica",
  };
  let history = [];
  let favorites = [];
  let currentGames = [];
  let selectedGame = null;
  let selectedGameId = "";
  let selectionVersion = 0;
  let catalogRequestVersion = 0;
  // Colección de "Descubre juegos" mostrada en Resultados (null = búsqueda normal).
  let currentCollection = null;
  const discoverChips = [...document.querySelectorAll(".discover-chip")];
  const discoverGenre = document.getElementById("discover-genre");
  const discoverYear = document.getElementById("discover-year");
  const discoverDescription = document.getElementById("discover-description");

  const shareButton = document.getElementById("share-link");
  const shareMessage = document.getElementById("share-message");
  const similarSection = document.getElementById("similar-section");
  const similarList = document.getElementById("similar-list");

  function yearLabel(anio) {
    if (anio === "todos") return "todos los años";
    if (anio === "sin-fecha") return "sin fecha";
    return anio;
  }

  // Año del archivo donde vive un juego: lo usan el historial y los favoritos.
  function gameYear(game) {
    return /^\d{4}$/.test(game.anio_salida || "") ? game.anio_salida : "sin-fecha";
  }

  function applyLayoutFormat(format, save = false) {
    const selectedFormat = Object.hasOwn(formatNames, format)
      ? format
      : "automatico";
    if (selectedFormat === "automatico") {
      document.body.removeAttribute("data-format");
    } else {
      document.body.dataset.format = selectedFormat;
    }
    formatButtons.forEach((button) => {
      button.setAttribute(
        "aria-pressed",
        String(button.dataset.layoutFormat === selectedFormat)
      );
    });
    formatSummary.textContent =
      `Cambiar formato · ${formatNames[selectedFormat]}`;

    if (save) {
      try {
        if (selectedFormat === "automatico") {
          localStorage.removeItem(formatKey);
        } else {
          localStorage.setItem(formatKey, selectedFormat);
        }
        formatStatus.textContent =
          `Formato ${formatNames[selectedFormat]} aplicado.`;
      } catch {
        formatStatus.textContent =
          `Formato ${formatNames[selectedFormat]} aplicado solo hasta cerrar esta página.`;
      }
    }
  }

  formatButtons.forEach((button) => {
    button.addEventListener("click", () => {
      applyLayoutFormat(button.dataset.layoutFormat, true);
      footerFormat.open = false;
    });
  });

  coverZoom.addEventListener("click", () => {
    if (!detailImage.currentSrc) return;
    zoomedImage.src = detailImage.currentSrc;
    zoomedImage.alt = detailImage.alt;
    coverDialog.showModal();
  });
  coverDialog.addEventListener("click", (event) => {
    if (event.target === coverDialog) coverDialog.close();
  });
  coverDialog.addEventListener("close", () => zoomedImage.removeAttribute("src"));
  backToListTop.addEventListener("click", () => {
    gameList.scrollTo({ top: 0, behavior: "smooth" });
    gameList.focus({ preventScroll: true });
  });

  function readHistory() {
    try {
      const saved = JSON.parse(localStorage.getItem(historyKey) || "[]");
      return Array.isArray(saved)
        ? saved.filter((item) =>
          item && typeof item.id === "string"
          && typeof item.titulo === "string"
          && typeof item.anio === "string"
        ).map((item) => ({
          id: item.id,
          titulo: item.titulo,
          anio: item.anio,
        })).slice(0, historyLimit)
        : [];
    } catch {
      historyMessage.textContent = "No se pudo leer el historial guardado en este navegador.";
      return [];
    }
  }

  function renderHistory() {
    historyList.replaceChildren();
    historyEmpty.hidden = history.length > 0;

    history.forEach((entry) => {
      const item = document.createElement("li");
      const button = document.createElement("button");
      item.className = "history-item";
      button.type = "button";
      button.textContent = `${entry.titulo} · ${entry.anio}`;
      button.addEventListener("click", () => openSavedGame(entry, "el historial"));
      item.append(button);
      historyList.append(item);
    });
  }

  function saveSelectedGame(game, anio) {
    history = [
      { id: game.id, titulo: game.titulo, anio },
      ...history.filter((saved) => saved.id !== game.id),
    ]
      .slice(0, historyLimit);
    renderHistory();
    try {
      localStorage.setItem(historyKey, JSON.stringify(history));
      historyMessage.textContent = "";
    } catch {
      historyMessage.textContent = "El juego quedará en el historial hasta cerrar esta página.";
    }
  }

  function readFavorites() {
    try {
      const saved = JSON.parse(localStorage.getItem(favoritesKey) || "[]");
      return Array.isArray(saved)
        ? saved.filter((item) =>
          item && typeof item.id === "string"
          && typeof item.titulo === "string"
          && typeof item.anio === "string"
        ).map((item) => ({
          id: item.id,
          titulo: item.titulo,
          anio: item.anio,
        })).filter((item, index, entries) =>
          entries.findIndex((entry) => entry.id === item.id) === index
        )
        : [];
    } catch {
      favoritesMessage.textContent = "No se pudieron leer los favoritos guardados en este navegador.";
      return [];
    }
  }

  function updateFavoriteToggle() {
    const isFavorite = Boolean(
      selectedGame && favorites.some((item) => item.id === selectedGame.id)
    );
    favoriteToggle.setAttribute("aria-pressed", String(isFavorite));
    favoriteToggle.textContent = isFavorite
      ? "★ En favoritos"
      : "☆ Añadir a favoritos";
  }

  function persistFavorites(message) {
    renderFavorites();
    updateFavoriteToggle();
    try {
      localStorage.setItem(favoritesKey, JSON.stringify(favorites));
      favoritesMessage.textContent = message;
    } catch {
      favoritesMessage.textContent =
        "No se pudieron guardar los cambios; estarán disponibles hasta cerrar esta página.";
    }
  }

  function renderFavorites() {
    favoritesList.replaceChildren();
    favoritesEmpty.hidden = favorites.length > 0;

    favorites.forEach((entry) => {
      const item = document.createElement("li");
      const openButton = document.createElement("button");
      const removeButton = document.createElement("button");
      item.className = "favorite-item";
      openButton.className = "favorite-open";
      openButton.type = "button";
      openButton.textContent = `${entry.titulo} · ${entry.anio}`;
      openButton.setAttribute("aria-label", `Abrir ${entry.titulo}, ${entry.anio}`);
      openButton.addEventListener("click", () => openSavedGame(entry, "favoritos"));
      removeButton.className = "favorite-remove";
      removeButton.type = "button";
      removeButton.textContent = "×";
      removeButton.setAttribute("aria-label", `Quitar ${entry.titulo} de favoritos`);
      removeButton.addEventListener("click", () => {
        favorites = favorites.filter((favorite) => favorite.id !== entry.id);
        persistFavorites(`${entry.titulo} se quitó de favoritos.`);
      });
      item.append(openButton, removeButton);
      favoritesList.append(item);
    });
  }

  async function openSavedGame(entry, origin) {
    const requestVersion = ++catalogRequestVersion;
    setActiveCollection(null);
    status.textContent = `Abriendo ${entry.titulo} desde ${origin}…`;
    submitButton.disabled = true;
    submitButton.textContent = "Abriendo…";
    yearSelect.value = entry.anio;
    input.value = entry.titulo;
    categorySelect.value = "";
    monthSelect.value = "";
    genreSelect.value = "";
    scoreSelect.value = "";
    updateActiveFilters();

    try {
      const categories = await loadCategories(entry.anio);
      if (requestVersion !== catalogRequestVersion) return;
      renderCategories(categories);
      const game = await fetchJson(
        `/api/videojuegos/${encodeURIComponent(entry.id)}`
      );
      if (requestVersion !== catalogRequestVersion) return;
      if (!game || game.id !== entry.id) {
        throw new Error(`No se encontró el videojuego guardado en ${origin}.`);
      }
      renderGames([game]);
      const gameButton = gameList.querySelector(".game-card");
      if (!gameButton) {
        throw new Error(`No se pudo mostrar el videojuego guardado en ${origin}.`);
      }
      selectGame(game, gameButton);
      favoritesMessage.textContent = "";
    } catch (error) {
      if (requestVersion !== catalogRequestVersion) return;
      status.textContent =
        error.message || `No se pudo abrir ${entry.titulo} desde ${origin}.`;
    } finally {
      if (requestVersion === catalogRequestVersion) {
        submitButton.disabled = false;
        submitButton.textContent = "Buscar juegos";
      }
    }
  }

  favoriteToggle.addEventListener("click", () => {
    if (!selectedGame) return;
    const isFavorite = favorites.some((item) => item.id === selectedGame.id);
    if (isFavorite) {
      favorites = favorites.filter((item) => item.id !== selectedGame.id);
      persistFavorites(`${selectedGame.titulo} se quitó de favoritos.`);
    } else {
      favorites = [
        {
          id: selectedGame.id,
          titulo: selectedGame.titulo,
          anio: gameYear(selectedGame),
        },
        ...favorites,
      ];
      persistFavorites(`${selectedGame.titulo} se añadió a favoritos.`);
    }
  });

  document.getElementById("clear-history").addEventListener("click", () => {
    history = [];
    renderHistory();
    try {
      localStorage.removeItem(historyKey);
      historyMessage.textContent = "Historial borrado.";
    } catch {
      historyMessage.textContent = "No se pudo borrar el historial guardado.";
    }
  });

  async function fetchJson(url) {
    const response = await fetch(url, {
      headers: { Accept: "application/json" },
    });
    let data;
    try {
      data = await response.json();
    } catch {
      throw new Error(`La API respondió con el error ${response.status}.`);
    }
    if (!response.ok) {
      throw new Error(data.error || `La API respondió con el error ${response.status}.`);
    }
    return data;
  }

  async function loadCategories(anio) {
    if (categoryCache.has(anio)) {
      return categoryCache.get(anio);
    }
    // Solo se piden las categorías, no el catálogo completo del año.
    const url = new URL("/api/categorias", window.location.href);
    url.searchParams.set("anio", anio);
    const { categorias } = await fetchJson(url);
    const categories = Array.isArray(categorias) ? categorias : [];
    categoryCache.set(anio, categories);
    return categories;
  }

  function safeExternalUrl(value) {
    try {
      const url = new URL(value);
      return url.protocol === "https:" ? url.href : "";
    } catch {
      return "";
    }
  }

  function renderCategories(categories) {
    const selected = categorySelect.value;
    categorySelect.replaceChildren(new Option("Todas", ""));
    categories.forEach((category) => {
      categorySelect.add(new Option(category, category));
    });
    categorySelect.value = categories.includes(selected) ? selected : "";
  }

  function updateActiveFilters() {
    const filters = [];
    if (genreSelect.value) filters.push(genreSelect.selectedOptions[0].textContent);
    if (scoreSelect.value) filters.push(`Nota ${scoreSelect.value}+`);
    if (categorySelect.value) filters.push(categorySelect.value);
    if (monthSelect.value) {
      filters.push(monthSelect.selectedOptions[0].textContent);
    }
    activeFilters.replaceChildren();
    if (!filters.length) {
      activeFilters.textContent = "Sin filtros de género, nota, categoría o mes.";
      return;
    }
    const label = document.createElement("strong");
    label.textContent = "Filtros activos: ";
    activeFilters.append(label, document.createTextNode(filters.join(" · ")));
  }

  function formatDate(value) {
    if (!value) return "Por confirmar";
    const [year, month, day] = value.split("-").map(Number);
    return new Intl.DateTimeFormat("es-ES", {
      day: "numeric",
      month: "long",
      year: "numeric",
      timeZone: "UTC",
    }).format(new Date(Date.UTC(year, month - 1, day)));
  }

  function formatListDate(game) {
    if (!game.fecha_salida) return game.anio_salida || "Sin fecha";
    const [year, month, day] = game.fecha_salida.split("-");
    return `${day}/${month}/${year}`;
  }

  function renderRatings(game) {
    const definitions = [
      {
        label: "3DJuegos · expectativas",
        field: "puntuacion_3djuegos",
        max: 10,
        source: "fuente_puntuacion_3djuegos",
        votes: "votos_3djuegos",
      },
      {
        label: "Vandal · crítica",
        field: "puntuacion_vandal",
        max: 10,
        source: "fuente_puntuacion_vandal",
      },
      {
        label: "Metacritic · crítica",
        field: "puntuacion_metacritic_criticos",
        max: 100,
        source: "fuente_puntuacion_metacritic",
      },
      {
        label: "Metacritic · usuarios",
        field: "puntuacion_metacritic_usuarios",
        max: 10,
        source: "fuente_puntuacion_metacritic",
      },
      {
        label: "Hobby Consolas · crítica",
        field: "puntuacion_hobbyconsolas",
        max: 10,
        source: "fuente_puntuacion_hobbyconsolas",
      },
    ];
    const chart = document.getElementById("ratings-chart");
    chart.replaceChildren();
    const available = definitions.flatMap((definition, index) => {
      const numeric = Number(game[definition.field]);
      if (
        !Number.isFinite(numeric)
        || numeric <= 0
        || numeric > definition.max
      ) return [];
      return [{
        ...definition,
        index,
        numeric,
        normalized: numeric / definition.max * 10,
        sourceUrl: safeExternalUrl(game[definition.source]),
      }];
    });
    if (!available.length) {
      const empty = document.createElement("p");
      empty.className = "rating-legend-empty";
      empty.textContent = "Aún no hay puntuaciones verificadas para este juego.";
      chart.append(empty);
      document.getElementById("ratings-summary").textContent =
        "No hay notas verificables para calcular una media.";
      return;
    }

    const average = available.reduce(
      (total, rating) => total + rating.normalized,
      0
    ) / available.length;
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("class", "rating-donut");
    svg.setAttribute("viewBox", "0 0 160 160");
    svg.setAttribute("role", "img");
    svg.setAttribute(
      "aria-label",
      `Media normalizada de las ${available.length} notas: ${average.toFixed(1)} sobre 10`
    );
    const track = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    track.setAttribute("class", "rating-donut-track");
    track.setAttribute("cx", "80");
    track.setAttribute("cy", "80");
    track.setAttribute("r", "60");
    svg.append(track);
    const progress = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    progress.setAttribute("class", "rating-donut-value");
    progress.setAttribute("cx", "80");
    progress.setAttribute("cy", "80");
    progress.setAttribute("r", "60");
    const circumference = 2 * Math.PI * 60;
    progress.setAttribute(
      "stroke-dasharray",
      `${circumference * average / 10} ${circumference}`
    );
    svg.append(progress);
    const centerValue = document.createElementNS("http://www.w3.org/2000/svg", "text");
    centerValue.setAttribute("class", "rating-donut-text");
    centerValue.setAttribute("x", "80");
    centerValue.setAttribute("y", "78");
    centerValue.textContent = average.toFixed(1);
    svg.append(centerValue);
    const caption = document.createElementNS("http://www.w3.org/2000/svg", "text");
    caption.setAttribute("class", "rating-donut-caption");
    caption.setAttribute("x", "80");
    caption.setAttribute("y", "97");
    caption.textContent = "MEDIA / 10";
    svg.append(caption);
    chart.append(svg);

    const legend = document.createElement("ul");
    legend.className = "rating-legend";
    available.forEach((rating) => {
      const item = document.createElement("li");
      const sourceLabel = document.createElement("span");
      const dot = document.createElement("span");
      const value = document.createElement("strong");
      item.className = "rating-legend-item";
      sourceLabel.className = "rating-legend-source";
      dot.className = "rating-legend-dot";
      dot.style.backgroundColor = rating.index === 0
        ? "#087e78"
        : ["#d17732", "#486bb2", "#8560a8", "#bd5868"][rating.index - 1];
      sourceLabel.append(dot);
      const label = document.createElement("span");
      label.textContent = rating.label;
      if (rating.sourceUrl) {
        const link = document.createElement("a");
        link.href = rating.sourceUrl;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.append(label);
        sourceLabel.append(link);
      } else {
        sourceLabel.append(label);
      }
      value.className = "rating-legend-value";
      const votes = rating.votes && game[rating.votes]
        ? ` · ${game[rating.votes]} votos`
        : "";
      value.textContent =
        `${rating.numeric}/${rating.max}${votes} ${reaction(rating.normalized)}`;
      item.append(sourceLabel, value);
      legend.append(item);
    });
    chart.append(legend);
    document.getElementById("ratings-summary").textContent =
      `Media orientativa de ${available.length} nota${available.length === 1 ? "" : "s"} disponible${available.length === 1 ? "" : "s"} · escalas normalizadas a /10`;
  }

  function reaction(score) {
    if (score >= 8.5) return "🤩";
    if (score >= 7) return "😊";
    if (score >= 5) return "😐";
    return "🙁";
  }

  function renderGames(games) {
    currentGames = games;
    const direction = orderSelect.value === "desc" ? -1 : 1;
    const score = (game) => Number(game.puntuacion_metacritic_criticos) || -1;
    // Las colecciones ya llegan ordenadas por su criterio (nota, ranking…).
    const ordered = currentCollection ? [...games] : [...games].sort((left, right) => {
      if (orderSelect.value === "nota") {
        return score(right) - score(left) || left.titulo.localeCompare(right.titulo, "es");
      }
      if (orderSelect.value === "titulo") {
        return left.titulo.localeCompare(right.titulo, "es", { sensitivity: "base" });
      }
      const leftDate = left.fecha_salida || "9999-99-99";
      const rightDate = right.fecha_salida || "9999-99-99";
      if (leftDate === "9999-99-99" && rightDate !== leftDate) return 1;
      if (rightDate === "9999-99-99" && leftDate !== rightDate) return -1;
      return direction * (
        leftDate.localeCompare(rightDate)
        || left.titulo.localeCompare(right.titulo, "es")
      );
    });
    gameList.replaceChildren();
    ordered.forEach((game) => {
      const button = document.createElement("button");
      const date = document.createElement("span");
      const title = document.createElement("strong");
      button.type = "button";
      button.className = "game-card";
      button.setAttribute("aria-pressed", String(game.id === selectedGameId));
      date.className = "game-date";
      date.textContent = formatListDate(game);
      title.textContent = game.titulo;
      if (currentCollection) {
        const rank = document.createElement("span");
        const titleBlock = document.createElement("span");
        const badge = document.createElement("span");
        // En las colecciones por fecha se muestra la fecha; en los rankings, el puesto.
        const byDate = ["proximos", "recientes", "expansiones-dlc"]
          .includes(currentCollection.coleccion);
        rank.className = byDate ? "game-date" : "game-rank";
        rank.textContent = byDate ? formatListDate(game) : `#${game.posicion}`;
        titleBlock.className = "game-card-title";
        badge.className = "game-badge";
        badge.textContent = game.destacado || "";
        titleBlock.append(title, badge);
        button.append(rank, titleBlock);
        button.addEventListener("click", () => selectGame(game, button));
      } else if (Number(game.puntuacion_metacritic_criticos) > 0) {
        // Con nota publicada, se muestra junto al título para comparar de un vistazo.
        const titleBlock = document.createElement("span");
        const badge = document.createElement("span");
        titleBlock.className = "game-card-title";
        badge.className = "game-badge";
        badge.textContent = `${game.puntuacion_metacritic_criticos} Metacritic`;
        titleBlock.append(title, badge);
        button.append(date, titleBlock);
        button.addEventListener("click", () => selectGame(game, button));
      } else {
        button.append(date, title);
        button.addEventListener("click", () => selectGame(game, button));
      }
      gameList.append(button);
    });
    catalogMessage.hidden = ordered.length > 0;
    catalogMessage.textContent = ordered.length
      ? ""
      : "No hay juegos que coincidan con estos filtros.";
    catalogSummary.textContent = currentCollection
      ? `${currentCollection.titulo} · ${ordered.length} juego${ordered.length === 1 ? "" : "s"}`
      : `${ordered.length} juego${ordered.length === 1 ? "" : "s"} · ordenados por fecha de salida`;
  }

  orderSelect.addEventListener("change", () => {
    if (currentCollection) return;
    renderGames(currentGames);
    // El enlace al JSON refleja también el orden elegido.
    const href = openJson.getAttribute("href");
    if (href && !selectedGame) {
      const url = new URL(href, window.location.href);
      if (["nota", "titulo"].includes(orderSelect.value)) {
        url.searchParams.set("orden", orderSelect.value);
      } else {
        url.searchParams.delete("orden");
      }
      openJson.href = url.toString();
    }
  });
  yearSelect.addEventListener("change", () => form.requestSubmit());
  categorySelect.addEventListener("change", () => form.requestSubmit());
  genreSelect.addEventListener("change", () => form.requestSubmit());
  scoreSelect.addEventListener("change", () => form.requestSubmit());
  monthSelect.addEventListener("change", () => form.requestSubmit());
  document.querySelectorAll(".year-shortcut").forEach((button) => {
    button.addEventListener("click", () => {
      yearSelect.value = button.dataset.year;
      input.value = "";
      categorySelect.value = "";
      monthSelect.value = "";
      genreSelect.value = "";
      scoreSelect.value = "";
      updateActiveFilters();
      form.requestSubmit();
      document.getElementById("catalog-title").scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    });
  });

  function selectGame(game, selectedButton) {
    // El año guardado es siempre el del archivo del juego, aunque se haya
    // encontrado buscando en «Todos los años» o en una colección.
    const anio = gameYear(game);
    selectionVersion += 1;
    selectedGame = game;
    selectedGameId = game.id;
    updateFavoriteToggle();
    catalogResults.classList.add("has-selection");
    backToListTop.hidden = false;
    gameList.querySelectorAll(".game-card").forEach((button) => {
      button.setAttribute("aria-pressed", String(button === selectedButton));
    });
    status.textContent = `Ficha de ${game.titulo} lista.`;
    const detailUrl = new URL(
      `/api/videojuegos/${encodeURIComponent(game.id)}`,
      window.location.href
    );
    document.getElementById("detail-title").textContent = game.titulo;
    document.getElementById("detail-developer").textContent =
      game.desarrollador || "Por confirmar";
    document.getElementById("detail-summary").textContent =
      game.resumen || "Sin resumen disponible.";
    document.getElementById("detail-date").textContent =
      game.fecha_salida
        ? formatDate(game.fecha_salida)
        : game.anio_salida || "Por confirmar";
    document.getElementById("detail-category").textContent = game.juego_base
      ? `${game.tipo || "Contenido adicional"} de ${game.juego_base}`
      : game.categoria || "Por confirmar";
    document.getElementById("detail-platform").textContent =
      game.plataforma || "PS5";
    const estados = {
      fecha_publicada: "Fecha publicada",
      fecha_listada: "Fecha en calendario",
      fuentes_discrepan: "Fuentes con fechas distintas",
      sin_fecha_confirmada: "Sin fecha confirmada",
    };
    document.getElementById("detail-status").textContent =
      estados[game.estado] || game.estado || "Sin información";
    renderRatings(game);

    gameDetail.hidden = false;
    const source = document.getElementById("detail-source");
    const sourceUrl = safeExternalUrl(game.fuente);
    if (sourceUrl) {
      source.href = sourceUrl;
      source.hidden = false;
    } else {
      source.removeAttribute("href");
      source.hidden = true;
    }
    gameCover.hidden = false;
    gameDetail.classList.remove("with-cover");
    gameCover.classList.remove("fit-contain");
    gameCover.classList.add("is-loading");
    gameCover.style.removeProperty("--cover-image");
    detailImage.onload = null;
    detailImage.onerror = null;
    detailImage.removeAttribute("src");
    const version = selectionVersion;
    const coverUrl = `/imagenes/${encodeURIComponent(game.id)}?v=${coverVersion(game)}`;
    detailImage.alt = `Portada de ${game.titulo}`;
    coverZoom.setAttribute("aria-label", `Ampliar imagen de ${game.titulo}`);
    gameDetail.classList.add("with-cover");
    detailImage.onload = () => {
      if (version !== selectionVersion) return;
      // Las portadas casi verticales (entre 3:5 y 4:5) llenan el marco 2:3;
      // el resto se muestra entero sobre un fondo desenfocado.
      const ratio = detailImage.naturalWidth / detailImage.naturalHeight;
      gameCover.classList.toggle("fit-contain", ratio < 0.6 || ratio > 0.8);
      gameCover.style.setProperty("--cover-image", `url("${coverUrl}")`);
      gameCover.classList.remove("is-loading");
      coverSource.textContent = String(game.imagen_url || "").startsWith("/imagenes/")
        ? "Portada ilustrativa: no hay arte oficial disponible para este juego."
        : !game.imagen_url
          ? "Portada buscada en Wikipedia o Steam; si no hay, se muestra una ilustración."
          : describeCoverSource(game);
      status.textContent = `Ficha de ${game.titulo} lista.`;
    };
    detailImage.onerror = () => {
      if (version !== selectionVersion) return;
      gameCover.classList.remove("is-loading");
      status.textContent = `No se pudo cargar la imagen de ${game.titulo}.`;
    };
    detailImage.src = coverUrl;

    gameDetail.hidden = false;
    output.textContent = JSON.stringify(game, null, 2);
    openJson.href = detailUrl.href;
    openJson.setAttribute("aria-disabled", "false");
    summary.textContent = `Ficha JSON · ${game.titulo}`;
    catalogSummary.textContent = currentCollection
      ? `${currentCollection.titulo} · juego seleccionado`
      : `Juego seleccionado · ${yearLabel(anio)}`;
    saveSelectedGame(game, anio);
    shareMessage.textContent = "";
    try {
      // La dirección de la página apunta al juego abierto para poder compartirla.
      window.history.replaceState(null, "", gameShareUrl(game));
    } catch {
      // Algunos navegadores bloquean replaceState en contextos especiales.
    }
    loadSimilar(game, selectionVersion);
    gameDetail.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  function gameShareUrl(game) {
    const url = new URL(window.location.pathname, window.location.href);
    url.searchParams.set("juego", game.id);
    return url.toString();
  }

  shareButton.addEventListener("click", async () => {
    if (!selectedGame) return;
    const url = gameShareUrl(selectedGame);
    try {
      await navigator.clipboard.writeText(url);
      shareMessage.textContent = "Enlace copiado. Quien lo abra verá esta ficha.";
    } catch {
      shareMessage.textContent = `Copia este enlace: ${url}`;
    }
  });

  async function loadSimilar(game, version) {
    similarSection.hidden = true;
    similarList.replaceChildren();
    try {
      const data = await fetchJson(
        `/api/videojuegos/${encodeURIComponent(game.id)}/similares`
      );
      if (version !== selectionVersion || !data.similares.length) return;
      data.similares.forEach((similar) => {
        const item = document.createElement("li");
        const button = document.createElement("button");
        const name = document.createElement("strong");
        const reason = document.createElement("span");
        button.type = "button";
        button.className = "similar-card";
        name.textContent = similar.titulo;
        reason.textContent = [formatListDate(similar), similar.destacado]
          .filter(Boolean)
          .join(" · ");
        button.append(name, reason);
        button.addEventListener("click", () => {
          gameList.querySelectorAll(".game-card").forEach((card) => {
            card.setAttribute("aria-pressed", "false");
          });
          selectGame(similar, null);
          gameDetail.scrollIntoView({ behavior: "smooth", block: "start" });
        });
        item.append(button);
        similarList.append(item);
      });
      similarSection.hidden = false;
    } catch {
      // Las recomendaciones son un extra: si fallan, la ficha sigue igual.
    }
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const requestVersion = ++catalogRequestVersion;
    setActiveCollection(null);
    selectionVersion += 1;
    const anio = yearSelect.value;
    const query = input.value.trim();
    let categoria = categorySelect.value;
    const mes = monthSelect.value;
    openJson.removeAttribute("href");
    openJson.setAttribute("aria-disabled", "true");
    submitButton.disabled = true;
    submitButton.textContent = "Buscando…";
    status.textContent = anio === "todos"
      ? "Buscando en todos los años…"
      : `Leyendo el archivo CSV de ${yearLabel(anio)}…`;
    summary.textContent = query
      ? `Búsqueda: “${query}” · ${yearLabel(anio)}`
      : `Calendario completo · ${yearLabel(anio)}`;
    try {
      // Una búsqueda nueva deja de apuntar al juego compartido.
      window.history.replaceState(null, "", window.location.pathname);
    } catch {
      // Sin replaceState la búsqueda funciona igual.
    }
    output.textContent = "";
    gameList.replaceChildren();
    gameList.scrollTop = 0;
    gameDetail.hidden = true;
    catalogResults.classList.remove("has-selection");
    backToListTop.hidden = true;
    selectedGame = null;
    selectedGameId = "";
    updateFavoriteToggle();
    updateActiveFilters();

    try {
      const categories = await loadCategories(anio);
      if (requestVersion !== catalogRequestVersion) return;
      renderCategories(categories);
      if (!categories.includes(categoria)) {
        categoria = "";
        categorySelect.value = "";
      }
      const apiUrl = new URL(form.action, window.location.href);
      apiUrl.searchParams.set("anio", anio);
      if (query) apiUrl.searchParams.set("q", query);
      if (categoria) apiUrl.searchParams.set("categoria", categoria);
      if (mes) apiUrl.searchParams.set("mes", mes);
      if (genreSelect.value) apiUrl.searchParams.set("genero", genreSelect.value);
      if (scoreSelect.value) apiUrl.searchParams.set("nota_min", scoreSelect.value);
      // El orden se aplica en la página; se añade a la URL para que el JSON coincida.
      if (["nota", "titulo"].includes(orderSelect.value)) {
        apiUrl.searchParams.set("orden", orderSelect.value);
      }
      const data = await fetchJson(apiUrl);
      if (requestVersion !== catalogRequestVersion) return;
      output.textContent = JSON.stringify(data, null, 2);
      openJson.href = apiUrl.toString();
      openJson.setAttribute("aria-disabled", "false");
      renderGames(data);
      status.textContent = data.length
        ? `${data.length} juego${data.length === 1 ? "" : "s"} encontrado${data.length === 1 ? "" : "s"}.`
        : scoreSelect.value
          ? "Ningún juego cumple esos filtros. Ten en cuenta que no todos los juegos tienen nota de Metacritic."
          : "No hay coincidencias para esa consulta en el archivo seleccionado.";
      summary.textContent = `Calendario PS5 · ${yearLabel(anio)} · ${data.length} registro${data.length === 1 ? "" : "s"}`;
      updateActiveFilters();
      if (query && data.length) {
        const firstCard = gameList.querySelector(".game-card");
        if (firstCard) selectGame(data[0], firstCard);
      }
    } catch (error) {
      if (requestVersion !== catalogRequestVersion) return;
      status.textContent = error.message || "No se pudo conectar con la API. Comprueba que el servidor siga activo.";
      summary.textContent = "Error al consultar la API.";
    } finally {
      if (requestVersion === catalogRequestVersion) {
        submitButton.disabled = false;
        submitButton.textContent = "Buscar juegos";
      }
    }
  });

  function setActiveCollection(collection) {
    currentCollection = collection;
    discoverChips.forEach((chip) => {
      chip.setAttribute(
        "aria-pressed",
        String(Boolean(collection) && chip.dataset.collection === collection.coleccion)
      );
    });
  }

  function describeCollection(data) {
    discoverDescription.replaceChildren();
    const name = document.createElement("strong");
    name.textContent = `${data.titulo}: `;
    discoverDescription.append(
      name,
      document.createTextNode(
        `${data.criterio} Mostrando ${data.juegos.length} de ${data.total} juego${data.total === 1 ? "" : "s"}.`
      )
    );
  }

  async function loadCollection(slug, scroll = true) {
    const requestVersion = ++catalogRequestVersion;
    selectionVersion += 1;
    const apiUrl = new URL(`/api/descubrir/${encodeURIComponent(slug)}`, window.location.href);
    if (discoverGenre.value) apiUrl.searchParams.set("genero", discoverGenre.value);
    if (discoverYear.value) apiUrl.searchParams.set("anio", discoverYear.value);
    discoverDescription.textContent = "Cargando la colección…";
    gameDetail.hidden = true;
    catalogResults.classList.remove("has-selection");
    backToListTop.hidden = true;
    selectedGame = null;
    selectedGameId = "";
    updateFavoriteToggle();
    try {
      const data = await fetchJson(apiUrl);
      if (requestVersion !== catalogRequestVersion) return;
      setActiveCollection(data);
      describeCollection(data);
      renderGames(data.juegos);
      if (!data.juegos.length) {
        catalogMessage.textContent =
          "Esta colección no tiene juegos con ese género o año. Prueba a quitar algún filtro.";
      }
      gameList.scrollTop = 0;
      output.textContent = JSON.stringify(data, null, 2);
      openJson.href = apiUrl.toString();
      openJson.setAttribute("aria-disabled", "false");
      summary.textContent = `Colección · ${data.titulo}`;
      status.textContent = `${data.titulo}: ${data.juegos.length} juego${data.juegos.length === 1 ? "" : "s"}.`;
      if (scroll) {
        document.getElementById("catalog-title").scrollIntoView({
          behavior: "smooth",
          block: "start",
        });
      }
    } catch (error) {
      if (requestVersion !== catalogRequestVersion) return;
      discoverDescription.textContent =
        error.message || "No se pudo cargar la colección.";
    }
  }

  discoverChips.forEach((chip) => {
    chip.addEventListener("click", () => loadCollection(chip.dataset.collection));
  });
  [discoverGenre, discoverYear].forEach((select) => {
    select.addEventListener("change", () => {
      // Con una colección abierta, los filtros se aplican al momento.
      if (currentCollection) loadCollection(currentCollection.coleccion, false);
    });
  });

  const initialYear = yearSelect.value;
  loadCategories(initialYear)
    .then((categories) => {
      if (yearSelect.value === initialYear) renderCategories(categories);
    })
    .catch((error) => {
      status.textContent = error.message || "No se pudieron cargar las categorías.";
    });
  // Un enlace compartido (?juego=<id>) abre directamente esa ficha.
  const sharedId = new URLSearchParams(window.location.search).get("juego");
  if (sharedId) {
    fetchJson(`/api/videojuegos/${encodeURIComponent(sharedId)}`)
      .then((game) => {
        openSavedGame(
          { id: game.id, titulo: game.titulo, anio: gameYear(game) },
          "el enlace compartido"
        );
        document.getElementById("catalog-title").scrollIntoView({ block: "start" });
      })
      .catch(() => {
        status.textContent = "El juego del enlace ya no está en el catálogo.";
      });
  }
  history = readHistory();
  renderHistory();
  favorites = readFavorites();
  renderFavorites();
  updateFavoriteToggle();
  try {
    applyLayoutFormat(localStorage.getItem(formatKey) || "automatico");
  } catch {
    applyLayoutFormat("automatico");
    formatStatus.textContent =
      "No se pudo leer el formato guardado; se usa el diseño adaptado a la pantalla.";
  }
})();
