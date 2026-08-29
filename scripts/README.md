# Windows startup and diagnostics

These helper scripts are intended for the local Windows notebook used by the POC.

## After a Windows restart

From the repository root, run:

```powershell
.\start-family-kb.cmd
```

The launcher uses Windows PowerShell with a process-local execution-policy bypass, so it also works on machines where direct `.ps1` execution is blocked.

The startup script:

1. checks whether the Docker CLI is installed,
2. starts Docker Desktop only when the Docker engine is not already running,
3. waits for the Docker engine,
4. runs `docker compose up -d`,
5. waits until the Qdrant REST API answers,
6. verifies that `.venv\Scripts\family-kb.exe` is available.

It does **not** run `git pull`, reinstall Python packages, reindex the knowledge base, or start a benchmark automatically.

Optional diagnostics after startup:

```powershell
.\start-family-kb.cmd -RunDiagnostics
```

## Diagnostics only

Run:

```powershell
.\diagnose-family-kb.cmd
```

This writes a UTF-8 report to:

```text
system_check.txt
```

The report includes:

- WSL status and distributions,
- Docker client/server status,
- Git working-tree status and current HEAD,
- Docker Compose / Qdrant container status,
- Qdrant collections,
- `family-kb --help`,
- virtual-environment Python, package and Torch versions,
- CUDA availability,
- configured KB path and whether it is accessible,
- configured Qdrant collection and embedding model.

The script removes embedded NUL characters from captured native-command output before writing the report, which makes the file easier to upload and inspect.

## Direct PowerShell scripts

The `.cmd` launchers are the recommended entry points. The underlying scripts are:

```text
scripts\start-family-kb.ps1
scripts\diagnose-family-kb.ps1
```

For example:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\diagnose-family-kb.ps1
```
