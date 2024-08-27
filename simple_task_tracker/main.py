import typer
from datetime import datetime, date, timedelta
import os
import json
from typing import Dict

app = typer.Typer(add_help_option=False, add_completion=False)

APP_NAME = "simple_task_tracker"
DEFAULT_PROJECT = "GLOBAL"
TASK_TRACKER_DIR: str = typer.get_app_dir(APP_NAME)


def get_today_folder() -> str:
    today = date.today()
    return os.path.join(TASK_TRACKER_DIR, f"{today.year}", f"{today.month:02d}", f"{today.day:02d}")


def get_project_file_path(project: str) -> str:
    today = date.today()
    return os.path.join(TASK_TRACKER_DIR, f"{today.year}", f"{today.month:02d}", f"{today.day:02d}", f"{project}.json")


def load_project_data(project: str) -> Dict | None:
    file_path = get_project_file_path(project)
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            return json.load(f)
    return None


def save_project_data(project: str, data: Dict):
    file_path = get_project_file_path(project)
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, 'w') as f:
        json.dump(data, f, default=str)


@app.command()
def start(task: str, project: str = typer.Argument(DEFAULT_PROJECT)):
    """Start a task"""

    project_data = load_project_data(project)
    start_time = datetime.now()

    # Project doesn't exist
    if project_data is None:
        project_data = {
            task: [
                {
                    "started_at": start_time.isoformat(),
                }
            ]
        }

    # Project exists already
    else:
        # task not found
        if task not in project_data:
            task_data = [
                {
                    "started_at": start_time.isoformat(),
                }
            ]
            project_data[task] = task_data

        # Need to work again on the same task
        elif "ended_at" in project_data[task][-1]:
            task_data = project_data[task]
            task_data.append(
                {
                    "started_at": start_time.isoformat(),
                }
            )
            project_data[task] = task_data

        # Task already started
        else:
            task_data = project_data[task]
            started_at = task_data[-1]["started_at"]
            duration: timedelta = datetime.now() - datetime.fromisoformat(started_at)
            typer.echo(f"Task already started before {str(duration).split(".")[0]}")
            raise typer.Exit(code=1)

    save_project_data(project, project_data)
    typer.echo(f"Task '{task}' started")


@app.command()
def stop(task: str, project_name: str = typer.Argument(DEFAULT_PROJECT)):
    """Mark a task as done. It can be restarted again using 'start' command. If no task is specified, stop the only active task."""
    project_data = load_project_data(project_name)

    # Project not found
    if not project_data:
        if project_name != DEFAULT_PROJECT:
            typer.echo(f"Project '{project_name}' not found")
            raise typer.Exit(code=1)
        project_data = {}

    if task not in project_data:
        typer.echo(f"Task '{task}' is not active")
        raise typer.Exit(code=1)

    task_data = project_data[task]

    # Task already ended
    if "ended_at" in task_data[-1]:
        ended_at = datetime.fromisoformat(task_data[-1]["ended_at"])
        duration: timedelta = datetime.now() - ended_at
        typer.echo(f"Task '{task}' was already ended at before {str(duration).split(".")[0]}")
        raise typer.Exit(code=1)

    ended_at = datetime.now().isoformat()
    task_data[-1]["ended_at"] = ended_at
    project_data[task] = task_data

    save_project_data(project_name, project_data)

    task_total_duration = timedelta(seconds=0)
    for data in task_data:
        task_total_duration += datetime.fromisoformat(data["ended_at"]) - datetime.fromisoformat(data["started_at"])

    typer.echo(f"Task ended. Total Duration: {str(task_total_duration).split(".")[0]}")


@app.command()
def save(task: str, duration_in_minutes: int, project: str = typer.Argument(DEFAULT_PROJECT)):
    """Save a new task as ended. The ended time is the time right now, and the starting time is calculated using (now - duration_in_minutes)"""
    project_data = load_project_data(project)
    ended_at: datetime = datetime.now()
    started_at: datetime = ended_at - timedelta(minutes=duration_in_minutes)

    # Project doesn't exist
    if project_data is None:
        project_data = {
            task: [
                {
                    "started_at": started_at.isoformat(),
                    "ended_at": ended_at.isoformat(),
                }
            ]
        }

    # Project exists already
    else:
        # task already exist
        if task in project_data:
            project_data[task].append(
                {
                    "started_at": started_at.isoformat(),
                    "ended_at": ended_at.isoformat(),
                }
            )
            # task not found
        else:
            project_data[task] = [
                {
                    "started_at": started_at.isoformat(),
                    "ended_at": ended_at.isoformat(),
                }
            ]

    save_project_data(project, project_data)
    typer.echo(f"Task '{task}' saved")


@app.command()
def delete(task: str, project: str = typer.Argument(DEFAULT_PROJECT)):
    """Delete a task"""
    project_data = load_project_data(project)

    # Project doesn't exist
    if project_data is None:
        typer.echo(f"Project '{project}' not found")
        raise typer.Exit(code=1)

    # Project exists
    else:
        # task not found
        if task not in project_data:
            typer.echo(f"Task '{task}' not found")
            raise typer.Exit(code=1)

        # task should be deleted
        else:
            confirmation: bool = typer.confirm(f"Are you sure you want to delete task '{task}'?")
            if confirmation:
                project_data.pop(task)
                save_project_data(project, project_data)
                typer.echo(f"Task '{task}' deleted")
            else:
                typer.echo(f"Ok then!")


