import typer
from datetime import datetime, date, timedelta
import os
import json
from typing import Dict

app = typer.Typer(add_help_option=False, add_completion=False)

APP_NAME = "simple_task_tracker"
FILE_NAME = "tasks.json"
TASK_TRACKER_DIR: str = typer.get_app_dir(APP_NAME)


def _format_timedelta(delta: timedelta) -> str:
    # Calculate total seconds
    total_seconds = int(delta.total_seconds())

    # Extract hours, minutes, and seconds
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    # Format as HH:MM:SS
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def get_today_file() -> str:
    today = datetime.now()
    return get_file_of_day(today)


def get_file_of_day(day: datetime) -> str:
    return os.path.join(
        TASK_TRACKER_DIR, f"{day.year}", f"{day.month:02d}", f"{day.day:02d}", FILE_NAME
    )


def load_tasks() -> Dict | None:
    file_path = get_today_file()
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            return json.load(f)
    return None


def load_tasks_of_day(day: datetime) -> Dict | None:
    file_path = get_file_of_day(day)
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            return json.load(f)
    return None


def save_tasks(data: Dict):
    file_path = get_today_file()
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "w") as f:
        json.dump(data, f, default=str)


@app.command()
@app.command(name="s", hidden=True)
def start(task: str):
    """(or "s") Start a task"""

    tasks = load_tasks()
    start_time = datetime.now()

    if tasks is None:
        tasks = {
            task: [
                {
                    "started_at": start_time.isoformat(),
                }
            ]
        }

    else:
        # task not found
        if task not in tasks:
            task_data = [
                {
                    "started_at": start_time.isoformat(),
                }
            ]
            tasks[task] = task_data

        # Need to work again on the same task
        elif "ended_at" in tasks[task][-1]:
            task_data = tasks[task]
            task_data.append(
                {
                    "started_at": start_time.isoformat(),
                }
            )
            tasks[task] = task_data

        # Task already started
        else:
            task_data = tasks[task]
            started_at = task_data[-1]["started_at"]
            duration: timedelta = datetime.now() - datetime.fromisoformat(started_at)
            typer.echo(f"Task already started before {_format_timedelta(duration)}")
            raise typer.Exit(code=1)

    save_tasks(tasks)
    typer.echo(f"Task '{task}' started")


@app.command()
@app.command(name="f", hidden=True)
def finish(task: str):
    """(or "f") Mark a task as done. It can be restarted again using 'start' command."""
    tasks = load_tasks()

    if not tasks or task not in tasks:
        typer.echo(f"Task '{task}' is not active")
        raise typer.Exit(code=1)

    task_data = tasks[task]

    # Task already ended
    if "ended_at" in task_data[-1]:
        ended_at = datetime.fromisoformat(task_data[-1]["ended_at"])
        duration: timedelta = datetime.now() - ended_at
        typer.echo(
            f"Task '{task}' was already ended at before {_format_timedelta(duration)}"
        )
        raise typer.Exit(code=1)

    ended_at = datetime.now().isoformat()
    task_data[-1]["ended_at"] = ended_at
    tasks[task] = task_data

    save_tasks(tasks)

    task_total_duration = timedelta(seconds=0)
    for data in task_data:
        task_total_duration += datetime.fromisoformat(
            data["ended_at"]
        ) - datetime.fromisoformat(data["started_at"])

    typer.echo(f"Task ended. Total Duration: {_format_timedelta(task_total_duration)}")


@app.command()
@app.command(name="c", hidden=True)
def create(task: str, duration_in_minutes: int):
    """(or "c") Create a new task as ended. The ended time is the time right now, and the starting time is calculated using (now - duration_in_minutes)"""
    tasks = load_tasks()
    ended_at: datetime = datetime.now()
    started_at: datetime = ended_at - timedelta(minutes=duration_in_minutes)

    if tasks is None:
        tasks = {
            task: [
                {
                    "started_at": started_at.isoformat(),
                    "ended_at": ended_at.isoformat(),
                }
            ]
        }

    else:
        # task already exist
        if task in tasks:
            tasks[task].append(
                {
                    "started_at": started_at.isoformat(),
                    "ended_at": ended_at.isoformat(),
                }
            )
            # task not found
        else:
            tasks[task] = [
                {
                    "started_at": started_at.isoformat(),
                    "ended_at": ended_at.isoformat(),
                }
            ]

    save_tasks(tasks)
    typer.echo(f"Task '{task}' saved")


@app.command()
@app.command(name="d", hidden=True)
def delete(task: str):
    """(or "d") Delete a task"""
    tasks = load_tasks()

    if tasks is None or task not in tasks:
        typer.echo(f"Task '{task}' not found")
        raise typer.Exit(code=1)

    # task should be deleted
    else:
        confirmation: bool = typer.confirm(f"Are you sure you want to delete task '{task}'?")
    if confirmation:
        tasks.pop(task)
        save_tasks(tasks)
        typer.echo(f"Task '{task}' deleted")
    else:
        typer.echo(f"Ok then!")


