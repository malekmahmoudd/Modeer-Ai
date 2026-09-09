import { Fragment, type ReactNode } from "react";

/**
 * Small, dependency-free renderer for the GitHub-flavored markdown that chat
 * models produce: headings, bold/italic/code, ordered + unordered lists,
 * blockquotes, fenced code, horizontal rules and pipe tables. HTML is escaped;
 * only the tags produced here are emitted.
 */

function inline(text: string, keyBase: string): ReactNode[] {
  // Split on the tokens we support, keeping delimiters.
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`|\*[^*]+\*|\[[^\]]+\]\([^)]+\))/g);
  return parts.filter(Boolean).map((p, i) => {
    const key = `${keyBase}-${i}`;
    if (/^\*\*[^*]+\*\*$/.test(p)) return <strong key={key}>{p.slice(2, -2)}</strong>;
    if (/^`[^`]+`$/.test(p)) return <code key={key}>{p.slice(1, -1)}</code>;
    if (/^\*[^*]+\*$/.test(p)) return <em key={key}>{p.slice(1, -1)}</em>;
    const link = p.match(/^\[([^\]]+)\]\(([^)]+)\)$/);
    if (link) {
      const href = link[2];
      const safe = /^(https?:|mailto:|\/)/.test(href) ? href : "#";
      return (
        <a key={key} href={safe} target="_blank" rel="noopener noreferrer">
          {link[1]}
        </a>
      );
    }
    return <Fragment key={key}>{p}</Fragment>;
  });
}

function splitRow(line: string): string[] {
  return line
    .replace(/^\||\|$/g, "")
    .split("|")
    .map((c) => c.trim());
}

export function renderMarkdown(src: string): ReactNode[] {
  const lines = src.replace(/\r\n/g, "\n").split("\n");
  const out: ReactNode[] = [];
  let i = 0;
  let k = 0;

  while (i < lines.length) {
    const line = lines[i];

    // fenced code
    if (/^```/.test(line.trim())) {
      const buf: string[] = [];
      i++;
      while (i < lines.length && !/^```/.test(lines[i].trim())) buf.push(lines[i++]);
      i++;
      out.push(
        <pre
          key={k++}
          className="my-2 overflow-x-auto rounded-[10px] border border-line bg-bg-elev p-3 text-[12.5px] leading-relaxed"
        >
          <code>{buf.join("\n")}</code>
        </pre>,
      );
      continue;
    }

    // blank
    if (!line.trim()) {
      i++;
      continue;
    }

    // horizontal rule
    if (/^(\s*[-*_]){3,}\s*$/.test(line)) {
      out.push(<hr key={k++} className="my-3 border-line" />);
      i++;
      continue;
    }

    // heading
    const h = line.match(/^(#{1,4})\s+(.*)$/);
    if (h) {
      out.push(
        <p key={k++} className="mb-1 mt-3 text-[13.5px] font-semibold text-white first:mt-0">
          {inline(h[2], `h${k}`)}
        </p>,
      );
      i++;
      continue;
    }

    // table (header row + separator)
    if (line.includes("|") && i + 1 < lines.length && /^\s*\|?[\s:|-]+\|?\s*$/.test(lines[i + 1])) {
      const header = splitRow(line);
      i += 2;
      const rows: string[][] = [];
      while (i < lines.length && lines[i].includes("|") && lines[i].trim()) {
        rows.push(splitRow(lines[i]));
        i++;
      }
      out.push(
        <div key={k++} className="my-2 overflow-x-auto">
          <table className="w-full border-collapse text-[12.5px]">
            <thead>
              <tr>
                {header.map((c, ci) => (
                  <th
                    key={ci}
                    className="border-b border-line-strong px-2.5 py-1.5 text-left font-semibold text-white"
                  >
                    {inline(c, `th${k}-${ci}`)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r, ri) => (
                <tr key={ri}>
                  {r.map((c, ci) => (
                    <td key={ci} className="border-b border-line px-2.5 py-1.5 align-top text-content-dim">
                      {inline(c, `td${k}-${ri}-${ci}`)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>,
      );
      continue;
    }

    // blockquote
    if (/^\s*>\s?/.test(line)) {
      const buf: string[] = [];
      while (i < lines.length && /^\s*>\s?/.test(lines[i])) {
        buf.push(lines[i].replace(/^\s*>\s?/, ""));
        i++;
      }
      out.push(
        <blockquote
          key={k++}
          className="my-2 border-l-2 border-line-strong pl-3 text-content-dim"
        >
          {inline(buf.join(" "), `q${k}`)}
        </blockquote>,
      );
      continue;
    }

    // list
    if (/^\s*([-*+]|\d+[.)])\s+/.test(line)) {
      const ordered = /^\s*\d+[.)]\s+/.test(line);
      const items: string[] = [];
      while (i < lines.length && /^\s*([-*+]|\d+[.)])\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^\s*([-*+]|\d+[.)])\s+/, ""));
        i++;
      }
      const List = ordered ? "ol" : "ul";
      out.push(
        <List key={k++} className={ordered ? "my-2 list-decimal pl-5" : "my-2 list-disc pl-5"}>
          {items.map((it, ii) => (
            <li key={ii} className="my-0.5">
              {inline(it, `li${k}-${ii}`)}
            </li>
          ))}
        </List>,
      );
      continue;
    }

    // paragraph (gather consecutive non-empty, non-special lines)
    const buf: string[] = [line];
    i++;
    while (
      i < lines.length &&
      lines[i].trim() &&
      !/^(#{1,4}\s|\s*([-*+]|\d+[.)])\s|\s*>\s?|```|(\s*[-*_]){3,}\s*$)/.test(lines[i])
    ) {
      buf.push(lines[i]);
      i++;
    }
    out.push(
      <p key={k++} className="my-2 first:mt-0 last:mb-0">
        {inline(buf.join(" "), `p${k}`)}
      </p>,
    );
  }

  return out;
}
