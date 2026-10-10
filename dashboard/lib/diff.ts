// Line diff (longest common subsequence) for the "SOP cũ → mới" view. SOPs are short, O(n·m) is fine.

export type DiffLine = { kind: "same" | "add" | "del"; text: string };

function lines(s: string): string[] {
  const t = s.replace(/\r\n/g, "\n").replace(/\n+$/, "");
  return t === "" ? [] : t.split("\n");
}

export function diffLines(oldText: string, newText: string): DiffLine[] {
  const a = lines(oldText);
  const b = lines(newText);
  const n = a.length;
  const m = b.length;
  // lcs[i][j] = LCS length of a[i:] and b[j:]
  const lcs: number[][] = Array.from({ length: n + 1 }, () => new Array<number>(m + 1).fill(0));
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      lcs[i][j] = a[i] === b[j] ? lcs[i + 1][j + 1] + 1 : Math.max(lcs[i + 1][j], lcs[i][j + 1]);
    }
  }
  const out: DiffLine[] = [];
  let i = 0;
  let j = 0;
  while (i < n && j < m) {
    if (a[i] === b[j]) {
      out.push({ kind: "same", text: a[i] });
      i++;
      j++;
    } else if (lcs[i + 1][j] >= lcs[i][j + 1]) {
      out.push({ kind: "del", text: a[i++] });
    } else {
      out.push({ kind: "add", text: b[j++] });
    }
  }
  while (i < n) out.push({ kind: "del", text: a[i++] });
  while (j < m) out.push({ kind: "add", text: b[j++] });
  return out;
}

export function diffStats(d: DiffLine[]): { added: number; removed: number; changed: boolean } {
  const added = d.filter((l) => l.kind === "add").length;
  const removed = d.filter((l) => l.kind === "del").length;
  return { added, removed, changed: added + removed > 0 };
}
