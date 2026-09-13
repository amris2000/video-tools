const state = {
  project: null,
  edits: [],
  clips: [],
  renders: [],
  renderScope: "exports",
  currentView: "edit",
  currentRenderFilename: "",
  clipMap: new Map(),
  currentFilename: "",
  document: { version: 1, output: "", clips: [] },
  savedSnapshot: "",
  selectedIndex: -1,
  dirty: false,
  activeDialogMode: "new",
  dialogOutputTouched: false,
  playbackStopAt: null,
};

const elements = {
  projectLine: document.getElementById("projectLine"),
  dirtyBadge: document.getElementById("dirtyBadge"),
  viewEditButton: document.getElementById("viewEditButton"),
  viewRendersButton: document.getElementById("viewRendersButton"),
  editView: document.getElementById("editView"),
  rendersView: document.getElementById("rendersView"),
  editSelect: document.getElementById("editSelect"),
  outputInput: document.getElementById("outputInput"),
  saveButton: document.getElementById("saveButton"),
  newButton: document.getElementById("newButton"),
  renameButton: document.getElementById("renameButton"),
  saveAsButton: document.getElementById("saveAsButton"),
  deleteButton: document.getElementById("deleteButton"),
  addClipButton: document.getElementById("addClipButton"),
  timelineList: document.getElementById("timelineList"),
  timelineEmpty: document.getElementById("timelineEmpty"),
  inspectorAnchor: document.getElementById("inspectorAnchor"),
  inspectorPanel: document.getElementById("inspectorPanel"),
  inspectorEmpty: document.getElementById("inspectorEmpty"),
  inspectorContent: document.getElementById("inspectorContent"),
  previewVideo: document.getElementById("previewVideo"),
  sourceDuration: document.getElementById("sourceDuration"),
  currentPosition: document.getElementById("currentPosition"),
  selectedDuration: document.getElementById("selectedDuration"),
  startRange: document.getElementById("startRange"),
  endRange: document.getElementById("endRange"),
  startInput: document.getElementById("startInput"),
  endInput: document.getElementById("endInput"),
  setStartButton: document.getElementById("setStartButton"),
  setEndButton: document.getElementById("setEndButton"),
  playSelectionButton: document.getElementById("playSelectionButton"),
  labelInput: document.getElementById("labelInput"),
  editDialog: document.getElementById("editDialog"),
  editDialogForm: document.getElementById("editDialogForm"),
  editDialogTitle: document.getElementById("editDialogTitle"),
  editDialogMessage: document.getElementById("editDialogMessage"),
  dialogFilename: document.getElementById("dialogFilename"),
  dialogOutput: document.getElementById("dialogOutput"),
  dialogSubmitButton: document.getElementById("dialogSubmitButton"),
  dialogCancelButton: document.getElementById("dialogCancelButton"),
  renameDialog: document.getElementById("renameDialog"),
  renameDialogForm: document.getElementById("renameDialogForm"),
  renameFilename: document.getElementById("renameFilename"),
  renameCancelButton: document.getElementById("renameCancelButton"),
  clipDialog: document.getElementById("clipDialog"),
  clipDialogForm: document.getElementById("clipDialogForm"),
  clipSearchInput: document.getElementById("clipSearchInput"),
  clipList: document.getElementById("clipList"),
  clipCancelButton: document.getElementById("clipCancelButton"),
  refreshRendersButton: document.getElementById("refreshRendersButton"),
  exportsScopeButton: document.getElementById("exportsScopeButton"),
  socialScopeButton: document.getElementById("socialScopeButton"),
  rendersEmpty: document.getElementById("rendersEmpty"),
  rendersList: document.getElementById("rendersList"),
  renderPlayerWrap: document.getElementById("renderPlayerWrap"),
  renderVideo: document.getElementById("renderVideo"),
  toast: document.getElementById("toast"),
};

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });

  if (response.status === 204) {
    return null;
  }

  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || `Request failed with status ${response.status}`);
  }

  return data;
}

function normalizeDocument(documentValue) {
  return {
    version: 1,
    output: documentValue.output || "",
    clips: Array.isArray(documentValue.clips)
      ? documentValue.clips.map((clip) => ({
          file: clip.file,
          start: Number(clip.start),
          end: Number(clip.end),
          ...(clip.label ? { label: clip.label } : {}),
        }))
      : [],
  };
}

function cloneCurrentDocument() {
  return JSON.parse(JSON.stringify(state.document));
}

