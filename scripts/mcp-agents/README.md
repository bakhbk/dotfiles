# mcp-agents

MCP servers config shared by AI agents (VS Code Copilot, pi, etc.).

- `mcp.json` — reference config (copy into `.vscode/mcp.json`).
- `setup.sh` — installs/removes the packages behind it.
- `check.py` — smoke test: every server must answer `tools/list`.

```bash
bash setup.sh              # install
bash setup.sh reinstall    # reinstall
bash setup.sh uninstall    # remove everything
```

Optional toolchains: `go` (gopls MCP, built into gopls), `dart` (built-in MCP server).

## Verify

```bash
bash -n setup.sh
python3 -m json.tool mcp.json
./check.py               # spawns every server, initialize + tools/list
```

## Notes

- Servers are launched on demand via `npx -y` / `uvx`; setup.sh pre-installs them and downloads Chromium for `playwright`.
- `figma-bridge` reads design data through a Figma plugin (WebSocket to the desktop app), no API key needed.
- No secrets in `mcp.json` — any token added later belongs in `env`, not in the repo.
