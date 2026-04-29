const elements = {
  answer: document.getElementById("answer"),
  question: document.getElementById("question"),
  pageSize: document.getElementById("page-size"),
  searchButton: document.getElementById("search-button"),
  status: document.getElementById("status"),
  summaryCards: document.getElementById("summary-cards"),
  sections: document.getElementById("results-sections"),
  tableHead: document.querySelector("#results-table thead"),
  tableBody: document.querySelector("#results-table tbody"),
  downloadJson: document.getElementById("download-json"),
  downloadCsv: document.getElementById("download-csv"),
  downloadXlsx: document.getElementById("download-xlsx"),
};

const exampleButtons = document.querySelectorAll("[data-example]");

let currentResult = null;

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function setStatus(message, tone = "") {
  elements.status.textContent = message;
  elements.status.className = `status-line${tone ? ` ${tone}` : ""}`;
}

function setDownloadsEnabled(enabled) {
  [elements.downloadJson, elements.downloadCsv, elements.downloadXlsx].forEach(
    (button) => {
      button.disabled = !enabled;
    },
  );
}

function renderSummaryCards(result) {
  const markup = result.sections
    .map(
      (section) => `
        <article class="summary-card">
          <span class="count">${section.total}</span>
          <span class="label">${escapeHtml(section.title)}</span>
        </article>
      `,
    )
    .join("");

  elements.summaryCards.innerHTML = markup;
}

function pillRow(values) {
  if (!values || values.length === 0) {
    return "";
  }

  return `
    <div class="pill-row">
      ${values
        .filter(Boolean)
        .slice(0, 6)
        .map((value) => `<span class="pill">${escapeHtml(value)}</span>`)
        .join("")}
    </div>
  `;
}

function renderDatasetItem(item) {
  return `
    <article class="result-item">
      <h4>${escapeHtml(item.title || "Untitled dataset")}</h4>
      ${pillRow(item.tags)}
      <p>${escapeHtml(item.description_short || item.description || "No description available.")}</p>
      <div class="pill-row">
        ${item.organization ? `<span class="pill">${escapeHtml(item.organization)}</span>` : ""}
        <span class="pill">${escapeHtml(item.resources_count ?? 0)} resources</span>
      </div>
      <a class="item-link" href="${escapeHtml(item.url || "#")}" target="_blank" rel="noreferrer">Open dataset</a>
    </article>
  `;
}

function renderDataserviceItem(item) {
  return `
    <article class="result-item">
      <h4>${escapeHtml(item.title || "Untitled dataservice")}</h4>
      ${pillRow(item.tags)}
      <p>${escapeHtml(item.description || "No description available.")}</p>
      <div class="pill-row">
        ${item.organization ? `<span class="pill">${escapeHtml(item.organization)}</span>` : ""}
        ${item.base_api_url ? `<span class="pill">${escapeHtml(item.base_api_url)}</span>` : ""}
      </div>
      <a class="item-link" href="${escapeHtml(item.url || "#")}" target="_blank" rel="noreferrer">Open dataservice</a>
    </article>
  `;
}

function renderOrganizationItem(item) {
  const metrics = item.metrics || {};
  const metricPills = [
    typeof metrics.datasets !== "undefined" ? `${metrics.datasets} datasets` : "",
    typeof metrics.reuses !== "undefined" ? `${metrics.reuses} reuses` : "",
    typeof metrics.followers !== "undefined" ? `${metrics.followers} followers` : "",
  ].filter(Boolean);

  return `
    <article class="result-item">
      <h4>${escapeHtml(item.name || "Untitled organization")}</h4>
      ${pillRow(item.badges)}
      ${metricPills.length ? `<div class="pill-row">${metricPills.map((metric) => `<span class="pill">${escapeHtml(metric)}</span>`).join("")}</div>` : ""}
      <p>${item.acronym ? `Acronym: ${escapeHtml(item.acronym)}` : "Organization profile from the data.gouv.fr catalog."}</p>
      <a class="item-link" href="${escapeHtml(item.url || "#")}" target="_blank" rel="noreferrer">Open organization</a>
    </article>
  `;
}

