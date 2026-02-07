# bash completion for devhost
_devhost_completions() {
    local cur prev cmds names
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"
    cmds="add remove list url open validate export edit resolve doctor info domain hosts caddy start stop status install diagnostics proxy"

    if [[ ${COMP_CWORD} -eq 1 ]]; then
        COMPREPLY=( $(compgen -W "${cmds}" -- "$cur") )
        return 0
    fi

    # subcommand-specific
    if [[ ${COMP_WORDS[1]} == "proxy" ]]; then
        case "$prev" in
            proxy)
                COMPREPLY=( $(compgen -W "start stop status reload upgrade expose export discover attach detach drift validate lock sync cleanup transfer" -- "$cur") )
                return 0
                ;;
            upgrade)
                COMPREPLY=( $(compgen -W "--to" -- "$cur") )
                return 0
                ;;
            --to)
                COMPREPLY=( $(compgen -W "gateway system" -- "$cur") )
                return 0
                ;;
            expose)
                COMPREPLY=( $(compgen -W "--lan --local --iface --yes -y" -- "$cur") )
                return 0
                ;;
            export)
                COMPREPLY=( $(compgen -W "--driver -d --show -s --use-lock --lock-path" -- "$cur") )
                return 0
                ;;
            --driver)
                COMPREPLY=( $(compgen -W "caddy nginx traefik" -- "$cur") )
                return 0
                ;;
            attach|transfer)
                COMPREPLY=( $(compgen -W "caddy nginx traefik" -- "$cur") )
                return 0
                ;;
            detach)
                COMPREPLY=( $(compgen -W "--config-path -c --force" -- "$cur") )
                return 0
                ;;
            drift)
                COMPREPLY=( $(compgen -W "--driver -d --config-path -c --validate --accept" -- "$cur") )
                return 0
                ;;
            validate)
                COMPREPLY=( $(compgen -W "--driver -d --config-path -c" -- "$cur") )
                return 0
                ;;
            lock)
                COMPREPLY=( $(compgen -W "write apply show" -- "$cur") )
                return 0
                ;;
            sync)
                COMPREPLY=( $(compgen -W "--driver -d --watch -w --interval --use-lock --lock-path" -- "$cur") )
                return 0
                ;;
            cleanup)
                COMPREPLY=( $(compgen -W "--system --external --lock --all --dry-run --yes -y" -- "$cur") )
                return 0
                ;;
            --config-path|-c)
                return 0
                ;;
        esac
    fi

    case "$prev" in
        add)
            COMPREPLY=( $(compgen -W "--http --https --upstream" -- "$cur") )
            return 0
            ;;
        list)
            COMPREPLY=( $(compgen -W "--json" -- "$cur") )
            return 0
            ;;
        remove|url|open|resolve)
            if command -v jq >/dev/null 2>&1; then
                names=$(jq -r 'keys[]' devhost.json 2>/dev/null)
            elif command -v python3 >/dev/null 2>&1; then
                names=$(python3 - <<'PY' 2>/dev/null
import json
try:
    data=json.load(open("devhost.json"))
    print("\n".join(sorted(data.keys())))
except Exception:
    pass
PY
)
            fi
            COMPREPLY=( $(compgen -W "${names}" -- "$cur") )
            return 0
            ;;
        export)
            COMPREPLY=( $(compgen -W "caddy" -- "$cur") )
            return 0
            ;;
        status)
            COMPREPLY=( $(compgen -W "--json" -- "$cur") )
            return 0
            ;;
        doctor)
            COMPREPLY=( $(compgen -W "--windows" -- "$cur") )
            return 0
            ;;
        diagnostics)
            COMPREPLY=( $(compgen -W "preview export upload" -- "$cur") )
            return 0
            ;;
        preview)
            COMPREPLY=( $(compgen -W "--no-state --no-config --no-proxy --no-logs --top --max-size --no-size-limit --redaction-file --redact --no-redact" -- "$cur") )
            return 0
            ;;
        export)
            COMPREPLY=( $(compgen -W "--no-state --no-config --no-proxy --no-logs --output -o --max-size --no-size-limit --redaction-file --redact --no-redact" -- "$cur") )
            return 0
            ;;
        upload)
            COMPREPLY=( $(compgen -W "--max-size --no-size-limit --redaction-file --redact --no-redact" -- "$cur") )
            return 0
            ;;
        hosts)
            COMPREPLY=( $(compgen -W "sync clear" -- "$cur") )
            return 0
            ;;
        caddy)
            COMPREPLY=( $(compgen -W "start stop restart status" -- "$cur") )
            return 0
            ;;
        install)
            COMPREPLY=( $(compgen -W "--macos --windows --linux --caddy --yes --dry-run --start-dns --install-completions --domain --uvicorn --user --clean" -- "$cur") )
            return 0
            ;;
    esac
}

complete -F _devhost_completions devhost
