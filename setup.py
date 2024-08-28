from setuptools import setup, find_packages
from simple_task_tracker import __version__

with open("requirements.txt", "r", encoding="utf-8") as f:
    requirements = f.read().splitlines()

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="simple_task_tracker",
    version=__version__,
    author="Ismail BENHALLAM",
    author_email="ismailben44@gmail.com",
    packages=find_packages(),
    include_package_data=True,
    install_requires=requirements,
    description="Simple Task Tracker CLI",
    long_description=long_description,
    long_description_content_type="text/markdown",
    keywords=["track", "task", "time"],
    url="https://github.com/ismailbenhallam/simple-task-tracker/",
    entry_points={
        "console_scripts": [
            "tt=simple_task_tracker.main:main",
        ],
    },
    classifiers=[
        "Environment :: Console",
        "Programming Language :: Python :: 3.11",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.11",
)
