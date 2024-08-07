import argparse
import os
import signal
import sys
import time

from truenas_api_client import Client
from truenas_api_client import ClientException


# Global Host List
host_list = []

# Accept WSS Self Signed?
wss_insecure = False

# Debug Mode?
debug_mode = False
if os.environ.get('DEBUG', ''):
    debug_mode = True

# Set default polling interval
poll_minutes = 5
user_poll = os.environ.get('POLLMINUTES')
if user_poll is not None:
    try:
        poll_minutes = int(user_poll)
    except ValueError:
        print("WARNING: Invalid POLLMINUTES, should be int. Using Default")


def signal_handler(signum, frame):
    global running
    print(f"Received {'SIGINT' if signum == signal.SIGINT else 'SIGTERM'},"
          "exiting gracefully...")
    sys.exit(1)


# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


def start_sync():
    """
    Begins the Sync Process

    Starts by connecting to each of the TrueNAS systems and fetching a list
    of all SMB shares.

    This list will be filtered and sorted by local and EXTERNAL.

    """

    local_shares = []
    external_shares = []

    for host in host_list:
        smb_list = get_smb_shares(host.get("host"), host.get("apikey"))

        for item in smb_list:
            smbexternal = False
            add_local = True
            smbid = item['id']
            smbname = item['name']
            smbpath = item['path']
            smbenabled = item['enabled']
            if not smbenabled:
                continue

            # Is this an external share?
            if "EXTERNAL:" in smbpath:
                smbexternal = True

            # Confirm we don't have a name conflict
            namekey = 'name'
            if not smbexternal:
                for litem in local_shares:
                    if litem.get(namekey) == smbname:
                        print("WARNING: The following systems have the " +
                              "same share name defined.")
                        print("------------------------------------")
                        print('Host: ' + host.get("host"))
                        print('Host: ' + litem.get("host"))
                        print('Share: ' + smbname)
                        print("------------------------------------")
                        print("External Links for this share will not " +
                              "be synced until this conflict is resolved.")
                        litem.update({'conflict': True})
                        add_local = False

            # Populate our lists into the local and EXTERNAL shares on the host
            if smbexternal:
                external_smb = {'name': smbname, 'host': host.get("host"),
                                'apikey': host.get("apikey"),
                                'smbpath': smbpath,
                                'smbid': smbid}
                external_shares.append(external_smb)
            else:
                if add_local:
                    local_smb = {'name': smbname, 'host': host.get("host"),
                                 'apikey': host.get("apikey"),
                                 'smbpath': smbpath, 'conflict': False}
                    local_shares.append(local_smb)

    # Create the external smb share links now
    parse_local_smb(local_shares, external_shares)

    # Prune any external links that point nowhere
    parse_external_smb(local_shares, external_shares)


def parse_local_smb(local_shares, external_shares):
    """
    Read through our list of local shares and create any
    new external share links

    Args:
    local_shares (list): List of all local smb shares
    external_shares (list): List of all local smb shares

    """

    global debug_mode

    # Loop through all the local shares, add external links where necessary
    for lshare in local_shares:

        # Confirm this share is on each host
        for host in host_list:
            create_share = True

            # Skip the same host
            if lshare.get("host") == host.get("host"):
                continue

            # Skip any shares that are in conflict
            # I.E. Two shares with same name existing
            if lshare.get("conflict"):
                continue

            # Check if this host has an external share already pointing back
            # to this particular host
            for eshare in external_shares:
                if eshare.get("name") == lshare.get("name"):
                    # External Share found with same name, confirm right host
                    if "EXTERNAL:" + lshare.get("host") \
                            in eshare.get("smbpath"):
                        # External Share is pointing to correct location
                        # Skip creation
                        create_share = False
                    else:
                        # External share is pointing to wrong host, remove it
                        # before we create a new share link with the same name
                        remove_smb_share(eshare.get("host"),
                                         eshare.get("apikey"),
                                         eshare.get("smbid"))
            if create_share:
                # Create the external share link
                create_external_share(host.get("host"), host.get("apikey"),
                                      lshare.get("host"), lshare.get("name"))

    if debug_mode:
        print("Local Shares:")
        print(local_shares)
        print("External Shares:")
        print(external_shares)


def parse_external_smb(local_shares, external_shares):
    """
    Read through our list of external shares and prune any that point nowhere

    Args:
    local_shares (list): List of all local smb shares
    external_shares (list): List of all local smb shares

    """

    # Loop through all the external shares, prune the dead where necessary
    for eshare in external_shares:

        prune_share = True

        # Check local shares for a matching name
        # We don't check path matches here, that is done in parse_local_smb()
        for lshare in local_shares:
            if eshare.get("name") == lshare.get("name"):
                prune_share = False
                break

        if prune_share:
            remove_smb_share(eshare.get("host"),
                             eshare.get("apikey"),
                             eshare.get("smbid"))

    # print("Local Shares:")
    # print(local_shares)
    # print("External Shares:")
    # print(external_shares)


