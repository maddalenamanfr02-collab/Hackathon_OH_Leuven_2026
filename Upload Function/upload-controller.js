/* Standalone upload rules: usable in a browser or with Node.js. */
(function (root) {
  'use strict';

  function validateMetadata(input) {
    const metadata = {};
    const errors = {};
    for (const field of ['name', 'date', 'title']) {
      metadata[field] = typeof input?.[field] === 'string' ? input[field].trim() : '';
      if (!metadata[field]) errors[field] = `${field} is required.`;
    }
    if (metadata.date) {
      const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(metadata.date);
      const parsed = new Date(`${metadata.date}T00:00:00Z`);
      if (!match || match[1] === '0000' || !Number.isFinite(parsed.getTime()) ||
          parsed.toISOString().slice(0, 10) !== metadata.date) {
        errors.date = 'Enter a valid date in YYYY-MM-DD format.';
      }
    }
    return { valid: Object.keys(errors).length === 0, metadata, errors };
  }

  // The adapter owns file storage and metadata persistence. It must resolve
  // only after both have been saved, and reject if saving fails.
  function createUploadController(save) {
    if (typeof save !== 'function') throw new TypeError('A save function is required.');
    let busy = false;
    return {
      validateMetadata,
      async upload(file, input) {
        const validation = validateMetadata(input);
        if (!file) validation.errors.file = 'Choose a file to upload.';
        if (Object.keys(validation.errors).length) {
          return { ok: false, status: 'invalid', errors: validation.errors };
        }
        if (busy) return { ok: false, status: 'busy', errors: { upload: 'An upload is already in progress.' } };
        busy = true;
        try {
          const result = await save({ file, metadata: validation.metadata });
          return { ok: true, status: 'saved', metadata: validation.metadata, result };
        } finally {
          busy = false;
        }
      }
    };
  }

  const api = { validateMetadata, createUploadController };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.UploadController = api;
})(globalThis);
