#!/usr/bin/env python3
"""
Manage local login users for the app (stored in auth.db, bcrypt-hashed).

Run locally — password is entered via a masked prompt and never passed
as a command-line argument or sent anywhere.

Usage:
    python manage_users.py add <username>
"""
import argparse
import getpass
import sys

from auth import create_user


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage local app users")
    sub = parser.add_subparsers(dest="command", required=True)
    add = sub.add_parser("add", help="Create a user, or reset an existing user's password")
    add.add_argument("username")
    args = parser.parse_args()

    if args.command == "add":
        password = getpass.getpass(f"Password for {args.username}: ")
        confirm = getpass.getpass("Confirm password: ")
        if not password:
            print("Password cannot be empty.", file=sys.stderr)
            sys.exit(1)
        if password != confirm:
            print("Passwords do not match.", file=sys.stderr)
            sys.exit(1)
        create_user(args.username, password)
        print(f"User '{args.username}' saved to auth.db.")


if __name__ == "__main__":
    main()
