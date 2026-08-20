---
name: codingstars-code-style
description: CodingStars code formatting and comment conventions. Use this skill whenever writing or editing CSS, Python, JS, or any code file for Robert or the CodingStars codebase. Covers comment headers, section markers, source references, and documentation style. Trigger on any code generation, file creation, or code editing task — even if the user doesn't mention formatting explicitly.
---

# CodingStars Code Style

Robert's codebases follow a strict comment and documentation style.
Apply these rules to **every** code file you write or edit.


## Comment Headers

### Section headers — three dashes

```
/* --- Section Name ---
   Optional explanation of what this section does and why.
   Ref: https://relevant-docs-url */
```

- Three dashes on each side: `---`
- Title on the first line, explanation on subsequent lines
- Always end with a `Ref:` link if one exists
- Multiple refs get their own lines:
  ```
  /* --- Composer Bar ---
     The input + overlaid buttons.
     Ref: https://docs.streamlit.io/develop/api-reference/chat/st.chat_input
     Ref: https://developer.mozilla.org/en-US/docs/Web/CSS/position */
  ```

### Sub-headers — two dashes

```
/* -- Short explanation of what follows -- */
```

- Two dashes on each side: `--`
- Single line, keeps it scannable
- Used inside a section to label individual rules or groups

### What NOT to do

```
/* ========================================================================
   NEVER USE THESE PLATE-STYLE HEADERS
   ======================================================================== */

/* *** Or star-box headers *** */

// Section 9a — no lettered/numbered sub-sections
```

- No plate/box headers with `====` or `****`
- No numbered sub-sections like `9a`, `9b`, `9c`
- No `#region` / `#endregion` style markers


## Source References

Every non-trivial pattern MUST link to its documentation source.

### Format

```
/* Ref: https://developer.mozilla.org/en-US/docs/Web/CSS/position */
```

### Where refs go

- **Inside section headers** — when the whole section is about one concept
- **Inline above a rule** — when a specific rule uses a non-obvious technique
- **In the project's SOURCES.md** — add a row when introducing a new pattern

### Common sources to link

| Domain | Base URL |
|--------|----------|
| CSS/HTML | `https://developer.mozilla.org/en-US/docs/Web/CSS/...` |
| Streamlit | `https://docs.streamlit.io/develop/api-reference/...` |
| Python | `https://docs.python.org/3/library/...` |
| Angular | `https://angular.io/api/...` |
| .NET/C# | `https://learn.microsoft.com/en-us/dotnet/api/...` |

Search for the real URL — don't guess or fabricate.


## Comment Content Rules

1. **Explain WHY, not WHAT** — the code shows what; the comment says why
   ```css
   /* GOOD: */
   /* -- Streamlit wraps each widget in nested divs; flatten them to
      a single flex row so the pill + settings sit side by side -- */

   /* BAD: */
   /* -- Set display to flex and direction to row -- */
   ```

2. **Keep structural comments** — layout diagrams in ASCII are encouraged:
   ```css
   /* Layout at rest:
        [ ... Message QueryMaster ...    🤖 SQL Assistant  ⚙  ↑ ]
                                         ├── composer_bar ──────┤ */
   ```

3. **Tag Streamlit internals** — when targeting a `data-testid`, note which
   Streamlit component it belongs to so future-you can grep it:
   ```css
   /* -- stChatInputSubmitButton: Streamlit's built-in send arrow -- */
   ```


## Python Files

Same header conventions, adapted to `#` comments:

```python
# --- Constants ---

# -- Agent display names for the UI --
# Ref: https://docs.streamlit.io/develop/api-reference/chat

AGENT_DISPLAY = { ... }
```

```python
# --- Style loader ---
# Ref: https://discuss.streamlit.io/t/custom-css-in-streamlit/4012

def load_styles():
    ...
```


## File-Level Header

Every file starts with a one-line docstring or comment saying what it does:

```python
"""QueryMaster - Streamlit chat interface.

Ref: https://docs.streamlit.io/develop/api-reference/chat
Ref: https://docs.streamlit.io/develop/api-reference/caching/st.session_state
"""
```

```css
/* --- QueryMaster - Themed Chat Interface ---
   Colors come from CSS variables set at runtime by load_styles() in app.py.
   Ref: https://developer.mozilla.org/en-US/docs/Web/CSS/Using_CSS_custom_properties */
```


## Quick Checklist

Before delivering any code file, verify:

- [ ] Section headers use `/* --- Name --- */` (three dashes)
- [ ] Sub-headers use `/* -- text -- */` (two dashes)
- [ ] No plate/box headers anywhere
- [ ] Every non-trivial pattern has a `Ref:` URL
- [ ] Refs are real URLs, not fabricated
- [ ] Comments explain WHY, not WHAT
- [ ] No numbered sub-sections (9a, 9b, etc.)
