# CLI discovery

Do not duplicate the installed CLI reference in the Skill. Discover it from the executable.

```bash
t32 --json capabilities
t32 --json schema
```

Configuration/connectivity verification:

```bash
t32 --json profile current
t32 --json doctor
```

Setup verification ends at `doctor`. Attaching to the target, changing target state, or running self-tests belongs to later debugging/regression work.

Runtime target capability discovery:

```bash
t32 --json target info
t32 --json reg list --core 0
t32 --json bp enums
```

Self-test plans:

```bash
t32 test
t32 test --memory
t32 test --extended
t32 test --execution
t32 test --all
```

The default plan is observation-only. `--memory` adds TRACE32 `VM:` scratch round-trips; `--extended` adds temporary breakpoint state; `--execution` adds Break/Step/Go; `--all` runs every registered suite.

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
