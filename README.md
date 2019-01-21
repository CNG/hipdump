# HipDump

HipChat is dying. To ease the pain, take your HipDump.

Your HipDump contains, optionally:

* Data about all accessible rooms
* Data about all users
* All user avatars
* History of all accessible rooms
* Files from all accessible rooms
* History of all individual conversations
* Files from all individual conversations

All the history will be in JSON format. I will hopefully soon add a utility to
convert that to a more human friendly format, but the important part for now is
to TAKE YOUR HIPDUMP!

You can run this multiple times. It should append any new content without
redownloading everything. **Caveat emptor:** *I wrote this quickly, and there
are no tests.*

## How?!

Get a [HipChat API key](https://www.hipchat.com/account/api).

Download this code and setup Python environment:

    git clone https://github.com/CNG/hipdump.git
    cd hipdump
    virtualenv -p $(which python2) env
    env/bin/pip install -r requirements.txt

See usage at top of [hipdump.py](hipdump.py) or by:

    env/bin/python hipdump.py --help

