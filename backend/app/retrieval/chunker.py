import re


BOUNDARY_RE = re.compile(r"(?m)(^#{1,6}\s+.+$|^\s*[-*]\s+.+$|\n{2,}|(?<=[。！？.!?])\s+)")


def boundary_aware_chunks(text: str, chunk_size: int, overlap: int) -> list[str]:
    normalized = re.sub(r"[ \t]+", " ", text).strip()
    if not normalized:
        return []
    parts = [part.strip() for part in BOUNDARY_RE.split(normalized) if part and part.strip()]
    chunks: list[str] = []
    current = ""
    for part in parts:
        if len(current) + len(part) + 1 <= chunk_size:
            current = f"{current}\n{part}".strip()
            continue
        if current:
            chunks.append(current)
        if len(part) <= chunk_size:
            current = part
        else:
            start = 0
            while start < len(part):
                end = min(len(part), start + chunk_size)
                chunks.append(part[start:end].strip())
                if end == len(part):
                    break
                start = max(0, end - overlap)
            current = ""
    if current:
        chunks.append(current)
    if overlap <= 0 or len(chunks) <= 1:
        return chunks
    merged = [chunks[0]]
    for index in range(1, len(chunks)):
        prefix = chunks[index - 1][-overlap:]
        merged.append(f"{prefix}\n{chunks[index]}".strip())
    return merged
