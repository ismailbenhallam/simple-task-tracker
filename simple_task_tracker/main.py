import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, date
from sqlite3 import Connection
from typing import Tuple, Iterator, List

import typer

app = typer.Typer(add_help_option=False, add_completion=False)

APP_NAME = "simple_task_tracker"
DB_NAME = "tasks.db"
MIGRATIONS_DIR = "db_migrations"
TASK_TRACKER_DIR: str = typer.get_app_dir(APP_NAME)


# Custom adapters for SQLite
def adapt_datetime(dt):
    """Convert datetime to string format compatible with SQLite"""
    if dt is None:
        return None
    return dt.strftime('%Y-%m-%d %H:%M:%S.%f')


def adapt_date(dt):
    """Convert date to string format compatible with SQLite"""
    return dt.isoformat() if dt else None


# Custom converters for SQLite
def convert_datetime(date_string):
    """Convert SQLite date/time string back to datetime object"""
    if not date_string:
        return None
    try:
        return datetime.strptime(date_string.decode(), '%Y-%m-%d %H:%M:%S.%f')
    except ValueError:
        # Handle timestamps without microseconds
        return datetime.strptime(date_string.decode(), '%Y-%m-%d %H:%M:%S')


def convert_date(date_string):
    """Convert SQLite date string back to date object"""
    if not date_string:
        return None
    try:
        date_str = date_string.decode('utf-8')
        return date.fromisoformat(date_str)
    except (UnicodeDecodeError, TypeError):
        return None


# Register the adapters and converters
sqlite3.register_adapter(datetime, adapt_datetime)
sqlite3.register_adapter(date, adapt_date)
sqlite3.register_converter("datetime", convert_datetime)
sqlite3.register_converter("timestamp", convert_datetime)  # Use same converter for TIMESTAMP
sqlite3.register_converter("date", convert_date)


def get_db_path() -> str:
    return os.path.join(TASK_TRACKER_DIR, DB_NAME)


@contextmanager
def get_db() -> Iterator[sqlite3.Connection]:
    db_path = get_db_path()
    conn: Connection = sqlite3.connect(
        db_path,
        detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
    )
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    with get_db() as conn:
        # Create migrations tracking table
        conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY,
            applied_on TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        conn.commit()

        # Get latest migration version
        version = conn.execute("SELECT max(version) FROM schema_version").fetchone()[0]
        if version is None:
            version = 0

        version += 1
        migrations_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), MIGRATIONS_DIR)

        # Execute migrations
        migration = os.path.join(migrations_path, f"v{version}.sql")
        while os.path.exists(migration):
            with open(migration, "r") as file:
                sql = file.read()

            conn.executescript(sql)
            conn.execute(f"INSERT INTO schema_version (version) VALUES ({version})")
            conn.commit()

            version += 1
            migration = os.path.join(migrations_path, f"v{version}.sql")


def _format_date(d: date) -> str:
    """Format a date in DD-MM-YYYY format."""
    return d.strftime("%d-%m-%Y")


def _format_timedelta(delta: timedelta) -> str:
    if not isinstance(delta, timedelta):
        raise ValueError("_format_timedelta expects a timedelta object.")

    total_seconds = int(delta.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

def _timedelta_to_hours(td):
    """Convert timedelta to hours as a float"""
    return round(td.total_seconds() / 3600, 2)

def get_week_bounds(target_date: date | None = None) -> Tuple[date, date]:
    """Get the start and end dates of the week containing the target date"""
    if target_date is None:
        target_date = date.today()
    start_of_week = target_date - timedelta(days=target_date.weekday())
    end_of_week = start_of_week + timedelta(days=6)
    return start_of_week, end_of_week


def calculate_task_duration(conn, task_name: str, start_date: date, end_date: date | None = None) -> timedelta:
    """Calculate total duration for a task within a date range"""
    if end_date is None:
        end_date = start_date

    result = conn.execute("""
        SELECT sum(CASE 
            WHEN ended_at IS NOT NULL
                THEN strftime('%s', ended_at) - strftime('%s', started_at)
            ELSE strftime('%s', 'now') - strftime('%s', started_at)
        END) as total_seconds
        FROM tasks 
        WHERE name = ? AND date >= ? AND date <= ?
    """, (task_name, start_date, end_date)).fetchone()

    return timedelta(seconds=result['total_seconds'] if result['total_seconds'] else 0)


@app.command()
@app.command(name="s", hidden=True)
def start(task_parts: List[str] = typer.Argument(..., help="Task name (can include spaces)"),
          tag: List[str] = typer.Option(None, "--tag", "-t", help="tag"),
          ):
    """(or "s") Start a task"""
    today = date.today()
    start_time = datetime.now()
    task = " ".join(task_parts)
    tag = " ".join(tag) if tag else None

    with get_db() as conn:
        # Check for existing active tasks efficiently
        active_task_count = conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE date = ? AND ended_at IS NULL",
            (today,)
        ).fetchone()[0]

        if active_task_count > 0:
            # Retrieve active task names if needed (e.g., for logging)
            active_tasks = conn.execute(
                "SELECT name FROM tasks WHERE date = ? AND ended_at IS NULL",
                (today,)
            ).fetchall()
            active_task_names = [t['name'] for t in active_tasks]

            if task in active_task_names:
                # Calculate duration of the ongoing task
                duration = calculate_task_duration(conn, task, today)
                typer.echo(f"Task '{task}' is already active (running for {_format_timedelta(duration)}).")
                raise typer.Exit(code=1)

        # Start the new task
        conn.execute(
            "INSERT INTO tasks (name, started_at, date, tag) VALUES (?, ?, ?, ?)",
            (task, start_time, today, tag)
        )
        conn.commit()

    typer.echo(f"Task '{task}' started.")


