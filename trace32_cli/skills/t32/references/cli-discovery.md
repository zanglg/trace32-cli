# CLI discovery

Do not duplicate the installed CLI reference in the Skill. Discover it from the executable.

```bash
t32 --json capabilities
t32 --json schema
```

Configuration discovery and verification:

```bash
t32
t32 --json profile current
t32 --json doctor
```

Bare `t32` is read-only and shows the resolved project root, profile, endpoint, and config files. Project config is the nearest ancestor `.trace32/config.toml`; persistent configuration has only user and project levels.

Setup verification ends at `doctor`. Attaching to the target, changing target state, or running self-tests belongs to later debugging/regression work.

Connected backend/runtime discovery:

```bash
t32 --json backend capabilities
t32 --json target info
t32 --json exec state
t32 --json context current
t32 --json reg list --core 0
t32 --json bp enums
```

When TRACE32 OS-awareness is configured:

```bash
t32 --json context task-current
t32 --json context task-list
t32 --json frame current
```

`backend capabilities` describes connected Layer 0 services/features. `schema` describes command availability; a command existing in `schema` does not prove that a particular PowerView/target/runtime supports the operation.

Stop-reason results include source/confidence metadata. Preserve `unknown` when the backend cannot prove an external stop cause.

Self-test plans:

```bash
t32 test
t32 test --memory
t32 test --extended
t32 test --execution
t32 test --all
```

The default plan is observation-only. `--memory` automatically initializes a dedicated 256-byte host-side TRACE32 `VM:` scratch range and exercises the current Layer 1 → Layer 0 memory path without writing target RAM. `--extended` adds temporary breakpoint state; `--execution` adds Break/Step/Go; `--all` runs every registered suite.

For machine parsing:

```bash
t32 --json test --all
```

For human drill-down:

```bash
t32 --help
t32 <resource> --help
t32 <resource> <action> --help
```
