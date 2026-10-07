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
