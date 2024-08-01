import os
import pprint
import signal
import sys
import time

from truenas_api_client import Client
from truenas_api_client import ClientException


# Flag to control the loop
running = True


# Get our list of HOSTS and KEYS combos
hosts = os.environ.get('SYNCHOSTS', '')

host_list = hosts.split('|')


def signal_handler(signum, frame):
    global running
    print(f"Received {'SIGINT' if signum == signal.SIGINT else 'SIGTERM'},"
          "exiting gracefully...")
    running = False
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

    for host_combo in host_list:
        host_data = host_combo.split("#")
        if len(host_data) < 1:
            print("Invalid host#apikey combination")
            sys.exit(1)

        smb_list = get_smb_shares(host_data[0], host_data[1])
        for item in smb_list:
            smbexternal = False
            add_local = True
            # smbid = item['id']
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
                              "same SMB Name defined.")
                        print("------------------------------------")
                        print('Host: ' + host_data[0] + 'Share:' + smbname)
                        print('Host: ' + litem.get("host") +
                              'Share:' + smbname)
                        print("------------------------------------")
                        print("External Links for this share will not " +
                              "be created until this conflict is resolved.")
                        add_local = False

            # Split our list into the local and EXTERNAL shares on the host
            if smbexternal:
                external_smb = {'name': smbname, 'host': host_data[0],
                                'apikey': host_data[1], 'smbpath': smbpath}
                external_shares.append(external_smb)
            else:
                if add_local:
                    local_smb = {'name': smbname, 'host': host_data[0],
                                 'apikey': host_data[1], 'smbpath': smbpath}
                    local_shares.append(local_smb)

        # Create the external smb share links now
        create_external_smb(local_shares, external_shares)

        # Prune any external links that point nowhere
        prune_external_smb(local_shares, external_shares)

        # if isinstance(rv, (int, str)):
        #   print(rv)
        # else:
        # print(json.dumps(rv))


def create_external_smb(local_shares, external_shares):
    """
    Read through our list of external shares and create any
    new external share links

    Args:
    local_shares (list): List of all local smb shares
    external_shares (list): List of all local smb shares

    """
    print("Local Shares:")
    print(local_shares)
    print("External Shares:")
    print(external_shares)


def prune_external_smb(local_shares, external_shares):
    """
    Read through our list of external shares and prune any that point nowhere

    Args:
    local_shares (list): List of all local smb shares
    external_shares (list): List of all local smb shares

    """
    print("Local Shares:")
    print(local_shares)
    print("External Shares:")
    print(external_shares)


def get_smb_shares(host, api_key):
    """
    Return a JSON list of all SMB shares on a target TrueNAS system

    Args:
    host (str): Hostname (or IP) of the TrueNAS system
    api_key (str): API Key of the TrueNAS system
    """
    command = "sharing.smb.query"

    print("Fetching SMB share list from TrueNAS: " + host)

    try:
        with Client("ws://" + host + "/websocket") as c:
            try:
                if not c.call('auth.login_with_api_key', api_key):
                    raise ValueError('Invalid API key')
            except Exception as e:
                print("Failed to login: ", e)
                sys.exit(0)
            try:
                kwargs = {}

                rv = c.call(command, *list(), **kwargs)
                return rv
            except ClientException as e:
                if e.error:
                    print(e.error, file=sys.stderr)
                if e.trace:
                    print(e.trace['formatted'], file=sys.stderr)
                if e.extra:
                    pprint.pprint(e.extra, stream=sys.stderr)
                sys.exit(1)
    except (FileNotFoundError, ConnectionRefusedError):
        print('Failed to run middleware call. Daemon not running?',
              file=sys.stderr)
        sys.exit(1)


def main():

    try:
        while running:
            print("Running... Press Ctrl+C to stop.")
            start_sync()
            time.sleep(10)
    except KeyboardInterrupt:
        print("Caught KeyboardInterrupt.")


if __name__ == '__main__':
    main()
