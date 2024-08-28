# Simple Task Tracker CLI

<!-- [![Project Status: Active – The project has reached a stable, usable state and is being actively developed.](https://www.repostatus.org/badges/latest/active.svg)](https://www.repostatus.org/#active) -->
[![PyPI - Version](https://img.shields.io/pypi/v/simple-task-tracker?style=for-the-badge)](https://pypi.org/project/simple-task-tracker/)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/simple-task-tracker?style=for-the-badge)
[![GitHub License](https://img.shields.io/github/license/ismailbenhallam/simple-task-tracker?style=for-the-badge)](https://github.com/ismailbenhallam/simple-task-tracker/?tab=MIT-1-ov-file)

<!-- ![GitHub Issues or Pull Requests](https://img.shields.io/github/issues/ismailbenhallam/simple-task-tracker)
![GitHub Repo stars](https://img.shields.io/github/stars/ismailbenhallam/simple-task-tracker?)-->

A command-line interface (CLI) application to keep track of your tasks, their starting time, finishing time and their
durations.
Tasks could be grouped in projects.

## Installation

You can install the package using either `pipx` or `pip`.

> **Note**: It is highly recommended to install this package using [pipx](https://pipx.pypa.io/stable/). It provides
> an isolated environment for installing and managing command-line tools. It also simplifies running CLIs without
> activating a virtual environment.  
> [Check out this page](https://pipx.pypa.io/stable/comparisons/) to compare **pip** and **pipx**.

### Using pipx

```shell
pipx install simple-task-tracker
```

### Using pip

```shell
pip install simple-task-tracker
```

## Usage

After the installation, you can run the CLI application with the following command:

```shell
tt help
```

This will display the list of available commands and their descriptions.

### Commands

- `tt active`:   (or **"a"**) List all active tasks
- `tt create`:   (or **"c"**) Save a new task as ended. The ended time is the time right now, and the starting time is calculated using (now - duration_in_minutes)
- `tt delete`:   (or **"d"**) Delete a task
- `tt finish`:   (or **"f"**) Mark a task as done. It can be restarted again using 'start' command. If no task is specified, stop the only active task.
- `tt help`  :   (or **"h"**) Show help message
- `tt log`   :   (or **"l"**) Log all tasks of the day
- `tt pause` :   (or **"p"**) Pause the active task
- `tt resume`:   (or **"r"**) Resume last stopped task
- `tt start` :   (or **"s"**) Start a task
- `tt week`  :   (or **"w"**) Log the current week stats about all project

## Contributing

Contributions are welcome! If you find any issues or have suggestions for improvements, please open an issue or submit a
pull request on the [GitHub repository](https://github.com/ismailbenhallam/simple-task-tracker/).

## License

This project is licensed under
the [MIT License](https://github.com/ismailbenhallam/simple-task-tracker/?tab=MIT-1-ov-file).

## Contact

If you have any questions or suggestions, feel free to contact me
at [ismailben44@gmail.com](mailto:ismailben44@gmail.com).