@app.command()
def active(from_command: bool = typer.Argument(hidden=True, default=False)):
    """List all active tasks"""

    projects_names = os.listdir(get_today_folder())

    if len(projects_names) == 0:
        typer.echo(f"No active tasks")
        raise typer.Exit(code=0)

    active_tasks = []
    for project in projects_names:
        project_name = project.split(".")[0]
        project_data = load_project_data(project_name)
        for (task_name, task_data) in project_data.items():
            if "ended_at" not in task_data[-1]:
                active_tasks.append((task_name, task_data[-1]["started_at"], project_name))

    if from_command:
        return active_tasks
    else:
        active_tasks_length = len(active_tasks)
        if active_tasks_length == 0:
            typer.echo(f"No active tasks")
            raise typer.Exit(code=0)

        typer.echo(f">> {active_tasks_length} active task{"s" if active_tasks_length > 1 else ""}")
        for task_name, task_started_at, task_project in active_tasks:
            typer.echo(f"• ({task_project}) '{task_name}'")


@app.command()
def resume():
    """Resume last stopped task"""

    active_tasks = active(from_command=True)
    if len(active_tasks) > 0:
        typer.echo(f"The task '{active_tasks[0][0]}' from the project '{active_tasks[0][2]}' is already active")
        raise typer.Exit(code=0)

    projects_names = os.listdir(get_today_folder())

    if len(projects_names) == 0:
        typer.echo(f"No task found")
        raise typer.Exit(code=0)

    current_project: str | None = None
    current_task_name: str | None = None
    current_ended_at: datetime = datetime.min
    for project in projects_names:
        project_name = project.split(".")[0]
        project_data = load_project_data(project_name)
        for (task_name, task_data) in project_data.items():
            if "ended_at" in task_data[-1]:
                task_ended_at = datetime.fromisoformat(task_data[-1]["ended_at"])
                if task_ended_at > current_ended_at:
                    current_project = project_name
                    current_task_name = task_name
                    current_ended_at = task_ended_at

    if current_task_name is None:
        typer.echo(f"No task found")
        raise typer.Exit(code=0)

    project_data = load_project_data(current_project)
    project_data[current_task_name].append({
        "started_at": datetime.now().isoformat(),
    })
    save_project_data(current_project, project_data)
    typer.echo(f"Continuing '{current_task_name}'")


@app.command()
def pause():
    """Pause the active task"""
    active_tasks = active(from_command=True)
    if len(active_tasks) == 0:
        typer.echo(f"No active tasks")
        raise typer.Exit(code=0)
    elif len(active_tasks) > 1:
        typer.echo(f"There are multiple active tasks")
        raise typer.Exit(code=0)
    else:
        active_task = active_tasks[0]
        active_task_name = active_task[0]
        project_name = active_task[2]
        project_data = load_project_data(project_name)
        project_data[active_task_name][-1]["ended_at"] = datetime.now().isoformat()
        save_project_data(project_name, project_data)
        typer.echo(f"Task '{active_task_name}' stopped")


@app.command()
def logs(project: str | None = typer.Argument(None,
                                              help="Project name. If not specified, all projects' tasks are listed")):
    """Log all tasks of the day"""

    if not project:
        projects_names = os.listdir(get_today_folder())
    else:
        projects_names = [project]

    if len(projects_names) == 0:
        typer.echo(f"No data found for today")
        raise typer.Exit(code=0)

    for project in projects_names:
        project_name = project.split(".")[0]
        project_data = load_project_data(project_name)
        if project_data is None:
            typer.echo(f"No project found with the name '{project}'")
            raise typer.Exit(code=1)

        project_total_duration: timedelta = timedelta(seconds=0)

        if len(project_data.items()) == 0:
            typer.echo(f"No tasks found for '{project_name}'")
            continue

        typer.echo(f" -------- '{project_name}' tasks --------")
        for (task_name, task_data) in project_data.items():
            task_total_duration: timedelta = timedelta(seconds=0)
            is_not_ended = False
            for data in task_data:
                if "ended_at" in data:
                    task_total_duration += datetime.fromisoformat(data["ended_at"]) - datetime.fromisoformat(
                        data["started_at"])
                else:
                    is_not_ended = True
                    task_total_duration += datetime.today() - datetime.fromisoformat(data["started_at"])

            project_total_duration += task_total_duration

            typer.echo(
                f"•{"⏳ " if is_not_ended else "✅ "} '{task_name}' => {str(task_total_duration).split(".")[0]} ")

        typer.echo(f">> ⏱️  Total duration: {str(project_total_duration).split(".")[0]}")
        typer.echo()


@app.command(name="help")
def display_help(ctx: typer.Context):
    """Show this help message"""
    print(ctx.parent.get_help())


def main():
    os.makedirs(get_today_folder(), exist_ok=True)
    app()


if __name__ == "__main__":
    main()