function updateDirtyState() {
  const snapshot = JSON.stringify(state.document);
  state.dirty = snapshot !== state.savedSnapshot;
  elements.dirtyBadge.textContent = state.dirty ? "Unsaved changes" : "Saved";
  elements.dirtyBadge.classList.toggle("dirty", state.dirty);
  elements.saveButton.disabled = !state.currentFilename || !state.dirty;
}

function markSaved(documentValue) {
  state.document = normalizeDocument(documentValue);
  state.savedSnapshot = JSON.stringify(state.document);
  updateDirtyState();
  renderAll();
}

function deriveSuggestedOutput(filename) {
  if (!filename.endsWith(".json")) {
    return "video.mp4";
  }
  const stem = filename.slice(0, -5);
  const base = stem.endsWith("_edit") ? stem.slice(0, -5) : stem;
  return `${base}_video.mp4`;
}

function formatSeconds(value) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "-";
  }
  return `${Number(value).toFixed(3)} s`;
}

function mediaUrl(relativePath) {
  return `/media/${relativePath.split("/").map(encodeURIComponent).join("/")}`;
}

function renderUrl(filename) {
  const base = state.renderScope === "social" ? "/social-renders" : "/renders";
  return `${base}/${encodeURIComponent(filename)}`;
}

function showToast(message) {
  elements.toast.textContent = message;
  elements.toast.classList.remove("hidden");
  window.clearTimeout(showToast.timeoutId);
  showToast.timeoutId = window.setTimeout(() => {
    elements.toast.classList.add("hidden");
  }, 2800);
}

function currentClip() {
  if (state.selectedIndex < 0 || state.selectedIndex >= state.document.clips.length) {
    return null;
  }
  return state.document.clips[state.selectedIndex];
}

function selectedClipInfo() {
  const clip = currentClip();
  return clip ? state.clipMap.get(clip.file) || null : null;
}

function renderEditSelector() {
  elements.editSelect.innerHTML = "";

  if (!state.edits.length) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "No edits yet";
    elements.editSelect.append(option);
    elements.editSelect.disabled = true;
    return;
  }

  elements.editSelect.disabled = false;

  for (const edit of state.edits) {
    const option = document.createElement("option");
    option.value = edit.filename;
    option.textContent = edit.filename;
    option.selected = edit.filename === state.currentFilename;
    elements.editSelect.append(option);
  }
}

function renderTimeline() {
  elements.timelineList.innerHTML = "";
  elements.timelineEmpty.classList.toggle("hidden", state.document.clips.length > 0);

  state.document.clips.forEach((clip, index) => {
    const wrapper = document.createElement("div");
    wrapper.className = "timeline-item";
    if (index === state.selectedIndex) {
      wrapper.classList.add("selected");
    }

    const info = state.clipMap.get(clip.file);
    const duration = clip.end - clip.start;
    const thumbnailHtml = info?.thumbnail_url
      ? `<img class="clip-thumb" src="${info.thumbnail_url}" alt="Thumbnail for ${clip.file}" loading="lazy" />`
      : `<div class="clip-thumb clip-thumb-placeholder" aria-hidden="true"></div>`;

    wrapper.innerHTML = `
      <div class="timeline-grid">
        <div class="timeline-col timeline-col-main">
          <div class="clip-index">${index + 1}</div>
          <div class="clip-file">${clip.file}</div>
          <div class="clip-range">${formatSeconds(clip.start)} -> ${formatSeconds(clip.end)}</div>
          <div class="timeline-actions">
            <button type="button" data-action="up" ${index === 0 ? "disabled" : ""}>Move Up</button>
            <button type="button" data-action="down" ${index === state.document.clips.length - 1 ? "disabled" : ""}>Move Down</button>
            <button type="button" data-action="remove" class="danger">Remove</button>
          </div>
        </div>

        <div class="timeline-col timeline-col-thumb">
          ${thumbnailHtml}
        </div>

        <div class="timeline-col timeline-col-details">
          <div class="timeline-detail">Duration ${formatSeconds(duration)}</div>
          <div class="timeline-detail clip-label-detail">${clip.label || "No label"}</div>
          <div class="timeline-detail">${info?.duration ? `Source ${formatSeconds(info.duration)}` : "Source duration unavailable"}</div>
        </div>

        <div class="timeline-col timeline-col-inspect">
          <button type="button" data-action="select">Inspect</button>
        </div>
      </div>
    `;

    wrapper.querySelectorAll("button[data-action]").forEach((button) => {
      button.addEventListener("click", () => handleTimelineAction(index, button.dataset.action));
    });

    if (index === state.selectedIndex) {
      const inspectorSlot = document.createElement("div");
      inspectorSlot.className = "selected-inspector-slot";
      inspectorSlot.append(elements.inspectorPanel);
      wrapper.append(inspectorSlot);
    }

    elements.timelineList.append(wrapper);
  });

  if (state.selectedIndex < 0 || state.selectedIndex >= state.document.clips.length) {
    elements.inspectorAnchor.append(elements.inspectorPanel);
  }
}

