# dotstash

![Tests](https://github.com/iris18102006/Dotstash/actions/workflows/tests.yml/badge.svg)

Back up and restore your dotfiles with one command. Pure Python, no dependencies.

You tell it which files matter (fish config, i3 config, `.bashrc`...), it keeps copies in a vault folder, and on a fresh machine one command puts everything back. The vault is a normal folder, so you can make it a git repo and push it to GitHub.

## Install

```bash
git clone https://github.com/iris18102006/dotstash.git
pipx install ./dotstash
```

Needs Python 3.9 or newer and [pipx](https://pipx.pypa.io). Plain `pip install` is blocked on recent Ubuntu and Debian, which is why this uses pipx. To update after pulling new code: `pipx install --force ./dotstash`.

## Usage

```bash
dotstash init                          # create ~/dotstash-vault
dotstash add ~/.config/fish ~/.config/i3/config ~/.bashrc
dotstash status                        # what changed since the last backup?
dotstash diff                          # see the actual lines that changed
dotstash backup                        # home -> vault
dotstash restore -n                    # dry run: see what a restore would do
dotstash restore                        # vault -> home
```

| Command | What it does |
| --- | --- |
| `init` | Create a new vault |
| `add <paths>` | Start tracking files or folders |
| `remove <paths>` | Stop tracking them |
| `ignore <patterns>` | Never back up files matching a pattern (`ignore --list` to see them) |
| `list` | Show everything tracked |
| `status` | Compare home with the vault (synced, modified, missing) |
| `diff [paths]` | Show line by line what `backup` would change |
| `backup [-n]` | Copy tracked files from home into the vault |
| `restore [-n]` | Copy tracked files from the vault into home |

Use `--vault PATH` or the `DOTSTASH_VAULT` environment variable to put the vault somewhere else.

## Fish completions

```bash
cp completions/dotstash.fish ~/.config/fish/completions/
```

Open a new terminal and `dotstash <Tab>` lists the commands.

## Ignoring files

Some files inside a folder you track should never leave your machine. Tell dotstash to skip them:

```bash
dotstash ignore '*.key' secrets.fish
dotstash ignore --list
dotstash ignore --remove '*.key'
```

Patterns match file and folder names (shell style, so `*` works). Adding a pattern also deletes any matching files already in the vault. Built in, always ignored: `.git`, `__pycache__`, `fish_variables` (fish stores exported variables there, API keys included) and `*.dotstash.bak`.

## Safety

- `restore` never overwrites silently. A file that differs is renamed to `name.dotstash.bak` first, and files that only exist in your home folder are left alone.
- Paths that look like secrets (`~/.ssh`, `~/.gnupg`, `~/.aws`, files named `id_*`) are refused unless you pass `--force`. Do not push those to a public repo.
- Only paths inside your home folder can be tracked.
- `-n` / `--dry-run` shows what would happen without touching anything.

## Back up the vault to GitHub

```bash
cd ~/dotstash-vault
git init
git add .
git commit -m "first backup"
```

Then create a **private** repo on GitHub and push to it.

## Development

```bash
pip install pytest
python -m pytest
```

## License

MIT, see [LICENSE](LICENSE).
