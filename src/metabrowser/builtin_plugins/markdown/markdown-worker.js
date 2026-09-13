import { runMarkdownOperation } from "./markdown-worker-operations.js";

self.onmessage = async (event) => {
  const message = event.data;
  if (
    !message ||
    typeof message !== "object" ||
    typeof message.id !== "number" ||
    !Number.isSafeInteger(message.id)
  ) {
    return;
  }
  try {
    const result = await runMarkdownOperation(message.op, message.payload);
    self.postMessage({ id: message.id, result });
  } catch (error) {
    const value = error && typeof error === "object" ? error : null;
    self.postMessage({
      error: {
        code: value && "code" in value && typeof value.code === "string" ? value.code : undefined,
        message: error instanceof Error ? error.message : String(error),
        name: error instanceof Error ? error.name : "Error",
      },
      id: message.id,
    });
  }
};
