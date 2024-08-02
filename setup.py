from setuptools import find_packages, setup


setup(
    name="truenas_share_sync",
    description="TrueNAS SMB Sharing Sync Daemon",
    packages=find_packages(),
    license="LGPLv3",
    install_requires=[
        "websocket-client",
    ],
    entry_points={
        "console_scripts": [
            "sharesync = share_sync:main",
        ],
    },
)