@app.command()
@app.command(name="f", hidden=True)
def finish(task_parts: List[str] = typer.Argument(..., help="Task name (can include spaces)")):
    """(or "f") Mark a task as done. It can be restarted again using 'start' command."""
    now = datetime.now()
    today = now.date()
    task = " ".join(task_parts)

    with get_db() as conn:
        # Fetch all active tasks with the given name
        active_tasks = conn.execute(
            "SELECT * FROM tasks WHERE name = ? AND ended_at IS NULL",
            (task,)
        ).fetchall()

        if not active_tasks:
            typer.echo(f"Task '{task}' is not active.")
            raise typer.Exit(code=1)

        # Update all active instances of the task
        for active_task in active_tasks:
            conn.execute(
                "UPDATE tasks SET ended_at = ? WHERE id = ?",
                (now, active_task['id'])
            )

        total_duration = calculate_task_duration(conn, task, today)
        conn.commit()

    typer.echo(f"\nTask '{task}' ended.\nTotal time spent on this task today: {_format_timedelta(total_duration)}.")


@app.command()
@app.command(name="c", hidden=True)
def create(
        task_parts: List[str] = typer.Argument(..., help="Task name (can include spaces)"),
        duration_in_minutes: int = typer.Argument(..., help="Duration in minutes"),
        tag_parts: List[str] = typer.Option(None, "--tag", "-t", help="tag"),
):
    """(or "c") Create a new task as ended. The ended time is the time right now, and the starting time is calculated using (now - duration_in_minutes)"""
    ended_at = datetime.now()
    started_at = ended_at - timedelta(minutes=duration_in_minutes)
    today = ended_at.date()
    task = " ".join(task_parts)
    tag_parts = " ".join(tag_parts) if tag_parts else None

    with get_db() as conn:
        conn.execute(
            "INSERT INTO tasks (name, started_at, ended_at, date, tag) VALUES (?, ?, ?, ?, ?)",
            (task, started_at, ended_at, today, tag_parts)
        )
        conn.commit()

        # Calculate duration after insertion (to match log calculation)
        duration = calculate_task_duration(conn, task, today)
        typer.echo(f"Task '{task}' saved with duration of {_format_timedelta(duration)}")


@app.command()
@app.command(name="d", hidden=True)
def delete(task_parts: List[str] = typer.Argument(..., help="Task name (can include spaces)")):
    """(or "d") Delete a task"""
    today = date.today()
    task = " ".join(task_parts)

    with get_db() as conn:
        task_exists = conn.execute(
            "SELECT 1 FROM tasks WHERE name = ? AND date = ?",
            (task, today)
        ).fetchone()

        if not task_exists:
            typer.echo(f"Task '{task}' not found")
            raise typer.Exit(code=1)

        confirmation = typer.confirm(f"Are you sure you want to delete task '{task}'?")
        if confirmation:
            conn.execute(
                "DELETE FROM tasks WHERE name = ? AND date = ?",
                (task, today)
            )
            conn.commit()
            typer.echo(f"Task '{task}' deleted")
        else:
            typer.echo("Ok then!")


