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
docker pull ghcr.io/truenas/truenas_smb_sync:latest
docker run -it ghcr.io/truenas/truenas_smb_sync:latest --host <host1>#<apikey1> --host <host2>#<apikey2>
```
