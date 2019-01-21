"""Dump HipChat history for rooms and users.

Usage:
    hipdump.py --key=<KEY> [--path=<PATH>] [--avatars] [--rooms] [--users] [--files]
    hipdump.py --key=<KEY> --avatars --rooms --users --files
    hipdump.py --key=<KEY> --rooms --users --files
    hipdump.py --key=<KEY> --users --files

Options:
    -k --key KEY      HipChat API key from https://www.hipchat.com/account/api
    -p --path PATH    Directory for data dump [default: history]
    -a --avatars      Dump avatars for all users.
    -u --users        Dump history for all users.
    -r --rooms        Dump history for all rooms.
    -f --files        Dump files for dumped history.

Prerequisites:

    virtualenv -p $(which python2) env
    env/bin/pip install -r requirements.txt
    env/bin/python hipdump.py --key=...

"""
from gevent import monkey

monkey.patch_all()

import glob
import io
import json
import logging
import os
import re
import sys
import unicodedata
import urllib

import docopt
import gevent
import hypchat
from hypchat.restobject import Linker, RestObject, User, Room


def main(args):
    hd = HipDump(args["--key"], args["--path"])
    if args["--avatars"]:
        hd.avatars(base_func=lambda x: x.email.split("@")[0])
    if args["--users"]:
        hd.save("users", args["--files"], base_func=lambda x: x.email.split("@")[0])
    if args["--rooms"]:
        hd.save("rooms", args["--files"], base_func=lambda x: x.name)
    logging.info("Done!")