@app.command()
@app.command(name="a", hidden=True)
def active(from_command: bool = typer.Argument(hidden=True, default=False)):
    """(or "a") List all active tasks"""
    today = date.today()

    with get_db() as conn:
        # Query to calculate total duration of active tasks grouped by name
        active_tasks = conn.execute("""
            SELECT name,
                   SUM(strftime('%s', 'now') - strftime('%s', started_at)) AS total_duration_seconds
            FROM tasks 
            WHERE ended_at IS NULL
            GROUP BY name
            ORDER BY started_at ASC
        """).fetchall()

    if not active_tasks:
        if from_command:
            return []
        typer.echo("No active tasks")
        raise typer.Exit(code=0)

    if from_command:
        return [task['name'] for task in active_tasks]

    active_tasks_length = len(active_tasks)
    typer.echo(f">> {active_tasks_length} active task{'s' if active_tasks_length > 1 else ''}")

    # Display the active tasks with their total durations
    for task in active_tasks:
        typer.echo(f"• {task['name']}")


@app.command()
@app.command(name="r", hidden=True)
def resume():
    """(or "r") Resume last stopped task"""
    today = date.today()

    with get_db() as conn:
        # Check for active tasks first
        active_tasks = active(from_command=True)
        if active_tasks:
            typer.echo(f"Cannot resume: Task '{active_tasks[0]}' is still active")
            raise typer.Exit(code=1)

        # Find the last ended task
        last_task = conn.execute("""
            SELECT name, ended_at
            FROM tasks 
            WHERE date = ? AND ended_at IS NOT NULL 
            ORDER BY ended_at DESC 
            LIMIT 1
        """, (today,)).fetchone()

        if not last_task:
            typer.echo("No previous task found to resume")
            raise typer.Exit(code=1)

        task_name = last_task['name']

        # Handle potential None value for previous_ended_at
        previous_ended_at = last_task['ended_at']
        if previous_ended_at is None:
            previous_ended_at = datetime.now()

        current_time = datetime.now()
        time_diff = current_time - previous_ended_at

        # Insert a new task record with the calculated `started_at`
        conn.execute(
            "INSERT INTO tasks (name, started_at, date) VALUES (?, ?, ?)",
            (task_name, previous_ended_at + time_diff, today)
        )
        conn.commit()

    typer.echo(f"Resumed task '{task_name}'")


@app.command()
@app.command(name="p", hidden=True)
def pause():
    """(or "p") Pause the active task"""
    today = date.today()

    with get_db() as conn:
        active_tasks = conn.execute(
            "SELECT * FROM tasks WHERE date = ? AND ended_at IS NULL",
            (today,)
        ).fetchall()

        if not active_tasks:
            typer.echo("No active tasks to pause")
            raise typer.Exit(code=1)
        elif len(active_tasks) > 1:
            typer.echo("Multiple active tasks found:")
            for task in active_tasks:
                typer.echo(f"• {task['name']}")
            raise typer.Exit(code=1)

        active_task = active_tasks[0]

        now = datetime.now()
        conn.execute(
            "UPDATE tasks SET ended_at = ? WHERE id = ?",
            (now, active_task['id'])
        )
        conn.commit()

        duration = calculate_task_duration(conn, active_task['name'], today)
        typer.echo(f"Paused '{active_task['name']}' (today's total: {_format_timedelta(duration)})")


