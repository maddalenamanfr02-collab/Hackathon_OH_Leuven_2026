# Standalone upload controller

## Calendar date field

Open `upload-metadata.html` for the standalone local upload form. Copy its
labelled `type="date"` field into your upload form. The browser supplies calendar
navigation; its appearance and month/year controls depend on the browser and
device. Users can also enter a date using the browser's date segments.
`upload-metadata.js` adds an explicit calendar button where supported.

Read `form.elements.namedItem('date').value` when calling `uploader.upload`.
Although the visible date follows the user's locale, this value is always
`YYYY-MM-DD` (or empty). Pass that string directly, without timezone conversion.
The field starts empty and is required; no date is silently chosen for the user.
Choose a local folder, select a PDF/HTML file, fill all three fields, then click
**Upload to local folder**. The page saves the original plus a sibling
`<filename>.metadata.json` containing name, date, title and filename. Existing
names are rejected. Each upload accepts one nonempty file of at most 20 MB.
Folder access must be granted again after reopening the page. Use Chrome/Edge
on localhost or HTTPS if folder selection is unavailable. No network upload occurs.
Two file writes are not atomic: a failure can leave partial files; inspect the
folder before retrying. Avoid simultaneous uploads from other tabs to this folder.

## Storage integration

Load `upload-controller.js` before your interface script. It exposes
`UploadController` (also available through `require` in Node.js).

Each document requires explicit `name`, `date`, and `title` strings. Whitespace
is trimmed; blank values and impossible dates are rejected. Dates use
`YYYY-MM-DD`. Name is a separate metadata value, not automatically the filename;
the interface should label its intended meaning. No author or publication-date
meaning is assumed by this module.

```js
const uploader = UploadController.createUploadController(async ({ file, metadata }) => {
  // Replace with your storage/backend adapter. Persist BOTH the file and metadata.
  return documentStore.save({ file, ...metadata });
});

async function submitUpload(file, name, date, title) {
  try {
    const outcome = await uploader.upload(file, { name, date, title });
    if (!outcome.ok) {
      // Display outcome.errors beside the relevant fields, using textContent.
      return outcome;
    }
    return outcome;
  } catch (error) {
    // Display a save failure and retain the user's field values for retry.
    throw error;
  }
}
```

Invalid submissions never call storage. Concurrent submissions on the same
controller return `busy`. Save failures propagate and release the controller
for retry. A successful result means the supplied adapter resolved; it does not
mean the document has been indexed.

The standalone form wires the controller to `upload-local-storage.js`, which
persists these metadata fields. It remains independent of the main interface.
The search algorithm still needs to read the JSON metadata and index documents.