@app.command()
@app.command(name="a", hidden=True)
def active(from_command: bool = typer.Argument(hidden=True, default=False)):
    """(or "a") List all active tasks"""
    tasks = load_tasks()

    if tasks is None:
        typer.echo(f"No active tasks")
        raise typer.Exit(code=0)

    active_tasks = []
    tasks = load_tasks()
    for task_name, task_data in tasks.items():
        if "ended_at" not in task_data[-1]:
            active_tasks.append(task_name)

    if from_command:
        return active_tasks
    else:
        active_tasks_length = len(active_tasks)
        if active_tasks_length == 0:
            typer.echo(f"No active tasks")
            raise typer.Exit(code=0)

    typer.echo(
        f">> {active_tasks_length} active task{"s" if active_tasks_length > 1 else ""}"
    )
    for task_name in active_tasks:
        typer.echo(f"• {task_name}")


@app.command()
@app.command(name="r", hidden=True)
def resume():
    """(or "r") Resume last stopped task"""

    active_tasks = active(from_command=True)
    if len(active_tasks) > 0:
        typer.echo(
            f"The task '{active_tasks[0]} 'is already active"
        )
        raise typer.Exit(code=0)

    current_task_name: str | None = None
    current_ended_at: datetime = datetime.min

    tasks = load_tasks()
    for task_name, task_data in tasks.items():
        if "ended_at" in task_data[-1]:
            task_ended_at = datetime.fromisoformat(task_data[-1]["ended_at"])
            if task_ended_at > current_ended_at:
                current_task_name = task_name
                current_ended_at = task_ended_at

    if current_task_name is None:
        typer.echo(f"No task found")
        raise typer.Exit(code=0)

    tasks = load_tasks()
    tasks[current_task_name].append(
        {
            "started_at": datetime.now().isoformat(),
        }
    )
    save_tasks(tasks)
    typer.echo(f"Continuing '{current_task_name}'")


@app.command()
@app.command(name="p", hidden=True)
def pause():
    """(or "p") Pause the active task"""
    active_tasks = active(from_command=True)
    if len(active_tasks) == 0:
        typer.echo(f"No active tasks")
        raise typer.Exit(code=0)
    elif len(active_tasks) > 1:
        typer.echo(f"There are multiple active tasks")
        raise typer.Exit(code=0)
    else:
        active_task_name = active_tasks[0]
        tasks = load_tasks()
        tasks[active_task_name][-1]["ended_at"] = datetime.now().isoformat()
        save_tasks(tasks)
        typer.echo(f"Task '{active_task_name}' stopped")


@app.command(name="l", hidden=True)
@app.command()
def log(brief: bool = typer.Option(False, "--brief", "-b", help="brief mode")):
    """(or "l") Log all tasks of the day"""

    tasks = load_tasks()
    if tasks is None or len(tasks.items()) == 0:
        typer.echo(f"No data found for today")
        raise typer.Exit(code=0)

    tasks_total_duration: timedelta = timedelta(seconds=0)

    now = datetime.now()
    if not brief:
        typer.echo(f" -------- Today's tasks --------")

    for task_name, task_data in tasks.items():
        task_total_duration: timedelta = timedelta(seconds=0)
        is_not_ended = False
        for data in task_data:
            if "ended_at" in data:
                task_total_duration += datetime.fromisoformat(
                    data["ended_at"]
                ) - datetime.fromisoformat(data["started_at"])
            else:
                is_not_ended = True
                task_total_duration += now - datetime.fromisoformat(
                    data["started_at"]
                )

        tasks_total_duration += task_total_duration

        if not brief:
            typer.echo(
                f"•{"⏳ " if is_not_ended else "✅ "} '{task_name}' => {_format_timedelta(task_total_duration)} "
            )

    typer.echo(
        f">> ⏱ Total duration : {_format_timedelta(tasks_total_duration)}"
    )
    if not brief:
        typer.echo()


@app.command(name="w", hidden=True)
@app.command()
def week():
    """(or "w") Log the current week tasks"""
    now = datetime.today()
    first_day_of_the_week: datetime = now - timedelta(now.weekday())
    first_second_of_the_week = first_day_of_the_week.replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    delta = now - first_second_of_the_week

    # Total duration of all task this week
    total_duration: timedelta = timedelta(seconds=0)

    for d in range(delta.days + 1):
        specific_day = first_second_of_the_week + timedelta(days=d)

        tasks = load_tasks_of_day(specific_day)
        if tasks is None or tasks == {}:
            continue

        today_tasks_duration: timedelta = timedelta()
        for task_name, task_data in tasks.items():
            for data in task_data:
                if "ended_at" in data:
                    today_tasks_duration += datetime.fromisoformat(
                        data["ended_at"]
                    ) - datetime.fromisoformat(data["started_at"])
                else:
                    today_tasks_duration += now - datetime.fromisoformat(
                        data["started_at"]
                    )

        total_duration = total_duration + today_tasks_duration

    typer.echo(f">> Week total work duration : {_format_timedelta(total_duration)}")


@app.command(name="help")
@app.command(name="h", hidden=True)
def display_help(ctx: typer.Context):
    """(or "h") Show this help message"""
    print(ctx.parent.get_help())


def main():
    os.makedirs(os.path.abspath(os.path.join(get_today_file(), os.pardir)), exist_ok=True)
    app()


if __name__ == "__main__":
    main()
