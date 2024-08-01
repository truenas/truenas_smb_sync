import os
import pprint
import signal
import sys
import time

from truenas_api_client import Client
from truenas_api_client import ClientException


# Flag to control the loop
running = True

# Global Host List
host_list = []


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
                                 'smbpath': smbpath}
                    local_shares.append(local_smb)

    # Create the external smb share links now
    parse_local_smb(local_shares, external_shares)

    # Prune any external links that point nowhere
    parse_external_smb(local_shares, external_shares)

    # if isinstance(rv, (int, str)):
    #   print(rv)
    # else:
    # print(json.dumps(rv))


def parse_local_smb(local_shares, external_shares):
    """
    Read through our list of local shares and create any
    new external share links

    Args:
    local_shares (list): List of all local smb shares
    external_shares (list): List of all local smb shares

    """

    # Loop through all the local shares, add external links where necessary
    for lshare in local_shares:

        # Confirm this share is on each host
        for host in host_list:
            create_share = True

            # Skip the same host
            if lshare.get("host") == host.get("host"):
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

    # print("Local Shares:")
    # print(local_shares)
    # print("External Shares:")
    # print(external_shares)


def parse_external_smb(local_shares, external_shares):
    """
    Read through our list of external shares and prune any that point nowhere

    Args:
    local_shares (list): List of all local smb shares
    external_shares (list): List of all local smb shares

    """
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
    print("Creating EXTERNAL share: " + host + "\\" + smbname
          + " ====> " + sharepath)
    createlist = {'path': "EXTERNAL:" + sharepath,
                  'comment': "Auto-Created SMB Redirect", 'name': smbname}

    try:
        with Client("ws://" + host + "/websocket") as c:
            try:
                if not c.call('auth.login_with_api_key', apikey):
                    raise ValueError('Invalid API key')
            except Exception as e:
                print("Failed to login: ", e)
                return
            try:
                kwargs = {}

                rv = c.call(command, createlist, **kwargs)
                # TODO - Add some error handling
                print(rv)
                return
            except ClientException as e:
                if e.error:
                    print(e.error, file=sys.stderr)
                if e.trace:
                    print(e.trace['formatted'], file=sys.stderr)
                if e.extra:
                    pprint.pprint(e.extra, stream=sys.stderr)
                return
    except (FileNotFoundError, ConnectionRefusedError):
        print('Failed to run middleware call. Daemon not running?',
              file=sys.stderr)
        return


def remove_smb_share(host, apikey, smbid):
    """
    Remove an SMB share identified by ID

    Args:
    host (str): hostname of the TrueNAS system
    apikey (str): api key of the TrueNAS system
    smbid (std): SMB Share ID to remove
    """
    command = "sharing.smb.delete"

    print("Deleting external share: " + host + " ShareID: " + smbid)
    dellist = {'id': smbid}

    print(dellist)
    return

    try:
        with Client("ws://" + host + "/websocket") as c:
            try:
                if not c.call('auth.login_with_api_key', apikey):
                    raise ValueError('Invalid API key')
            except Exception as e:
                print("Failed to login: ", e)
                return
            try:
                kwargs = {}

                rv = c.call(command, dellist, **kwargs)
                # TODO - Add some error handling
                print(rv)
                return
            except ClientException as e:
                if e.error:
                    print(e.error, file=sys.stderr)
                if e.trace:
                    print(e.trace['formatted'], file=sys.stderr)
                if e.extra:
                    pprint.pprint(e.extra, stream=sys.stderr)
                return
    except (FileNotFoundError, ConnectionRefusedError):
        print('Failed to run middleware call. Daemon not running?',
              file=sys.stderr)
        return


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


def setup_hosts():
    """
    Read through environment variable of hosts, parse
    and add to our list / dict
    """
    # Get our list of HOSTS and KEYS combos
    hosts = os.environ.get('SYNCHOSTS', '')
    host_raw = hosts.split('|')

    for host_combo in host_raw:
        host_data = host_combo.split("#")
        if len(host_data) < 1:
            print("Invalid host#apikey combination")
            sys.exit(1)
        hostadd = {'host': host_data[0], 'apikey': host_data[1]}
        host_list.append(hostadd)


def main():

    # Load the supplied list of hosts
    setup_hosts()

    try:
        while running:
            print("Running... Press Ctrl+C to stop.")
            start_sync()
            time.sleep(60 * 5)
    except KeyboardInterrupt:
        print("Caught KeyboardInterrupt.")


if __name__ == '__main__':
    main()
