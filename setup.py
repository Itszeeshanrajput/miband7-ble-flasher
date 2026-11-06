from setuptools import setup, find_packages

setup(
    name="miband7-ble-flasher",
    version="1.0.0",
    description="Standalone BLE Firmware Flasher and Auth Tool for Xiaomi Smart Band 7",
    author="Zeeshan Rajput",
    url="https://github.com/Itszeeshanrajput/miband7-ble-flasher",
    packages=find_packages(),
    py_modules=["flasher"],
    entry_points={
        "console_scripts": [
            "miband7-flasher=flasher:main",
        ],
    },
    install_requires=[
        "dbus-python>=1.3.2",
        "PyGObject>=3.46.0",
        "pycryptodome>=3.20.0",
        "requests>=2.31.0",
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: POSIX :: Linux",
        "Topic :: System :: Hardware",
        "Topic :: Software Development :: Embedded Systems",
    ],
    python_requires=">=3.8",
)