class HipDump:
    def __init__(self, key, path):
        hypchat.Linker = HipDump.BasicLinker
        self.hc = hypchat.HypChat(key)
        self.path = path
        HipDump.mkdir(path)

    def rooms(self):
        filename = "{}/rooms.json".format(self.path)
        try:
            with open(filename) as f:
                rooms = json.load(f)
        except IOError:
            params = {
                "max-results": 1000,
                "include-archived": "true",
                "expand": "items.participants,items.statistics",
            }
            rooms = list(self.hc.rooms(**params).contents())
            HipDump.write_json(filename, rooms)
        return (Room(room) for room in rooms)

    def users(self):
        filename = "{}/users.json".format(self.path)
        try:
            with open(filename) as f:
                users = json.load(f)
        except IOError:
            users = list(self.hc.users(expand="items", guests=True).contents())
            HipDump.write_json(filename, users)
        return (User(user) for user in users)

    def chats(self, obj, since=None):
        kind = "user" if hasattr(obj, "mention_name") else "room"
        url = "{}/v2/{}/{}/history".format(self.hc.endpoint, kind, obj.id)
        params = {"max-results": 1, "reverse": "false"}
        results = None
        while results is None or len(results) == params["max-results"]:
            # Start with 10 to save time appending latest to previous run.
            params["max-results"] = min(1000, 10 * params["max-results"])
            params["date"] = None if results is None else results[-1]["date"]
            logging.debug(
                u"Fetching {} chats for {} {}{}".format(
                    params["max-results"],
                    kind,
                    obj.name,
                    "" if results is None else " ending " + str(params["date"])[:19],
                )
            )
            results = self.hc.fromurl(url, **params)["items"]
            for result in results:
                if str(result["date"]) == since:
                    return  # Reached overlap
                yield result

    def avatars(self, base_func):
        """Save avatars for all users to avatars/base_func().

            base_func:  callable such as (lambda x: x.email.split("@")[0])
        """
        # for user in self.users():
        #    basename = HipDump.slugify(base_func(user))
        #    HipDump.avatar_download(user, self.path + "/avatars", basename)
        jobs = [
            gevent.spawn(
                HipDump.avatar_download,
                user,
                self.path + "/avatars",
                HipDump.slugify(base_func(user)),
            )
            for user in self.users()
        ]
        gevent.joinall(jobs, timeout=5)

    def save(self, item_kind, files_too, base_func):
        """Save history for all of item_kind to folders named base_func().

            item_kind:  "users" or "rooms"
            files_too:  True or False
            base_func:  callable such as (lambda x: x.name)
        """
        for item in getattr(self, item_kind)():
            basename = HipDump.slugify(base_func(item))
            pathname = "{}/{}/{}".format(self.path, item_kind, basename)
            filename = "{}/{}.json".format(pathname, basename)
            # Combine any saved chats with newly fetched chats and save.
            try:
                with open(filename) as f:
                    chats = json.load(f)
                    since = chats[0]["date"]
            except IOError:
                chats, since = [], None  # No saved chats.
            new_chats = list(self.chats(item, since))
            if len(new_chats):
                chats = new_chats + chats
                HipDump.mkdir(pathname)
                HipDump.write_json(filename, chats)
            if not len(chats):
                logging.debug("No history for " + item.name)
                continue
            logging.debug(u"{}: {} ({})".format(filename, basename, len(chats)))
            # Fetch any unfetched files in the entire history.
            if files_too:
                self.files(chats, pathname)
                HipDump.avatar_download(item, pathname, basename)

    def files(self, chats, path):
        ids = [chat.get("authenticated_file", {}).get("id") for chat in chats]
        for file_id in ids:
            if file_id is not None:
                self.auth_download(path + "/files", file_id)

    def auth_download(self, path, file_id):
        if glob.glob("{}/{}_*".format(path, file_id)):
            return
        url = "{}/v2/file/{}".format(self.hc.endpoint, file_id)
        obj = self.hc.fromurl(url)
        name = u"{}_{}".format(file_id, obj.name.split("/")[-1])
        HipDump.download(obj.temp_download_url, path, name)

    @staticmethod
    def avatar_download(user, path, base):
        url = user.get("photo_url")
        if not url:
            return
        ext = os.path.splitext(url)[-1]
        # Try getting larger version.
        url = re.sub("_\d+$", "", os.path.splitext(url)[0]) + ext
        HipDump.download(url, path, base + ext)

    @staticmethod
    def download(url, path, name):
        HipDump.mkdir(path)
        filename = u"{}/{}".format(path, name)
        if not os.path.exists(filename):
            logging.debug(filename)
            urllib.urlretrieve(url, filename)

    @staticmethod
    def write_json(filename, obj):
        with io.open(filename, "w", encoding="utf-8") as f:
            f.write(json.dumps(obj, ensure_ascii=False, default=str))

    @staticmethod
    def mkdir(path):
        try:
            os.makedirs(path)
        except OSError:
            if not os.path.isdir(path):
                raise

    @staticmethod
    def slugify(value):
        """
        Convert to ASCII and spaces to hyphens; keep alphanumerics, underscores
        and hyphens; strip leading and trailing whitespace.
        https://github.com/django/django/blob/277017ae/django/utils/text.py#L386
        """
        return re.sub(
            r"[-\s]+",
            "-",
            re.sub(
                r"[^\w\s-]",
                "",
                unicodedata.normalize("NFKD", value)
                .encode("ascii", "ignore")
                .decode("ascii"),
            ).strip(),
        )

    class BasicLinker(Linker):
        """
        The files JSON response lacks expected "links", so _obj_from_text
        does not return object without this hacky workaround.
        """

        def __init__(self, *p, **kw):
            super(HipDump.BasicLinker, self).__init__(*p, **kw)

        @staticmethod
        def _obj_from_text(text, requests):
            obj = json.JSONDecoder(object_hook=RestObject).decode(text)
            if "links" in obj:
                return Linker._obj_from_text(text, requests)
            obj["_requests"] = requests
            return obj


if __name__ == "__main__":
    logging.getLogger("urllib3").setLevel(logging.ERROR)
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(filename)s:%(lineno)s:%(funcName)s] %(message)s",
    )
    sys.exit(main(docopt.docopt(__doc__)))
