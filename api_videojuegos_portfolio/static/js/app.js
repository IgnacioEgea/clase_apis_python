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
      button.addEventListener("click", async () => {
        yearSelect.value = entry.anio;
        input.value = entry.titulo;
        categorySelect.value = "";
        monthSelect.value = "";
        try {
          renderCategories(await loadCategories(entry.anio));
        } catch (error) {
          status.textContent = error.message || "No se pudieron cargar los filtros de ese año.";
          return;
        }
        updateActiveFilters();
        form.requestSubmit();
      });
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
      openButton.addEventListener("click", () => openFavorite(entry));
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

  async function openFavorite(entry) {
    const requestVersion = ++catalogRequestVersion;
    status.textContent = `Abriendo ${entry.titulo} desde favoritos…`;
    submitButton.disabled = true;
    submitButton.textContent = "Abriendo…";
    yearSelect.value = entry.anio;
    input.value = entry.titulo;
    categorySelect.value = "";
    monthSelect.value = "";
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
        throw new Error("No se encontró el videojuego guardado en favoritos.");
      }
      renderGames([game]);
      const gameButton = gameList.querySelector(".game-card");
      if (!gameButton) {
        throw new Error("No se pudo mostrar el videojuego guardado en favoritos.");
      }
      selectGame(game, gameButton, entry.anio);
      favoritesMessage.textContent = "";
    } catch (error) {
      if (requestVersion !== catalogRequestVersion) return;
      status.textContent =
        error.message || `No se pudo abrir ${entry.titulo} desde favoritos.`;
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
          anio: yearSelect.value,
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
    if (categorySelect.value) filters.push(categorySelect.value);
    if (monthSelect.value) {
      filters.push(monthSelect.selectedOptions[0].textContent);
    }
    activeFilters.replaceChildren();
    if (!filters.length) {
      activeFilters.textContent = "Sin filtros de categoría o mes.";
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
    const ordered = [...games].sort((left, right) => {
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
      button.append(date, title);
      button.addEventListener("click", () => selectGame(game, button));
      gameList.append(button);
    });
    catalogMessage.hidden = ordered.length > 0;
    catalogMessage.textContent = ordered.length
      ? ""
      : "No hay juegos que coincidan con estos filtros.";
    catalogSummary.textContent = `${ordered.length} juego${ordered.length === 1 ? "" : "s"} · ordenados por fecha de salida`;
  }

  orderSelect.addEventListener("change", () => renderGames(currentGames));
  yearSelect.addEventListener("change", () => form.requestSubmit());
  categorySelect.addEventListener("change", () => form.requestSubmit());
  monthSelect.addEventListener("change", () => form.requestSubmit());
  document.querySelectorAll(".year-shortcut").forEach((button) => {
    button.addEventListener("click", () => {
      yearSelect.value = button.dataset.year;
      input.value = "";
      categorySelect.value = "";
      monthSelect.value = "";
      updateActiveFilters();
      form.requestSubmit();
      document.getElementById("catalog-title").scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    });
  });

  function selectGame(game, selectedButton, anio = yearSelect.value) {
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
    document.getElementById("detail-category").textContent =
      game.categoria || "Por confirmar";
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
    gameCover.classList.remove("is-artwork");
    detailImage.onload = null;
    detailImage.onerror = null;
    detailImage.removeAttribute("src");
    const version = selectionVersion;
    detailImage.alt = `Portada de ${game.titulo}`;
    coverZoom.setAttribute("aria-label", `Ampliar imagen de ${game.titulo}`);
    gameDetail.classList.add("with-cover");
    detailImage.onload = () => {
      if (version === selectionVersion) {
        gameCover.classList.toggle(
          "is-artwork",
          detailImage.naturalWidth / detailImage.naturalHeight > 1.05
        );
        status.textContent = `Ficha de ${game.titulo} lista.`;
      }
    };
    detailImage.onerror = () => {
      if (version !== selectionVersion) return;
      status.textContent = `No se pudo cargar la imagen de ${game.titulo}.`;
    };
    detailImage.src = `/imagenes/${encodeURIComponent(game.id)}`;

    gameDetail.hidden = false;
    output.textContent = JSON.stringify(game, null, 2);
    openJson.href = detailUrl.href;
    openJson.setAttribute("aria-disabled", "false");
    summary.textContent = `Ficha JSON · ${game.titulo}`;
    catalogSummary.textContent = `Juego seleccionado · ${anio}`;
    saveSelectedGame(game, anio);
    gameDetail.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const requestVersion = ++catalogRequestVersion;
    selectionVersion += 1;
    const anio = yearSelect.value;
    const query = input.value.trim();
    let categoria = categorySelect.value;
    const mes = monthSelect.value;
    openJson.removeAttribute("href");
    openJson.setAttribute("aria-disabled", "true");
    submitButton.disabled = true;
    submitButton.textContent = "Buscando…";
    status.textContent = `Leyendo el archivo CSV de ${anio}…`;
    summary.textContent = query
      ? `Búsqueda: “${query}” · ${anio}`
      : `Calendario completo · ${anio}`;
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
      const data = await fetchJson(apiUrl);
      if (requestVersion !== catalogRequestVersion) return;
      output.textContent = JSON.stringify(data, null, 2);
      openJson.href = apiUrl.toString();
      openJson.setAttribute("aria-disabled", "false");
      renderGames(data);
      status.textContent = data.length
        ? `${data.length} juego${data.length === 1 ? "" : "s"} encontrado${data.length === 1 ? "" : "s"}.`
        : "No hay coincidencias para esa consulta en el archivo seleccionado.";
      summary.textContent = `Calendario PS5 ${anio} · ${data.length} registro${data.length === 1 ? "" : "s"}`;
      updateActiveFilters();
      if (query && data.length) {
        const firstCard = gameList.querySelector(".game-card");
        if (firstCard) selectGame(data[0], firstCard, anio);
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

  const initialYear = yearSelect.value;
  loadCategories(initialYear)
    .then((categories) => {
      if (yearSelect.value === initialYear) renderCategories(categories);
    })
    .catch((error) => {
      status.textContent = error.message || "No se pudieron cargar las categorías.";
    });
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
