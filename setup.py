#!/usr/bin/env python
import os
from setuptools import setup, find_packages

# If you want long_description to come from README.md:
here = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(here, "README.md"), encoding="utf-8") as f:
    long_desc = f.read()

setup(
    name="pobshell",
    version="0.1.2",
    author="Peter Dalloz",
    author_email="pdalloz@proton.me",
    description="A Bash-like shell for Python objects",
    long_description=long_desc,
    long_description_content_type="text/markdown",
    license="MIT",
    url="https://github.com/pdalloz/pobshell",  

    # ───── Package discovery ─────
    packages=find_packages(),         # finds 'pobshell' automatically
    include_package_data=True,        # honors MANIFEST.in

    # Tell setuptools “in the installed wheel, copy over these non-.py files”:
    package_data={
        "pobshell": ["manpages/*.txt"],
    },

    # ── Runtime dependencies ──
    install_requires=[
        "cmd2>=2.5.8,<3.0",
        "Pygments>=2.15.1,<3.0",
        "Pympler>=0.9,<1.0",
        "rich>=13.0.0,<15.0",
        "six>=1.16.0,<2.0",
        # only on non-Windows platforms:
        # "readline; sys_platform!='win32'",
        # only on Windows platforms:
        "pyreadline3; sys_platform=='win32'",
    ],

    python_requires=">=3.12,<4",

    
    # ── Additional metadata (highly recommended for PyPI) ──
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.12",
        "License :: OSI Approved :: MIT License",
         "Operating System :: MacOS :: MacOS X",
        # "Operating System :: POSIX :: Linux",
        # "Operating System :: OS Independent",
    ],
)
