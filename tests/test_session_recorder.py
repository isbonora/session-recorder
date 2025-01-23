from click.testing import CliRunner
from session_recorder.cli import cli


def test_version():
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert result.output.startswith("cli, version ")
        
        
def test_list():
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["ls"])
        assert result.exit_code == 0