def create_external_share(host, apikey, smbhost, smbname):
    """
    Add a new external SMB Share

    Args:
    host (str): hostname of the TrueNAS system
    apikey (str): api key of the TrueNAS system
    smbhost (str): Target hostname for share link
    smbname (str): Remote share name to link
    """
    command = "sharing.smb.create"

    sharepath = smbhost + '\\' + smbname

    print("Creating share: " + host + "\\" + smbname
          + " redirect to ==> " + sharepath)
    createlist = {'path': "EXTERNAL:" + sharepath,
                  'comment': "Auto-Created SMB Redirect", 'name': smbname}

    api_call(host, apikey, command, createlist, False)


def remove_smb_share(host, apikey, smbid):
    """
    Remove an SMB share identified by ID

    Args:
    host (str): hostname of the TrueNAS system
    apikey (str): api key of the TrueNAS system
    smbid (std): SMB Share ID to remove
    """
    command = "sharing.smb.delete"

    print("Deleting orphaned external share: " + host + " ShareID: " +
          str(smbid))

    api_call(host, apikey, command, smbid, False)


def api_call(host, apikey, command, args, wssmode):
    """
    Run an API call against the specified TrueNAS

    Args:
    host (str): Hostname (or IP) of the TrueNAS system
    apikey (str): API Key of the TrueNAS system
    command (str): API command to call
    args: API arguments
    wssmode (bool): Optional
    """

    # Are we in ws:// or wss:// mode
    wssprefix = "ws://"
    if wssmode:
        wssprefix = "wss://"

    try:
        with Client(wssprefix + host + "/websocket", False,
                    False, False, 60, wss_insecure) as c:
            try:
                if not c.call('auth.login_with_api_key', apikey):
                    raise ValueError('Invalid API key')
            except Exception as e:
                print("WARNING: Failed to login: ", e)
            try:
                kwargs = {}

                rv = c.call(command, args, **kwargs)
                return rv
            except ClientException as e:
                if wssprefix == "ws://":
                    rtn = api_call(host, apikey, command,
                                   args, True)
                    return rtn
                else:
                    print("WARNING: Failed to connect to: " + host)
                    if e.error:
                        print(e.error, file=sys.stderr)

    except (FileNotFoundError, ConnectionRefusedError):
        if wssprefix == "ws://":
            return api_call(host, apikey, command, args, True)
        else:
            print("WARNING: Failed to connect to: " + host)


def get_smb_shares(host, apikey):
    """
    Return a JSON list of all SMB shares on a target TrueNAS system

    Args:
    host (str): Hostname (or IP) of the TrueNAS system
    apikey (str): API Key of the TrueNAS system
    """
    command = "sharing.smb.query"

    print("Fetching SMB share list from TrueNAS: " + host)

    return api_call(host, apikey, command, list(), False)


def main():

    global wss_insecure

    # Create the parser
    parser = argparse.ArgumentParser(description="Process TrueNAS Hosts")
    parser.add_argument('--host', action='append', type=str,
                        help='TrueNAS host to sync in format <host>#<apikey>')
    parser.add_argument('--wssinsecure', type=bool, default=False,
                        help='Auto accept HTTPS certificates over wss://')
    args = parser.parse_args()

    # Show usage if no arguments provided
    if len(sys.argv) == 1:
        parser.print_usage()
        sys.exit(1)

    # Auto accept self-signed wss:// connections?
    if args.wssinsecure:
        wss_insecure = True

    # Read our provided hosts and bail if none
    if args.host:
        if len(args.host) < 2:
            print("Requires a minimum of two TrueNAS hosts to operate.")
            sys.exit(1)

        for host in args.host:
            host_data = host.split("#")
            if len(host_data) < 1:
                print("Invalid <host>#<apikey> combination")
                sys.exit(1)
            hostadd = {'host': host_data[0], 'apikey': host_data[1]}
            host_list.append(hostadd)
    else:
        print("Missing hosts to monitor, use -h for syntax.")
        sys.exit(1)

    if wss_insecure:
        print("Warning: Running with WSS Insecure Mode")

    # We have good hosts to run with, start the main loop until SIGTERM
    try:
        while True:
            print("Starting SMB Share Monitoring... Press Ctrl+C to stop.")
            start_sync()
            time.sleep(poll_minutes * 60)
    except KeyboardInterrupt:
        print("Caught KeyboardInterrupt.")


if __name__ == '__main__':
    main()
