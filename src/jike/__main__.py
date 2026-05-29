import sys

USAGE = (
    "Usage: jike <command> [options]\n"
    "\n"
    "Commands:\n"
    "  auth             QR login; print or --out tokens\n"
    "  feed             Following feed\n"
    "  post             Create a post\n"
    "  delete-post      Delete a post\n"
    "  comment          Comment on a post\n"
    "  delete-comment   Delete a comment\n"
    "  search           Search content\n"
    "  profile          User profile\n"
    "  user-posts       List a user's posts\n"
    "  notifications    Unread + notification list\n"
    "  export           Export a user's post history to Markdown\n"
    "\n"
    "Run 'jike <command> --help' for command-specific options."
)


def main() -> None:
    if len(sys.argv) < 2:
        print(USAGE, file=sys.stderr)
        sys.exit(1)

    if sys.argv[1] in ("-h", "--help"):
        print(USAGE)
        return

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