function renderInspector() {
  const clip = currentClip();
  const clipInfo = selectedClipInfo();
  const hasSelection = Boolean(clip && clipInfo);

  elements.inspectorPanel.classList.toggle("hidden", !hasSelection);
  elements.inspectorEmpty.classList.toggle("hidden", hasSelection);
  elements.inspectorContent.classList.toggle("hidden", !hasSelection);

  if (!clip || !clipInfo) {
    elements.previewVideo.removeAttribute("src");
    elements.previewVideo.load();
    return;
  }

  if (!elements.previewVideo.dataset.currentFile || elements.previewVideo.dataset.currentFile !== clip.file) {
    elements.previewVideo.dataset.currentFile = clip.file;
    elements.previewVideo.src = mediaUrl(clip.file);
    elements.previewVideo.load();
  }

  const maxDuration = clipInfo.duration || clip.end;
  elements.sourceDuration.textContent = formatSeconds(clipInfo.duration);
  elements.selectedDuration.textContent = formatSeconds(clip.end - clip.start);
  elements.currentPosition.textContent = formatSeconds(elements.previewVideo.currentTime);

  elements.startRange.max = String(maxDuration);
  elements.endRange.max = String(maxDuration);
  elements.startRange.value = String(clip.start);
  elements.endRange.value = String(clip.end);
  elements.startInput.max = String(maxDuration);
  elements.endInput.max = String(maxDuration);
  elements.startInput.value = String(clip.start);
  elements.endInput.value = String(clip.end);
  elements.labelInput.value = clip.label || "";
}

function renderAll() {
  renderView();
  renderEditSelector();
  renderTimeline();
  renderInspector();
  renderRendersList();
  elements.outputInput.value = state.document.output || "";
  elements.renameButton.disabled = !state.currentFilename || state.dirty;
  elements.saveAsButton.disabled = !state.currentFilename;
  elements.deleteButton.disabled = !state.currentFilename;
  updateDirtyState();
}

function renderView() {
  const editActive = state.currentView === "edit";
  elements.editView.classList.toggle("hidden", !editActive);
  elements.rendersView.classList.toggle("hidden", editActive);
  elements.viewEditButton.classList.toggle("active", editActive);
  elements.viewRendersButton.classList.toggle("active", !editActive);
  elements.viewEditButton.setAttribute("aria-selected", editActive ? "true" : "false");
  elements.viewRendersButton.setAttribute("aria-selected", editActive ? "false" : "true");
}

function renderRendersList() {
  elements.rendersList.innerHTML = "";
  const hasRenders = state.renders.length > 0;

  elements.exportsScopeButton.classList.toggle("active-scope", state.renderScope === "exports");
  elements.socialScopeButton.classList.toggle("active-scope", state.renderScope === "social");

  const emptyHint = state.renderScope === "social"
    ? "No social-media exports yet.\n\nCreate one from the terminal with:\n\nvideo-tools social"
    : "No rendered videos yet.\n\nRender an edit from the terminal with:\n\nvideo-tools render";
  elements.rendersEmpty.textContent = emptyHint;

  elements.rendersEmpty.classList.toggle("hidden", hasRenders);

  if (!hasRenders) {
    state.currentRenderFilename = "";
    elements.renderVideo.removeAttribute("src");
    elements.renderVideo.load();
    elements.renderPlayerWrap.classList.add("hidden");
    return;
  }

  if (!state.currentRenderFilename || !state.renders.some((item) => item.filename === state.currentRenderFilename)) {
    state.currentRenderFilename = state.renders[0].filename;
  }

  for (const renderItem of state.renders) {
    const row = document.createElement("div");
    row.className = "render-row";

    const button = document.createElement("button");
    button.type = "button";
    button.className = "render-item";
    if (renderItem.filename === state.currentRenderFilename) {
      button.classList.add("selected");
    }
    button.textContent = renderItem.filename;
    button.addEventListener("click", () => {
      state.currentRenderFilename = renderItem.filename;
      renderRendersList();
    });

    row.append(button);

    if (renderItem.filename === state.currentRenderFilename) {
      const playerSlot = document.createElement("div");
      playerSlot.className = "render-player-slot";
      playerSlot.append(elements.renderPlayerWrap);
      row.append(playerSlot);
    }

    elements.rendersList.append(row);
  }

  const selectedFilename = state.currentRenderFilename;
  if (elements.renderVideo.dataset.currentFile !== selectedFilename) {
    elements.renderVideo.dataset.currentFile = selectedFilename;
    elements.renderVideo.src = renderUrl(selectedFilename);
    elements.renderVideo.load();
  }
  elements.renderPlayerWrap.classList.remove("hidden");
}

