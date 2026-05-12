# MaCode — Math Animation Harness

You are working in MaCode, a UNIX-native math animation Harness. All tools are independent CLIs invoked via standard Bash.

## Allowed Operations (execute freely)

**Read-only / Info:**
- `macode status`, `macode inspect`, `macode engine`
- `ls`, `cat`, `jq`, `tail`, `head`, `find`, `grep`, `du -sh`, `ps`
- `ffprobe`, `manim --version`, `ffmpeg -version`, `node --version`
- `python3 bin/discover`
- `python3 bin/signal-check.py [--scene <name>|--global-only]` — Query human-intervention signals

**Checks / Validation:**
- `macode check <scene>`, `macode report <scene>`, `macode timeline`
- `macode test <unit|integration|smoke>`
- `macode dry-run <scene_file>`

**Rendering / Production:**
- `macode render <scene>`, `macode render-all`, `macode dev <scene>`
- `pipeline/render.sh`, `pipeline/preview.sh`, `pipeline/deliver.sh`
- `pipeline/concat.sh`, `pipeline/add_audio.sh`, `pipeline/compress.sh`
- `pipeline/fade.sh`, `pipeline/thumbnail.sh`, `pipeline/smart-cut.sh`

**Maintenance:**
- `macode cleanup [--dry-run]`
- `python3 bin/cleanup-stale.py [--dry-run]`
- `git status`, `git diff`, `git log`
- `git add scenes/*`, `git commit -m "..."`

## Require Confirmation (ask before executing)

- `rm -rf`, `sudo`, `pip install`, `npm install`
- `git push`, `git reset --hard`, `git clean -fd`
- `curl`, `wget`
- Modifying files in `engines/`, `bin/`, `pipeline/`

## Never Do

- Access `.git/config`, `.macode/`, `.claude/`
- Modify engine adapter code (`engines/*/src/`, `bin/`, `pipeline/`)
- Install packages globally
- Force-push or reset Git history
- Use `subprocess`, `os.system`, `socket`, `requests` in scene code
