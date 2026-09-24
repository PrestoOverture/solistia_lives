from typer.testing import CliRunner

from story_engine.cli import app


def test_help_lists_commands() -> None:
    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0
    for command in ("generate", "kb", "eval"):
        assert command in result.output
