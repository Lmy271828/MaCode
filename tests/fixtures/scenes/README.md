# tests/fixtures/scenes/

Test-only scene fixtures. **Not** rendered by `macode render-all` or referenced
from user-facing examples.

## Naming convention

Every directory here MUST be prefixed `test_*`. Conversely, `scenes/test_*`
is reserved — production scenes never use the `test_` prefix.

## What lives here

| Fixture | Purpose |
|---------|---------|
| `test_layout_compiler/` | Layout compiler hash-resolution test (`tests/unit/test_macode_hash.py`) |
| `test_self_correction/` | Multi-shot composite self-correction smoke test |
| `test_self_correction_mc/` | Motion Canvas variant of the above |

## Adding a new fixture

1. Create `tests/fixtures/scenes/test_<scenario>/` with `manifest.json` + `scene.py` or `scene.tsx`.
2. Reference it from your test via:
   ```python
   FIXTURE = os.path.join(PROJECT_ROOT, "tests", "fixtures", "scenes", "test_<scenario>")
   ```
3. The fixture is intentionally **excluded** from `bin/render-all.sh` (which
   only scans `scenes/[0-9]*` directories).

## Why not in `scenes/`?

S8 hygiene per PRD: keeping test fixtures alongside production scenes
caused `render-all` noise, `find scenes -name manifest.json` polluting the
inventory, and naming collisions during scene authoring. Separating them
makes `scenes/` exclusively a user-facing artifact.