async function refreshRenders() {
  const endpoint = state.renderScope === "social" ? "/api/renders-social" : "/api/renders";
  const data = await api(endpoint);
  state.renders = data.renders;
  renderRendersList();
}

async function switchRenderScope(scope) {
  if (state.renderScope === scope) {
    return;
  }
  state.renderScope = scope;
  state.currentRenderFilename = "";
  await refreshRenders();
}

async function switchView(view) {
  state.currentView = view;
  renderView();

  if (view === "renders") {
    await refreshRenders();
  }
}

async function refreshEdits() {
  const data = await api("/api/edits");
  state.edits = data.edits;
  renderEditSelector();
}

async function loadEdit(filename) {
  const documentValue = await api(`/api/edits/${encodeURIComponent(filename)}`);
  state.currentFilename = filename;
  markSaved(documentValue);
}

async function initialize() {
  const [projectData, editData, clipData] = await Promise.all([
    api("/api/project"),
    api("/api/edits"),
    api("/api/clips"),
  ]);

  state.project = projectData;
  state.edits = editData.edits;
  state.clips = clipData.clips;
  state.clipMap = new Map(state.clips.map((clip) => [clip.file, clip]));

  elements.projectLine.textContent = `Project: ${projectData.name} · ${projectData.root}`;

  if (state.edits.length) {
    await loadEdit(state.edits[0].filename);
  } else {
    state.currentFilename = "";
    markSaved({ version: 1, output: "", clips: [] });
  }

  renderClipPicker();
  renderAll();
}

function renderClipPicker() {
  const term = elements.clipSearchInput.value.trim().toLowerCase();
  elements.clipList.innerHTML = "";

  const matches = state.clips.filter((clip) => clip.file.toLowerCase().includes(term));

  if (!matches.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.textContent = "No clips match the current filter.";
    elements.clipList.append(empty);
    return;
  }

  for (const clip of matches) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "clip-option";
    button.innerHTML = `
      <span>
        <strong>${clip.file}</strong>
        <span class="muted">${clip.name}</span>
      </span>
      <span>${clip.duration ? formatSeconds(clip.duration) : "Unknown"}</span>
    `;
    button.addEventListener("click", () => addClipToTimeline(clip));
    elements.clipList.append(button);
  }
}

function addClipToTimeline(clip) {
  const duration = clip.duration || 3;
  state.document.clips.push({
    file: clip.file,
    start: 0,
    end: Math.min(3, duration),
    label: `Sample from ${clip.name}`,
  });
  state.selectedIndex = state.document.clips.length - 1;
  updateDirtyState();
  renderAll();
  elements.clipDialog.close();
}

function handleTimelineAction(index, action) {
  if (action === "select") {
    state.selectedIndex = index;
  } else if (action === "up" && index > 0) {
    [state.document.clips[index - 1], state.document.clips[index]] = [state.document.clips[index], state.document.clips[index - 1]];
    state.selectedIndex = index - 1;
    updateDirtyState();
  } else if (action === "down" && index < state.document.clips.length - 1) {
    [state.document.clips[index + 1], state.document.clips[index]] = [state.document.clips[index], state.document.clips[index + 1]];
    state.selectedIndex = index + 1;
    updateDirtyState();
  } else if (action === "remove") {
    state.document.clips.splice(index, 1);
    if (!state.document.clips.length) {
      state.selectedIndex = -1;
    } else if (state.selectedIndex >= state.document.clips.length) {
      state.selectedIndex = state.document.clips.length - 1;
    } else if (state.selectedIndex === index) {
      state.selectedIndex = Math.min(index, state.document.clips.length - 1);
    }
    updateDirtyState();
  }

  renderAll();
}

