import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { cn } from "../../utils/cn";

export function Markdown({ content, className }: { content: string; className?: string }) {
  const text = (content ?? "").trim();
  if (!text) {
    return <p className="text-sm italic text-slate-400">Kein Inhalt.</p>;
  }
  return (
    <div className={cn("prose-council", className)}>
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{text}</ReactMarkdown>
    </div>
  );
}
