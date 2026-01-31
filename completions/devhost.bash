# bash completion for devhost
_devhost_completions() {
    local cur prev cmds names
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"
    cmds="add remove list url open validate export edit resolve doctor info domain hosts caddy start stop status install"

    if [[ ${COMP_CWORD} -eq 1 ]]; then
        COMPREPLY=( $(compgen -W "${cmds}" -- "$cur") )
        return 0
    fi

    # subcommand-specific
    case "$prev" in
        add)
            COMPREPLY=( $(compgen -W "--http --https" -- "$cur") )
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
        hosts)
            COMPREPLY=( $(compgen -W "sync clear" -- "$cur") )
            return 0
            ;;
        caddy)
            COMPREPLY=( $(compgen -W "start stop restart status" -- "$cur") )
            return 0
            ;;
        install)
            COMPREPLY=( $(compgen -W "--macos --windows --linux --caddy" -- "$cur") )
            return 0
            ;;
    esac
}

complete -F _devhost_completions devhost
