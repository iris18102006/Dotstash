# Fish completions for dotstash.
# Install: cp completions/dotstash.fish ~/.config/fish/completions/

set -l cmds init add remove list status diff backup restore ignore

complete -c dotstash -f
complete -c dotstash -l vault -r -F -d 'vault folder'
complete -c dotstash -s V -l version -d 'show the version'
complete -c dotstash -s h -l help -d 'show help'

complete -c dotstash -n "not __fish_seen_subcommand_from $cmds" -a init -d 'create a new vault'
complete -c dotstash -n "not __fish_seen_subcommand_from $cmds" -a add -d 'start tracking files or folders'
complete -c dotstash -n "not __fish_seen_subcommand_from $cmds" -a remove -d 'stop tracking files or folders'
complete -c dotstash -n "not __fish_seen_subcommand_from $cmds" -a list -d 'show tracked files'
complete -c dotstash -n "not __fish_seen_subcommand_from $cmds" -a status -d 'compare home with the vault'
complete -c dotstash -n "not __fish_seen_subcommand_from $cmds" -a diff -d 'show what backup would change'
complete -c dotstash -n "not __fish_seen_subcommand_from $cmds" -a backup -d 'copy tracked files into the vault'
complete -c dotstash -n "not __fish_seen_subcommand_from $cmds" -a restore -d 'copy tracked files into home'
complete -c dotstash -n "not __fish_seen_subcommand_from $cmds" -a ignore -d 'never back up matching names'

complete -c dotstash -n '__fish_seen_subcommand_from add' -F
complete -c dotstash -n '__fish_seen_subcommand_from add' -l force -d 'allow paths that look like secrets'
complete -c dotstash -n '__fish_seen_subcommand_from remove diff' -F
complete -c dotstash -n '__fish_seen_subcommand_from backup restore' -s n -l dry-run -d 'show what would happen'
complete -c dotstash -n '__fish_seen_subcommand_from ignore' -l list -d 'show the ignore list'
complete -c dotstash -n '__fish_seen_subcommand_from ignore' -l remove -d 'remove patterns from the list'
