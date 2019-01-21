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

All the history will be in JSON format. See below for a command to convert to
plain text format.

You can run this multiple times. It should append any new content without
redownloading everything. **Caveat emptor:** *I wrote this quickly, and there
are no tests.*

## How to take a HipDump

Get a [HipChat API key](https://www.hipchat.com/account/api).

Download this code and setup Python environment:

    git clone https://github.com/CNG/hipdump.git
    cd hipdump
    virtualenv -p $(which python2) env
    env/bin/pip install -r requirements.txt

See usage at top of [hipdump.py](hipdump.py) or by:

    env/bin/python hipdump.py --help

## How to look at your dump

A quick and dirty solution if you have [`jq`](https://stedolan.github.io/jq/)
installed:

    for f in $(find history \( -path "*/users/*" -or -path "*/rooms/*" \) -name "*.json"); do
        echo "${f%.*}.{json -> txt}";
        command cat $f |
        jq -r '.[] | "\(.date[0:19]) \(.from.name): \(.message)"' >
        ${f%.json}.txt;
    done

An alternative to that first line could be something like:

    cd history
    for f in $(find users rooms -name "*.json"); do
