import argparse
import os
import sys


def parse_args(argv):
    parser = argparse.ArgumentParser(prog="ftp.py")
    parser.add_argument("--host", default=os.environ.get("FTP_BIND", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("FTP_PORT", "2121")))
    parser.add_argument("--user", default=os.environ.get("FTP_USER", "user"))
    parser.add_argument("--password", default=os.environ.get("FTP_PASS", "1234"))
    parser.add_argument("--root", default=os.environ.get("FTP_ROOT", os.getcwd()))
    return parser.parse_args(argv)


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    args = parse_args(argv)

    try:
        from pyftpdlib.authorizers import DummyAuthorizer
        from pyftpdlib.handlers import FTPHandler
        from pyftpdlib.servers import FTPServer
    except Exception:
        print("Chybí balík 'pyftpdlib'. Nainstaluj: python -m pip install pyftpdlib")
        return 1

    root = os.path.abspath(args.root)
    if not os.path.isdir(root):
        print("Root složka neexistuje: {}".format(root))
        return 2

    if args.password == "1234" and args.host not in ("127.0.0.1", "localhost"):
        print("Varování: heslo '1234' je slabé. Pokud binduješ mimo localhost, změň FTP_PASS/--password.")

    authorizer = DummyAuthorizer()
    authorizer.add_user(args.user, args.password, root, perm="elradfmwMT")

    handler = FTPHandler
    handler.authorizer = authorizer

    address = (args.host, args.port)
    server = FTPServer(address, handler)
    print("FTP běží na ftp://{}:{} (user='{}', root='{}')".format(args.host, args.port, args.user, root))
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
