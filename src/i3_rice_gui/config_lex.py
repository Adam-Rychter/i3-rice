"""Position-preserving masking for supported configuration syntaxes."""


def mask_comments_and_strings(
    text: str, *, hash_comments: bool, single_quotes: bool = False,
    nested_comments: bool = False,
) -> str:
    result = list(text)
    i = 0
    while i < len(text):
        start = i
        quote = text[i] if text[i] == '"' or (single_quotes and text[i] == "'") else None
        if quote:
            i += 1
            while i < len(text):
                if text[i] == "\\":
                    i += 2
                elif text[i] == quote:
                    i += 1
                    break
                else:
                    i += 1
            else:
                raise ValueError("Unterminated string requires manual review.")
        elif text.startswith("/*", i):
            i += 2
            depth = 1
            while i < len(text) and depth:
                if nested_comments and text.startswith("/*", i):
                    depth += 1
                    i += 2
                elif text.startswith("*/", i):
                    depth -= 1
                    i += 2
                else:
                    i += 1
            if depth:
                raise ValueError("Unterminated comment requires manual review.")
        elif (hash_comments and text[i] == "#") or text.startswith("//", i):
            newline = text.find("\n", i)
            i = len(text) if newline == -1 else newline
        else:
            i += 1
            continue
        for index in range(start, min(i, len(text))):
            if text[index] not in "\r\n":
                result[index] = " "
    return "".join(result)
