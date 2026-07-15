/** Manifest V3 worker: convert Markdown locally and download the DOCX. */
importScripts("md2docx.js");

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message.type === "CONVERT") {
    handleConvert(message).then(sendResponse);
    return true;
  }
  return false;
});

async function handleConvert({ markdown, filename = "result.docx" }) {
  try {
    const bytes = self.Md2Docx.convert(markdown, {
      font: "Arial",
      baseFont: "Times New Roman",
    });
    const base64 = self.Md2Docx.toBase64(bytes);
    const url = `data:application/vnd.openxmlformats-officedocument.wordprocessingml.document;base64,${base64}`;
    await chrome.downloads.download({ url, filename, saveAs: false });
    return { ok: true };
  } catch (error) {
    return { ok: false, error: `Local conversion failed: ${error.message}` };
  }
}
