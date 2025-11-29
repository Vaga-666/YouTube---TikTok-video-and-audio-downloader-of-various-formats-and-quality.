document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("download-form");
  const panel = document.getElementById("job-panel");
  const statusMessage = document.getElementById("status-message");
  const progressBar = document.getElementById("progress-bar");
  const progressValue = document.getElementById("progress-value");
  const resultBox = document.getElementById("result");
  const metaSection = document.getElementById("meta");
  const metaTitle = document.getElementById("meta-title");
  const metaDuration = document.getElementById("meta-duration");
  const metaSize = document.getElementById("meta-size");
  const metaThumbnail = document.getElementById("meta-thumbnail");
  const qualitySelect = document.getElementById("quality");
  const urlField = document.getElementById("media-url");
  const formatSelect = document.getElementById("format");
  const audioFormats = new Set(["mp3", "m4a", "ogg", "source"]);

  if (!form || !panel) return;

  const lastUrl = window.localStorage.getItem("last_url");
  if (lastUrl && urlField) {
    urlField.value = lastUrl;
  }

  form.addEventListener("change", (event) => {
    if (event.target.name === "format" && qualitySelect) {
      const disabled = audioFormats.has(event.target.value);
      qualitySelect.disabled = disabled;
      qualitySelect.classList.toggle("opacity-50", disabled);
      if (disabled) {
        qualitySelect.value = "auto";
      } else if (qualitySelect.value === "auto") {
        qualitySelect.value = "720p";
      }
    }
  });

  if (formatSelect && qualitySelect && audioFormats.has(formatSelect.value)) {
    qualitySelect.disabled = true;
    qualitySelect.classList.add("opacity-50");
    qualitySelect.value = "auto";
  }

  let activeMarker = null;

  form.addEventListener("submit", async (event) => {
    event.preventDefault();

    if (activeMarker) {
      activeMarker.cancelled = true;
    }

    const formData = new FormData(form);
    const url = formData.get("url");
    const qualityValue = formData.get("quality");
    const quality = qualityValue || "auto";
    const format = formatSelect ? formatSelect.value : formData.get("format") || "mp4";

    if (url) {
      window.localStorage.setItem("last_url", url);
    }

    resetUI();
    panel.classList.remove("hidden");
    setStatus("Создаю задачу...", false);

    try {
      const resp = await fetch(
        `/api/download?url=${encodeURIComponent(url)}&format=${encodeURIComponent(format)}&quality=${encodeURIComponent(quality)}`,
        {
          method: "POST",
        },
      );

      if (!resp.ok) {
        let errText = `HTTP ${resp.status}`;
        try {
          const err = await resp.json();
          if (err.detail) errText = err.detail;
        } catch (_) {
          // ignore JSON parse errors
        }
        setStatus(`Ошибка: ${errText}`, true);
        console.error("download error:", errText);
        return;
      }

      const data = await resp.json();
      console.log("download response:", data);
      setStatus("Задача создана, ожидайте...", false);

      activeMarker = { cancelled: false };
      await pollStatus(data.job_id, activeMarker);
    } catch (error) {
      setStatus(
        error instanceof Error
          ? error.message
          : "Не удалось создать задачу.",
        true,
      );
    }
  });

  function resetUI() {
    setStatus("", false);
    updateProgress(0);
    resultBox.innerHTML = "";
    metaSection.classList.add("hidden");
    metaTitle.textContent = "";
    metaDuration.textContent = "";
    metaSize.textContent = "";
    metaThumbnail.innerHTML = "";
  }

  function setStatus(message, isError) {
    statusMessage.textContent = message || "";
    statusMessage.classList.toggle("text-red-300", Boolean(isError));
    statusMessage.classList.toggle("text-emerald-300", Boolean(!isError));
  }

  function updateProgress(value) {
    const percent = Math.max(0, Math.min(100, Number(value) || 0));
    progressBar.style.width = `${percent}%`;
    progressValue.textContent = `${percent}%`;
  }

  function updateMeta(meta) {
    if (!meta || typeof meta !== "object") {
      return;
    }

    const { title, duration, thumbnail, estimated_size_mb } = meta;
    if (title || duration || thumbnail || estimated_size_mb) {
      metaSection.classList.remove("hidden");
    }

    if (title) {
      metaTitle.textContent = title;
    }

    if (typeof duration === "number") {
      metaDuration.textContent = formatDuration(duration);
    }

    if (typeof estimated_size_mb === "number") {
      metaSize.textContent = `${estimated_size_mb} МБ`;
    }

    if (thumbnail) {
      metaThumbnail.innerHTML = `
        <img src="${thumbnail}" alt="Превью" class="mt-3 w-full max-w-xs rounded-md border border-slate-700" loading="lazy" />
      `;
    }
  }

  async function pollStatus(jobId, marker) {
    if (!jobId) {
      setStatus("Некорректный идентификатор задачи.", true);
      return;
    }

    while (!marker.cancelled) {
      let data;
      try {
        const response = await fetch(`/api/status/${jobId}`);
        data = await safeJson(response);
        if (!response.ok) {
          throw new Error("Не удалось получить статус задачи.");
        }
      } catch (error) {
        setStatus(
          error instanceof Error
            ? error.message
            : "Ошибка получения статуса задачи.",
          true,
        );
        break;
      }

      if (marker.cancelled) {
        break;
      }

      updateProgress(data?.progress ?? 0);
      updateMeta(data?.meta);

      const status = data?.status || "";
      const isError = status === "error";
      const message =
        data?.message ||
        (status === "done"
          ? "Файл готов к скачиванию."
          : status || "Ожидание...");

      setStatus(message, isError);

      if (status === "done") {
        showDownload(jobId, data?.filename);
        break;
      }

      if (status === "error") {
        const reason = data?.reason ? ` (${data.reason})` : "";
        resultBox.innerHTML = `<p class="text-red-300">${data?.error || "Произошла ошибка при обработке задачи."}${reason}</p>`;
        break;
      }

      await sleep(1500);
    }

    if (marker === activeMarker) {
      activeMarker = null;
    }
  }

  function showDownload(jobId, filename) {
    const safeName = filename || "скачать файл";
    resultBox.innerHTML = `
      <div class="flex flex-wrap gap-3">
        <a
          class="inline-flex items-center justify-center rounded-md bg-emerald-500 px-4 py-2 font-semibold text-white transition hover:bg-emerald-400 focus:outline-none focus:ring-4 focus:ring-emerald-300"
          href="/api/file/${jobId}"
        >
          Скачать ${safeName}
        </a>
        <button
          id="delete-${jobId}"
          class="inline-flex items-center justify-center rounded-md border border-red-500 px-4 py-2 font-semibold text-red-300 transition hover:bg-red-500/10 focus:outline-none focus:ring-4 focus:ring-red-500/30"
          type="button"
        >
          Удалить файл
        </button>
      </div>
    `;

    const deleteBtn = document.getElementById(`delete-${jobId}`);
    if (deleteBtn) {
      deleteBtn.addEventListener("click", () => deleteFile(jobId));
    }
  }

  async function deleteFile(jobId) {
    try {
      const response = await fetch(`/api/file/${jobId}`, {
        method: "DELETE",
      });
      if (!response.ok) {
        throw new Error("Не удалось удалить файл.");
      }
      resultBox.innerHTML = `<p class="text-slate-300">Файл удалён.</p>`;
      setStatus("Файл удалён.", false);
      updateProgress(0);
    } catch (error) {
      setStatus(
        error instanceof Error ? error.message : "Ошибка удаления файла.",
        true,
      );
    }
  }

  function sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  async function safeJson(response) {
    try {
      return await response.json();
    } catch (error) {
      return null;
    }
  }

  function formatDuration(seconds) {
    if (!Number.isFinite(seconds)) {
      return "";
    }
    const total = Math.max(0, Math.floor(seconds));
    const h = Math.floor(total / 3600);
    const m = Math.floor((total % 3600) / 60);
    const s = total % 60;
    const parts = [];
    if (h) parts.push(String(h).padStart(2, "0"));
    parts.push(String(m).padStart(2, "0"));
    parts.push(String(s).padStart(2, "0"));
    return parts.join(":");
  }
});