@app.command(name="l", hidden=True)
@app.command()
def log(
        brief: bool = typer.Option(False, "--brief", "-b", help="brief mode"),
        date_str: str = typer.Option(None, "--date", "-d", help="Date in DD-MM format")
):
    """
    (or "l") Log all tasks of the day (DD-MM). If --date is not provided, today's date will be used
    """
    try:
        today = date.today()
        target_date = (
            datetime.strptime(f"{date_str}-{today.year}", "%d-%m-%Y").date()
            if date_str
            else today
        )
    except ValueError:
        typer.echo("Invalid date format. Please use DD-MM")
        raise typer.Exit(code=1)

    with get_db() as conn:
        tasks = conn.execute(
            """
            SELECT 
                name,
                tag,
                SUM(
                    CASE 
                        WHEN ended_at IS NOT NULL 
                        THEN strftime('%s', ended_at) - strftime('%s', started_at)
                        ELSE strftime('%s', 'now', 'localtime') - strftime('%s', started_at)
                    END
                ) AS total_seconds,
                COUNT(CASE WHEN ended_at IS NULL THEN 1 END) AS active_count
            FROM tasks 
            WHERE date = ?
            GROUP BY name
            ORDER BY MIN(started_at)
            """,
            (target_date,),
        ).fetchall()

        if not tasks:
            typer.echo(f"No data found for {target_date}")
            raise typer.Exit(code=0)

        total_duration = timedelta()
        tag_duration_map: dict[str, timedelta] = dict()

        if not brief:
            # Get the day of the week
            day_of_week = target_date.strftime('%A')
            typer.echo(f"\n-------- {day_of_week} {_format_date(target_date)} --------")
            typer.echo("Tasks")

        for task in tasks:
            task_duration_seconds = task["total_seconds"] or 0
            task_duration = timedelta(seconds=task_duration_seconds)
            total_duration += task_duration

            if task["tag"]:
                tag = task["tag"]
                if tag in tag_duration_map:
                    tag_duration_map[tag] += task_duration
                else:
                    tag_duration_map[tag] = task_duration

            if not brief:
                status = "⏳ " if task["active_count"] > 0 else "✅ "
                typer.echo(f"• {status} {task['name']} {f"[{task['tag']}]" if task["tag"] else ''} => {_format_timedelta(task_duration)} ({_timedelta_to_hours(task_duration)}h)")

        if not brief and len(tag_duration_map) > 0:
            typer.echo("\nTags")
            for tag, duration in tag_duration_map.items():
                typer.echo(f"• {tag} => {_format_timedelta(duration)} ({_timedelta_to_hours(duration)}h)")
            typer.echo()

        typer.echo(f">> ⏱ Total duration : {_format_timedelta(total_duration)}")


@app.command()
@app.command(name="w", hidden=True)
def week():
    """(or 'w') List all tasks for the current week along with their durations"""
    today = datetime.now().date()

    # Calculate the start of the current week (Monday)
    start_of_week = today - timedelta(days=today.weekday())  # Monday of this week
    # Calculate the end of the current week (Sunday)
    end_of_week = start_of_week + timedelta(days=6)  # Sunday of this week

    # Convert to strings in 'YYYY-MM-DD' format, which SQLite understands
    start_of_week_str = start_of_week.isoformat()
    end_of_week_str = end_of_week.isoformat()

    with get_db() as conn:
        tasks_this_week = conn.execute("""
            SELECT name,
                   SUM(CASE 
                        WHEN ended_at IS NOT NULL
                        THEN (strftime('%s', ended_at) - strftime('%s', started_at))
                        ELSE (strftime('%s', 'now', 'localtime') - strftime('%s', started_at))
                    END) AS total_duration_seconds
            FROM tasks
            WHERE date BETWEEN ? AND ?
            GROUP BY name
            ORDER BY total_duration_seconds DESC
            NULLS LAST
        """, (start_of_week_str, end_of_week_str)).fetchall()

    if not tasks_this_week:
        typer.echo("No tasks recorded for this week")
        raise typer.Exit(code=0)

    total_duration_all_tasks = 0  # Variable to sum all tasks' durations

    typer.echo(f"\n-------- Tasks for the week ({_format_date(start_of_week)} - {_format_date(end_of_week)}) --------")

    for task in tasks_this_week:
        duration_seconds = task["total_duration_seconds"] or 0  # Handle NULL values
        total_duration = timedelta(seconds=duration_seconds)
        typer.echo(f"• {task['name']} (total duration: {_format_timedelta(total_duration)})")
        total_duration_all_tasks += duration_seconds

    total_duration_all_tasks_timedelta = timedelta(seconds=total_duration_all_tasks)
    typer.echo(f"\nTotal duration of all tasks: {_format_timedelta(total_duration_all_tasks_timedelta)}")