function updateSelectedClip(changes) {
  const clip = currentClip();
  if (!clip) {
    return;
  }

  Object.assign(clip, changes);
  updateDirtyState();
  renderAll();
}

function clampClipRange(nextStart, nextEnd) {
  const info = selectedClipInfo();
  const maxDuration = info?.duration ?? nextEnd;
  let start = Math.max(0, nextStart);
  let end = Math.max(start + 0.001, nextEnd);
  if (info?.duration) {
    end = Math.min(end, maxDuration);
    start = Math.min(start, Math.max(0, end - 0.001));
  }
  return {
    start: Number(start.toFixed(3)),
    end: Number(end.toFixed(3)),
  };
}

async function saveCurrentEdit() {
  if (!state.currentFilename) {
    return;
  }

  const response = await api(`/api/edits/${encodeURIComponent(state.currentFilename)}`, {
    method: "PUT",
    body: JSON.stringify({ document: cloneCurrentDocument() }),
  });
  markSaved(response.document);
  showToast(`Saved ${response.filename}`);
}

async function openDialog(mode) {
  if (mode === "new" && state.dirty) {
    const confirmed = window.confirm("Discard unsaved changes and create a new edit?");
    if (!confirmed) {
      return;
    }
  }

  const defaults = await api("/api/edits/defaults");
  state.activeDialogMode = mode;
  state.dialogOutputTouched = false;
  elements.editDialogTitle.textContent = mode === "save-as" ? "Save As" : "New Edit";
  elements.dialogSubmitButton.textContent = mode === "save-as" ? "Save As" : "Create";
  elements.editDialogMessage.textContent = mode === "save-as"
    ? "Save the current in-memory timeline as a new edit file."
    : "Create a new empty timeline draft inside the project edits directory.";
  elements.dialogFilename.value = defaults.filename;
  elements.dialogOutput.value = defaults.output;
  elements.editDialog.showModal();
}

async function submitEditDialog(event) {
  event.preventDefault();

  const filename = elements.dialogFilename.value.trim();
  const output = elements.dialogOutput.value.trim();

  if (state.activeDialogMode === "new") {
    const response = await api("/api/edits", {
      method: "POST",
      body: JSON.stringify({ filename, output }),
    });
    await refreshEdits();
    state.currentFilename = response.filename;
    state.selectedIndex = -1;
    markSaved(response.document);
    showToast(`Created ${response.filename}`);
  } else {
    const documentValue = cloneCurrentDocument();
    documentValue.output = output;
    const response = await api(`/api/edits/${encodeURIComponent(state.currentFilename)}/save-as`, {
      method: "POST",
      body: JSON.stringify({ filename, document: documentValue }),
    });
    await refreshEdits();
    state.currentFilename = response.filename;
    markSaved(response.document);
    showToast(`Saved as ${response.filename}`);
  }

  elements.editDialog.close();
}

async function submitRenameDialog(event) {
  event.preventDefault();
  const filename = elements.renameFilename.value.trim();
  const response = await api(`/api/edits/${encodeURIComponent(state.currentFilename)}/rename`, {
    method: "POST",
    body: JSON.stringify({ filename }),
  });
  await refreshEdits();
  state.currentFilename = response.filename;
  renderAll();
  elements.renameDialog.close();
  showToast(`Renamed to ${response.filename}`);
}

async function handleDelete() {
  if (!state.currentFilename) {
    return;
  }

  const confirmed = window.confirm(
    `Delete ${state.currentFilename}?\n\nThis only deletes the edit JSON. Rendered videos are not deleted.`
  );
  if (!confirmed) {
    return;
  }

  await api(`/api/edits/${encodeURIComponent(state.currentFilename)}`, { method: "DELETE" });
  const deletedName = state.currentFilename;
  await refreshEdits();

  if (state.edits.length) {
    await loadEdit(state.edits[0].filename);
  } else {
    state.currentFilename = "";
    state.selectedIndex = -1;
    markSaved({ version: 1, output: "", clips: [] });
  }

  showToast(`Deleted ${deletedName}`);
}

async function handleEditSelection(event) {
  const filename = event.target.value;
  if (!filename || filename === state.currentFilename) {
    return;
  }

  if (state.dirty && !window.confirm("Discard unsaved changes and load another edit?")) {
    renderEditSelector();
    return;
  }

  await loadEdit(filename);
}

elements.outputInput.addEventListener("input", (event) => {
  state.document.output = event.target.value;
  updateDirtyState();
});

