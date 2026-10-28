/* Saves originals and searchable metadata into the selected directory. */
(function (root) {
  'use strict';
  async function saveLocalUpload(directory, { file, metadata }) {
    if (!file || !/\.(pdf|html?)$/i.test(file.name) || !file.size || file.size > 20 * 1024 * 1024) {
      throw new Error('Choose a nonempty PDF or HTML file of at most 20 MB.');
    }
    const metadataName = `${file.name}.metadata.json`;
    for (const name of [file.name, metadataName]) {
      try {
        await directory.getFileHandle(name);
      } catch (error) {
        if (error.name === 'NotFoundError') continue;
        throw error;
      }
      throw new Error(`${name} already exists. Rename the selected file or choose another folder.`);
    }
    async function write(name, content) {
      const handle = await directory.getFileHandle(name, { create: true });
      const stream = await handle.createWritable();
      try {
        await stream.write(content);
        await stream.close();
      } catch (error) {
        try { await stream.abort(); } catch { /* Preserve the write error. */ }
        throw error;
      }
    }
    try {
      await write(file.name, file);
      await write(metadataName, JSON.stringify({ ...metadata, filename: file.name }, null, 2));
    } catch (error) {
      throw new Error(`Save did not finish. Check the chosen folder for partial files before retrying. ${error.message}`);
    }
    return { filename: file.name, metadataFilename: metadataName };
  }
  if (typeof module !== 'undefined' && module.exports) module.exports = saveLocalUpload;
  else root.saveLocalUpload = saveLocalUpload;
})(globalThis);
