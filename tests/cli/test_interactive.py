import pytest
import src.cli.interactive as interactive

from src.cli.interactive import PromptSession, get_banner, get_help_text, run_interactive


class TestInteractiveHelpers:
    def test_get_banner_contains_swarm(self):
        banner = get_banner()
        assert "Cognitive Foundry" in banner
        assert "status" in banner

    def test_get_help_text_contains_commands(self):
        help_text = get_help_text()
        assert "status" in help_text
        assert "prompt" in help_text
        assert "metrics" in help_text
        assert "exit" in help_text


class TestInteractiveRepl:
    @pytest.fixture(autouse=True)
    def _require_prompt_toolkit(self):
        if PromptSession is None:
            pytest.skip("prompt_toolkit not installed")

    def test_run_interactive_exits_on_quit(self, monkeypatch, capsys):
        inputs = iter(["quit"])
        monkeypatch.setattr(
            "src.cli.interactive.PromptSession.prompt",
            lambda *args, **kwargs: next(inputs),
        )
        ret = run_interactive()
        assert ret == 0
        out = capsys.readouterr().out
        assert "Exiting swarm shell" in out

    def test_run_interactive_help_command(self, monkeypatch, capsys):
        inputs = iter(["help", "quit"])
        monkeypatch.setattr(
            "src.cli.interactive.PromptSession.prompt",
            lambda *args, **kwargs: next(inputs),
        )
        run_interactive()
        out = capsys.readouterr().out
        assert "Available commands" in out

    def test_run_interactive_unknown_command(self, monkeypatch, capsys):
        inputs = iter(["foobar", "quit"])
        monkeypatch.setattr(
            "src.cli.interactive.PromptSession.prompt",
            lambda *args, **kwargs: next(inputs),
        )
        run_interactive()
        out = capsys.readouterr().out
        assert "Unknown command" in out

    def test_run_interactive_status_command(self, monkeypatch, capsys):
        inputs = iter(["status", "quit"])
        monkeypatch.setattr(
            "src.cli.interactive.PromptSession.prompt",
            lambda *args, **kwargs: next(inputs),
        )
        run_interactive()
        out = capsys.readouterr().out
        assert "Cognitive Foundry Swarm Status" in out

    def test_run_interactive_empty_input(self, monkeypatch, capsys):
        inputs = iter(["", "quit"])
        monkeypatch.setattr(
            "src.cli.interactive.PromptSession.prompt",
            lambda *args, **kwargs: next(inputs),
        )
        run_interactive()
        out = capsys.readouterr().out
        assert "Exiting swarm shell" in out

    def test_run_interactive_eof(self, monkeypatch, capsys):
        def raise_eof(*args, **kwargs):
            raise EOFError()

        monkeypatch.setattr("src.cli.interactive.PromptSession.prompt", raise_eof)
        run_interactive()
        out = capsys.readouterr().out
        assert "Exiting" in out


class TestInteractiveFallback:
    def test_run_interactive_fallback_dispatches_command(self, monkeypatch, capsys):
        monkeypatch.setattr(interactive, "PromptSession", None)
        inputs = iter(["status", "quit"])
        calls = []

        monkeypatch.setattr("builtins.input", lambda _prompt='': next(inputs))

        def fake_main(argv):
            calls.append(argv)
            print("fallback status executed")
            return 0

        monkeypatch.setattr(interactive.swarm_cli, "main", fake_main)

        ret = interactive.run_interactive()

        assert ret == 0
        assert calls == [["status"]]
        out = capsys.readouterr().out
        assert "falling back to plain input" in out
        assert "fallback status executed" in out

    def test_run_interactive_fallback_unknown_command(self, monkeypatch, capsys):
        monkeypatch.setattr(interactive, "PromptSession", None)
        inputs = iter(["foobar", "quit"])
        monkeypatch.setattr("builtins.input", lambda _prompt='': next(inputs))

        interactive.run_interactive()

        out = capsys.readouterr().out
        assert "Unknown command" in out
