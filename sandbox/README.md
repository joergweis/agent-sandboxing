# Claude Code in an MXC sandbox on Windows

Runs Claude Code (with git, Git Bash, Node/npx, plugins and MCP servers) inside a
**Microsoft Execution Containers ProcessContainer** (AppContainer-based) on a
developer's own Windows machine.

```
 Developer terminal
   └─ Start-ClaudeSandbox.ps1
        ├─ egress-proxy.mjs   (host, 127.0.0.1:18080, hostname allowlist, logs every decision)
        └─ wxc-exec.exe policy.json
             └─ [ MXC ProcessContainer ]
                  claude.exe ─┬─ bash.exe / git.exe
                              ├─ node / npx  (MCP servers, plugins)
                              └─ anything else it spawns (all inherit the container)
```

## What the agent can and cannot touch

| Resource | Inside the sandbox |
|---|---|
| Project folder | read/write |
| Its own home, `.claude` config, plugins, temp, npm cache | read/write, **private per sandbox** (`%LOCALAPPDATA%\agent-sandboxes\<name>`) |
| Git, Git Bash, Node, claude.exe | read-only |
| Your real profile (`.ssh`, `.azure`, `.aws`, browser profiles, the host's `~\.claude`) | no access (deny-by-default, plus explicit denies) |
| Host environment variables | none. The env block is supplied verbatim |
| Network | no direct sockets. HTTP(S) only via the proxy, only to hosts in `allowlist.txt` |
| Clipboard, UI, input injection | disabled |
| `git push` | no credentials inside. The agent commits and a human pushes from the host |

## Setup (once per machine)

Requires Windows 11 24H2/25H2 with the Aug 2026 update (build 26100.9278 / 26200.9278) or newer.

```powershell
# Claude Code (native installer), Git for Windows and Node must already be installed on the host
cd <repo>\sandbox
npm install @microsoft/mxc-sdk          # ships wxc-exec.exe
```

## Run

```powershell
# Interactive session (TUI). Run /login once; the credentials stay in the sandbox's private config dir
.\Start-ClaudeSandbox.ps1 -Workspace C:\src\my-repo

# Or with a per-developer API key from the host
.\Start-ClaudeSandbox.ps1 -Workspace C:\src\my-repo -PassApiKey

# Headless / CI-style
.\Start-ClaudeSandbox.ps1 -Workspace C:\src\my-repo -ClaudeArgs '-p','run the tests and fix failures'

# Extra toolchains (read-only)
.\Start-ClaudeSandbox.ps1 -Workspace C:\src\my-repo -ExtraReadOnly 'C:\Python313','C:\Program Files\dotnet'
```

## Tuning the policy

1. **`-Mode Learn`**: enforcement stays on and every blocked file or registry access is recorded to
   `logs\denials.json`. This is safe to use with real work.
2. **`-Mode Audit`**: nothing is blocked. You get `denials.json` plus an `Adjusted_*.json`
   suggested policy. Use it **only with trusted repos and prompts**, to bring up a new toolchain.
3. **Network**: every denied host is listed at the end of each session and logged to
   `logs\egress.jsonl`. Add the hosts you need to `allowlist.txt`. It reloads live, so there's no restart.

## Plugins and MCP servers

Run `/plugin` and `claude mcp add ...` **inside** the sandbox. They are written to the sandbox's
private `CLAUDE_CONFIG_DIR` and run inside the container, under the same file and network rules.
npx-based MCP servers need `registry.npmjs.org` (or your internal mirror). Plugin marketplaces
need the GitHub hosts. Both are in the default allowlist.

## Known limits

- **The proxy runs unpackaged on the host.** Because of that, MXC requires `hostLoopback: "allow"`,
  which Microsoft classes as the weaker dev/test variant. MXC still pins the container's egress to the
  proxy endpoint. For a fleet rollout, package the proxy (MSIX) or run it in its own AppContainer, set
  `processContainer.network.allowedProxyPeer`, and switch to `hostLoopback: "deny"`.
- **The proxy filters by hostname only.** It doesn't intercept TLS, so an allowed host is fully
  allowed (e.g. any repo on github.com). For tighter control, point the allowlist at an internal
  Git server and an Artifactory mirror only. It also doesn't chain to a corporate upstream proxy.
- **Some things on the host are not reachable** from inside, by design: Docker Desktop, local databases
  on localhost, and the VS Code/JetBrains Claude extension (its localhost WebSocket). For
  container-heavy work, look at the MXC `wslc` backend.
- **Native Claude Code support for MXC is announced but not shipped.** When it lands, prefer it over
  this wrapper.