@app.command(name="g", hidden=True)
@app.command(name="grep")
def grep(
        pattern_parts: List[str] = typer.Argument(..., help="Search pattern (can include spaces)"),
        date_str: str = typer.Option(None, "--date", "-d", help="Optional date in DD-MM format to limit search")
):
    """(or "g") Search for tasks containing the given pattern (case-insensitive). Optionally limit to a specific date"""
    pattern = " ".join(pattern_parts)

    try:
        today = date.today()
        target_date = None
        if date_str:
            target_date = datetime.strptime(f"{date_str}-{today.year}", "%d-%m-%Y").date()
    except ValueError:
        typer.echo("Invalid date format. Please use DD-MM")
        raise typer.Exit(code=1)

    with get_db() as conn:
        # Build the query based on whether a date was provided
        query = """
            SELECT 
                name,
                date,
                SUM(CASE 
                    WHEN ended_at IS NOT NULL 
                    THEN strftime('%s', ended_at) - strftime('%s', started_at)
                    ELSE strftime('%s', 'now', 'localtime') - strftime('%s', started_at)
                END) AS total_seconds,
                COUNT(CASE WHEN ended_at IS NULL THEN 1 END) AS active_count
            FROM tasks 
            WHERE name LIKE '%' || ? || '%' COLLATE NOCASE
        """
        params = [pattern]

        if target_date:
            query += " AND date = ?"
            params.append(target_date)

        query += """
            GROUP BY name, date
            ORDER BY date DESC, name
        """

        matching_tasks = conn.execute(query, params).fetchall()

        if not matching_tasks:
            date_msg = f" on {target_date}" if target_date else ""
            typer.echo(f"No matching tasks found{date_msg}")
            raise typer.Exit(code=0)

        # Display results
        current_date = None
        daily_total_seconds = 0

        for task in matching_tasks:
            # When date changes, print previous day's total and reset counter
            if current_date is not None and current_date != task['date']:
                daily_total = timedelta(seconds=daily_total_seconds)
                typer.echo(f" >>  Total: {_format_timedelta(daily_total)}")
                daily_total_seconds = 0

            # Print date header when date changes
            if current_date != task['date']:
                current_date = task['date']
                typer.echo(f"\n-------- {current_date.strftime('%A')} {_format_date(current_date)} --------")

            duration_seconds = task["total_seconds"] or 0
            daily_total_seconds += duration_seconds
            duration = timedelta(seconds=duration_seconds)
            status = "⏳ " if task["active_count"] > 0 else "✅ "
            typer.echo(f"• {status} {task['name']} => {_format_timedelta(duration)}")

        # Print the total for the last day
        if matching_tasks:
            daily_total = timedelta(seconds=daily_total_seconds)
            typer.echo(f" >>  Total: {_format_timedelta(daily_total)}")

        # Calculate and display grand total
        grand_total_seconds = sum((task["total_seconds"] or 0) for task in matching_tasks)
        grand_total = timedelta(seconds=grand_total_seconds)
        typer.echo(f"\n>> Grand total: {_format_timedelta(grand_total)}")


@app.command(name="stats")
def statistics():
    """Show detailed statistics about your work patterns"""
    with get_db() as conn:
        # Average daily hours in the last 30 days
        daily_avg = conn.execute("""
            SELECT avg(daily_seconds) as avg_seconds
            FROM (
                SELECT date, 
                       sum(CASE 
                           WHEN ended_at IS NOT NULL 
                           THEN strftime('%s', ended_at) - strftime('%s', started_at)
                           ELSE strftime('%s', 'now') - strftime('%s', started_at)
                       END) as daily_seconds
                FROM tasks
                WHERE date >= date('now', '-30 days')
                GROUP BY date
            )
        """).fetchone()

        # Most productive day of week
        productive_day = conn.execute("""
            SELECT 
                strftime('%w', date) as weekday,
                avg(daily_seconds) as avg_seconds
            FROM (
                SELECT date, 
                       sum(CASE 
                           WHEN ended_at IS NOT NULL 
                           THEN strftime('%s', ended_at) - strftime('%s', started_at)
                           ELSE strftime('%s', 'now') - strftime('%s', started_at)
                       END) as daily_seconds
                FROM tasks
                GROUP BY date
            )
            GROUP BY weekday
            ORDER BY avg_seconds DESC
            LIMIT 1
        """).fetchone()

        weekdays = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']

        typer.echo("\n-------- Work Statistics 📊 --------")
        if daily_avg and daily_avg['avg_seconds']:
            avg_duration = timedelta(seconds=daily_avg['avg_seconds'])
            typer.echo(f"• Average daily work (last 30 days): {_format_timedelta(avg_duration)}")

        if productive_day and productive_day['avg_seconds']:
            productive_duration = timedelta(seconds=productive_day['avg_seconds'])
            weekday = weekdays[int(productive_day['weekday'])]
            typer.echo(f"• Most productive day: {weekday} (avg: {_format_timedelta(productive_duration)})")


@app.command(name="help")
@app.command(name="h", hidden=True)
def display_help(ctx: typer.Context):
    """(or "h") Show this help message"""
    print(ctx.parent.get_help())


def main():
    os.makedirs(TASK_TRACKER_DIR, exist_ok=True)
    init_db()
    app()


if __name__ == "__main__":
    main()
