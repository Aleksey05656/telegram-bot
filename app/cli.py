"""
@file: cli.py
@description: CLI entry point with placeholder for retrain subcommand
@dependencies: logging, sys
@created: 2025-09-10
"""


def main() -> None:
    import logging
    import sys

    logging.getLogger(__name__).warning("Subcommand 'retrain' is not implemented yet.")
    # Явно выходим ненулевым кодом при явном вызове, чтобы не маскировать проблему
    if len(sys.argv) > 1 and sys.argv[1] == "retrain":
        raise NotImplementedError("CLI 'retrain' not implemented")


if __name__ == "__main__":
    main()