elements.editSelect.addEventListener("change", (event) => {
  handleEditSelection(event).catch(reportError);
});

elements.saveButton.addEventListener("click", () => saveCurrentEdit().catch(reportError));
elements.newButton.addEventListener("click", () => openDialog("new").catch(reportError));
elements.saveAsButton.addEventListener("click", () => openDialog("save-as").catch(reportError));
elements.addClipButton.addEventListener("click", () => elements.clipDialog.showModal());
elements.deleteButton.addEventListener("click", () => handleDelete().catch(reportError));
elements.viewEditButton.addEventListener("click", () => {
  switchView("edit").catch(reportError);
});
elements.viewRendersButton.addEventListener("click", () => {
  switchView("renders").catch(reportError);
});
elements.refreshRendersButton.addEventListener("click", () => {
  refreshRenders().catch(reportError);
});
elements.exportsScopeButton.addEventListener("click", () => {
  switchRenderScope("exports").catch(reportError);
});
elements.socialScopeButton.addEventListener("click", () => {
  switchRenderScope("social").catch(reportError);
});

elements.renameButton.addEventListener("click", () => {
  if (state.dirty) {
    showToast("Save or Save As before renaming this edit.");
    return;
  }
  elements.renameFilename.value = state.currentFilename;
  elements.renameDialog.showModal();
});

elements.dialogFilename.addEventListener("input", () => {
  if (!state.dialogOutputTouched) {
    elements.dialogOutput.value = deriveSuggestedOutput(elements.dialogFilename.value.trim());
  }
});

elements.dialogOutput.addEventListener("input", () => {
  state.dialogOutputTouched = true;
});

elements.editDialogForm.addEventListener("submit", (event) => submitEditDialog(event).catch(reportError));
elements.dialogCancelButton.addEventListener("click", () => elements.editDialog.close());

elements.renameDialogForm.addEventListener("submit", (event) => submitRenameDialog(event).catch(reportError));
elements.renameCancelButton.addEventListener("click", () => elements.renameDialog.close());

elements.clipSearchInput.addEventListener("input", renderClipPicker);
elements.clipCancelButton.addEventListener("click", () => elements.clipDialog.close());

elements.startRange.addEventListener("input", (event) => {
  const clip = currentClip();
  if (!clip) {
    return;
  }
  const next = clampClipRange(Number(event.target.value), clip.end);
  updateSelectedClip(next);
});

elements.endRange.addEventListener("input", (event) => {
  const clip = currentClip();
  if (!clip) {
    return;
  }
  const next = clampClipRange(clip.start, Number(event.target.value));
  updateSelectedClip(next);
});

elements.startInput.addEventListener("input", (event) => {
  const clip = currentClip();
  if (!clip) {
    return;
  }
  const next = clampClipRange(Number(event.target.value), clip.end);
  updateSelectedClip(next);
});

elements.endInput.addEventListener("input", (event) => {
  const clip = currentClip();
  if (!clip) {
    return;
  }
  const next = clampClipRange(clip.start, Number(event.target.value));
  updateSelectedClip(next);
});

elements.labelInput.addEventListener("input", (event) => {
  updateSelectedClip({ label: event.target.value });
});

elements.setStartButton.addEventListener("click", () => {
  const clip = currentClip();
  if (!clip) {
    return;
  }
  const next = clampClipRange(elements.previewVideo.currentTime, clip.end);
  updateSelectedClip(next);
});

elements.setEndButton.addEventListener("click", () => {
  const clip = currentClip();
  if (!clip) {
    return;
  }
  const next = clampClipRange(clip.start, elements.previewVideo.currentTime);
  updateSelectedClip(next);
});

elements.playSelectionButton.addEventListener("click", async () => {
  const clip = currentClip();
  if (!clip) {
    return;
  }
  state.playbackStopAt = clip.end;
  elements.previewVideo.currentTime = clip.start;
  await elements.previewVideo.play();
});

elements.previewVideo.addEventListener("timeupdate", () => {
  elements.currentPosition.textContent = formatSeconds(elements.previewVideo.currentTime);
  if (state.playbackStopAt !== null && elements.previewVideo.currentTime >= state.playbackStopAt) {
    elements.previewVideo.pause();
    state.playbackStopAt = null;
  }
});

window.addEventListener("beforeunload", (event) => {
  if (!state.dirty) {
    return;
  }
  event.preventDefault();
  event.returnValue = "";
});

function reportError(error) {
  console.error(error);
  showToast(error.message);
}

initialize().catch(reportError);