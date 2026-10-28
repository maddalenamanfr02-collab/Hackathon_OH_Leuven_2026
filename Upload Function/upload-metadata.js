'use strict';

const metadataForm = document.getElementById('upload-metadata');
const dateInput = metadataForm.elements.namedItem('date');
const calendarButton = document.getElementById('choose-date');
const metadataStatus = document.getElementById('metadata-status');
const folderButton = document.getElementById('choose-folder');
const uploadButton = document.getElementById('upload-button');
const folderStatus = document.getElementById('folder-status');
let directory;
let saving = false;
const uploader = UploadController.createUploadController((payload) => saveLocalUpload(directory, payload));

if (!window.isSecureContext || typeof window.showDirectoryPicker !== 'function') {
  folderButton.disabled = true;
  folderStatus.textContent = 'Folder saving is unavailable here. Open this page in Chrome or Edge using localhost or HTTPS.';
}
folderButton.addEventListener('click', async () => {
  try {
    const selected = await window.showDirectoryPicker({ mode: 'readwrite' });
    directory = selected;
    folderStatus.textContent = `Selected folder: ${directory.name}`;
    uploadButton.disabled = false;
  } catch (error) {
    if (error.name !== 'AbortError') metadataStatus.textContent = `Could not select folder: ${error.message}`;
  }
});

if (typeof dateInput.showPicker === 'function') {
  calendarButton.hidden = false;
  calendarButton.addEventListener('click', () => {
    try { dateInput.showPicker(); }
    catch { dateInput.focus(); }
  });
}

metadataForm.addEventListener('input', () => { metadataStatus.textContent = ''; });
metadataForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  if (saving || !directory) return;
  const values = Object.fromEntries(new FormData(metadataForm));
  const result = UploadController.validateMetadata(values);
  if (!result.valid) {
    metadataStatus.textContent = Object.values(result.errors).join(' ');
    metadataForm.elements.namedItem(Object.keys(result.errors)[0]).focus();
    return;
  }
  saving = true;
  const controls = Array.from(metadataForm.elements);
  const disabledStates = controls.map((control) => control.disabled);
  controls.forEach((control) => { control.disabled = true; });
  metadataStatus.textContent = 'Saving file and metadata…';
  try {
    const outcome = await uploader.upload(values.file, result.metadata);
    metadataStatus.textContent = outcome.ok
      ? `Saved ${outcome.result.filename} and its metadata in ${directory.name}.`
      : Object.values(outcome.errors).join(' ');
  } catch (error) {
    metadataStatus.textContent = error.message;
  } finally {
    controls.forEach((control, index) => { control.disabled = disabledStates[index]; });
    saving = false;
  }
});