function renderSection(section) {
  let itemsMarkup = '<div class="empty-state">No result for this section yet.</div>';

  if (section.error) {
    itemsMarkup = `<div class="empty-state">This section could not be loaded: ${escapeHtml(section.error)}</div>`;
  } else if (section.items.length > 0) {
    const itemRenderer =
      section.key === "datasets"
        ? renderDatasetItem
        : section.key === "dataservices"
          ? renderDataserviceItem
          : renderOrganizationItem;

    itemsMarkup = `
      <div class="result-list">
        ${section.items.map((item) => itemRenderer(item)).join("")}
      </div>
    `;
  }

  return `
    <section class="results-card">
      <h3>${escapeHtml(section.title)}</h3>
      <ul class="section-meta">
        <li>${escapeHtml(section.total)} total match${section.total === 1 ? "" : "es"}</li>
        <li>${escapeHtml(section.displayed)} shown</li>
      </ul>
      ${itemsMarkup}
    </section>
  `;
}

function renderSections(result) {
  elements.sections.innerHTML = result.sections.map(renderSection).join("");
}

function renderTable(rows) {
  if (!rows || rows.length === 0) {
    elements.tableHead.innerHTML = "";
    elements.tableBody.innerHTML = `
      <tr>
        <td>No rows to preview yet.</td>
      </tr>
    `;
    return;
  }

  const columns = Array.from(
    rows.reduce((set, row) => {
      Object.keys(row).forEach((key) => set.add(key));
      return set;
    }, new Set()),
  );

  elements.tableHead.innerHTML = `
    <tr>
      ${columns.map((column) => `<th>${escapeHtml(column)}</th>`).join("")}
    </tr>
  `;

  elements.tableBody.innerHTML = rows
    .map(
      (row) => `
        <tr>
          ${columns
            .map((column) => `<td>${escapeHtml(row[column] ?? "")}</td>`)
            .join("")}
        </tr>
      `,
    )
    .join("");
}

function renderResult(result) {
  currentResult = result;
  elements.answer.textContent = result.answer;
  renderSummaryCards(result);
  renderSections(result);
  renderTable(result.rows);
  setDownloadsEnabled(result.rows.length > 0);
}

async function postJson(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const errorPayload = await response.json().catch(() => ({}));
    const message = errorPayload.error || `Request failed with ${response.status}`;
    throw new Error(message);
  }

  return response;
}

async function runSearch() {
  const question = elements.question.value.trim();
  if (!question) {
    setStatus("Please enter a question first.", "error");
    return;
  }

  elements.searchButton.disabled = true;
  setStatus("Searching datasets, dataservices, and organizations...", "");

  try {
    const response = await postJson("/ui/api/search", {
      question,
      page_size: Number(elements.pageSize.value),
    });
    const result = await response.json();
    renderResult(result);

    if (result.errors && result.errors.length > 0) {
      setStatus(
        `Search completed with partial warnings: ${result.errors.join(" | ")}`,
        "error",
      );
    } else {
      setStatus("Search complete. You can now review or export the displayed rows.", "success");
    }
  } catch (error) {
    currentResult = null;
    setDownloadsEnabled(false);
    elements.summaryCards.innerHTML = "";
    elements.sections.innerHTML = "";
    renderTable([]);
    elements.answer.textContent = "Run a search to populate the explorer.";
    setStatus(error.message, "error");
  } finally {
    elements.searchButton.disabled = false;
  }
}

async function downloadResult(format) {
  if (!currentResult || !currentResult.rows || currentResult.rows.length === 0) {
    setStatus("Run a search before downloading.", "error");
    return;
  }

  try {
    setStatus(`Preparing ${format.toUpperCase()} export...`);
    const response = await postJson("/ui/api/export", {
      format,
      question: currentResult.question,
      search_query: currentResult.search_query,
      rows: currentResult.rows,
    });

    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    const disposition = response.headers.get("Content-Disposition") || "";
    const filenameMatch = disposition.match(/filename="([^"]+)"/i);
    anchor.href = url;
    anchor.download = filenameMatch ? filenameMatch[1] : `datagouv-results.${format}`;
    anchor.click();
    URL.revokeObjectURL(url);
    setStatus(`${format.toUpperCase()} export ready.`, "success");
  } catch (error) {
    setStatus(error.message, "error");
  }
}

elements.searchButton.addEventListener("click", runSearch);
elements.downloadJson.addEventListener("click", () => downloadResult("json"));
elements.downloadCsv.addEventListener("click", () => downloadResult("csv"));
elements.downloadXlsx.addEventListener("click", () => downloadResult("xlsx"));

elements.question.addEventListener("keydown", (event) => {
  if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
    event.preventDefault();
    runSearch();
  }
});

exampleButtons.forEach((button) => {
  button.addEventListener("click", () => {
    elements.question.value = button.dataset.example || "";
    runSearch();
  });
});

setDownloadsEnabled(false);
renderTable([]);
