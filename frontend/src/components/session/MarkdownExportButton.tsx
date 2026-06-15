import { useState } from "react";
import { Button } from "../ui/Button";
import { Api } from "../../api/endpoints";
import { downloadText } from "../../utils/clipboard";

export function MarkdownExportButton({
  sessionId,
  title,
}: {
  sessionId: string;
  title: string;
}) {
  const [busy, setBusy] = useState(false);

  const exportMd = async () => {
    setBusy(true);
    try {
      const { markdown } = await Api.exportMarkdown(sessionId);
      const safe = title.replace(/[^\w-]+/g, "_").slice(0, 40) || "session";
      downloadText(`council-${safe}.md`, markdown);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Button size="sm" variant="secondary" loading={busy} onClick={exportMd}>
      Markdown-Export
    </Button>
  );
}
