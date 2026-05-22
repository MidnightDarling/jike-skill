import sys


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: jike <auth|export|feed|post|search|...>", file=sys.stderr)
        sys.exit(1)

    if sys.argv[1] == "auth":
        from .auth import main as auth_main

        auth_main(sys.argv[2:])
        return

    if sys.argv[1] == "export":
        from .export import main as export_main

        export_main(sys.argv[2:])
        return

    from .client_cli import main as client_main

    client_main(sys.argv[1:])


if __name__ == "__main__":
    main()
