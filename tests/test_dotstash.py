import pytest

from dotstash import cli, core


@pytest.fixture()
def env(tmp_path, monkeypatch):
    h = tmp_path / "home"
    h.mkdir()
    monkeypatch.setenv("HOME", str(h))
    monkeypatch.chdir(h)
    v = tmp_path / "vault"
    core.init_vault(v)
    return h, v


def test_add_backup_restore_roundtrip(env):
    h, v = env
    (h / ".bashrc").write_text("alias ll='ls -l'\n")
    (h / ".config/fish").mkdir(parents=True)
    (h / ".config/fish/config.fish").write_text("set -g x 1\n")
    core.add(v, [".bashrc", ".config/fish"])
    assert core.state(".bashrc", v) == "synced"

    (h / ".bashrc").write_text("changed\n")
    assert core.state(".bashrc", v) == "modified"
    core.backup(v)
    assert (v / "files/.bashrc").read_text() == "changed\n"

    (h / ".bashrc").write_text("oops\n")
    core.restore(v)
    assert (h / ".bashrc").read_text() == "changed\n"
    assert (h / ".bashrc.dotstash.bak").read_text() == "oops\n"


def test_dry_run_changes_nothing(env):
    h, v = env
    (h / "a").write_text("1")
    core.add(v, ["a"])
    (h / "a").write_text("2")
    core.restore(v, dry=True)
    assert (h / "a").read_text() == "2"


def test_refuses_secrets_and_outside_home(env, tmp_path):
    h, v = env
    (h / ".ssh").mkdir()
    (h / ".ssh/id_ed25519").write_text("secret")
    with pytest.raises(core.DotstashError):
        core.add(v, [".ssh"])
    with pytest.raises(core.DotstashError):
        core.add(v, [str(tmp_path)])


def test_cli_exit_codes(env, capsys):
    h, v = env
    (h / "x").write_text("1")
    assert cli.run(["--vault", str(v), "add", "x"]) == 0
    assert cli.run(["--vault", str(v), "status"]) == 0
    assert "synced" in capsys.readouterr().out
    assert cli.run(["--vault", str(v), "add", "nope"]) == 1


def test_default_ignore_skips_fish_variables(env):
    h, v = env
    (h / ".config/fish").mkdir(parents=True)
    (h / ".config/fish/config.fish").write_text("ok\n")
    (h / ".config/fish/fish_variables").write_text("SETUVAR --export KEY:abc\n")
    core.add(v, [".config/fish"])
    assert (v / "files/.config/fish/config.fish").exists()
    assert not (v / "files/.config/fish/fish_variables").exists()
    assert core.state(".config/fish", v) == "synced"


def test_ignore_pattern_purges_vault_and_blocks_backup(env):
    h, v = env
    (h / "conf").mkdir()
    (h / "conf/a.txt").write_text("a")
    (h / "conf/token.key").write_text("shh")
    core.add(v, ["conf"])
    assert (v / "files/conf/token.key").exists()
    removed = core.add_ignore(v, ["*.key"])
    assert removed == ["conf/token.key"]
    (h / "conf/a.txt").write_text("b")
    core.backup(v)
    assert not (v / "files/conf/token.key").exists()
    assert (v / "files/conf/a.txt").read_text() == "b"


def test_restore_keeps_ignored_files_in_home(env):
    h, v = env
    (h / "conf").mkdir()
    (h / "conf/a.txt").write_text("a")
    (h / "conf/fish_variables").write_text("mine")
    core.add(v, ["conf"])
    (h / "conf/a.txt").write_text("edited")
    core.restore(v)
    assert (h / "conf/a.txt").read_text() == "a"
    assert (h / "conf/fish_variables").read_text() == "mine"
    assert (h / "conf/a.txt.dotstash.bak").read_text() == "edited"
