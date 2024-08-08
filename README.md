## Introduction

`truenas_smb_sync` is a tool which allows you to sync SMB share maps between
 TrueNAS SCALE systems. By providing a list of hosts and API keys, the agent
will monitor each TrueNAS system for locally created SMB shares. When detected
an EXTERNAL: link to that share will be created on all other TrueNAS systems.

For SMB clients, this means no matter which TrueNAS system they connect to, they
will see a list of all the SMB shares across all hosts. The client can connect
to any of those shares and will be transparently re-directed to the proper TrueNAS
host. 


## Installation Instructions

```
# virtualenv venv
# ./venv/bin/pip install -r requirements.txt
# ./venv/bin/pip install .
```

## Usage Instructions

```
# ./venv/bin/sharesync --host <host1>#<apikey1> --host <host2>#<apikey2>
```

### Docker Instructions
```
docker pull ghcr.io/truenas/truenas_smb_sync:master
docker run -it ghcr.io/truenas/truenas_smb_sync:master --host <host1>#<apikey1> --host <host2>#<apikey2>
```
