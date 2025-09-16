import git, os, json, re, requests
from datetime import datetime, time
from InquirerPy import inquirer
from rich.console import Console
from rich.table import Table
from rich.syntax import Syntax

# ===== Global Config =====
console = Console()
QUEUE_FILE = ".devbot_queue.json"
PROJECTS_FILE = ".devbot_projects.json"
WORK_START, WORK_END = 8, 21  # 8AM–9PM

# ===== Helper Functions =====
def load_projects():
    if os.path.exists(PROJECTS_FILE):
        with open(PROJECTS_FILE, "r") as f:
            return json.load(f)
    return {"projects": {}, "default": None}

def save_projects(projects):
    with open(PROJECTS_FILE, "w") as f:
        json.dump(projects, f, indent=2)

def choose_project():
    projects_data = load_projects()
    projects = projects_data["projects"]
    if not projects:
        console.print("[red]No registered projects found.[/red]")
        return None
    project_name = inquirer.fuzzy(
        message="Select a project to work on:",
        choices=list(projects.keys())
    ).execute()
    return projects[project_name]

def detect_repo(folder):
    try:
        return git.Repo(folder)
    except git.exc.InvalidGitRepositoryError:
        return None

def init_repo(folder):
    repo = git.Repo.init(folder)
    console.print(f"[green]Initialized new Git repo in {folder}[/green]")
    return repo

def is_online(remote_url="https://github.com"):
    try:
        requests.head(remote_url, timeout=3)
        return True
    except requests.RequestException:
        return False

def check_work_time():
    now = datetime.now().time()
    if time(WORK_START) <= now <= time(WORK_END):
        return True
    console.print(f"[red]⚠ You are outside scheduled work hours ({WORK_START}:00-{WORK_END}:00)[/red]")
    return False

# ===== Git & Queue Functions =====
def load_queue():
    if os.path.exists(QUEUE_FILE):
        with open(QUEUE_FILE, "r") as f:
            return json.load(f)
    return []

def save_queue(queue):
    with open(QUEUE_FILE, "w") as f:
        json.dump(queue, f, indent=2)

def queue_commit(commit_msg, files):
    queue = load_queue()
    queue.append({
        "message": commit_msg,
        "files": files,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    save_queue(queue)
    console.print(f"[yellow]⏳ Commit queued (offline):[/yellow] {commit_msg}")

def push_queue(repo):
    queue = load_queue()
    if not queue or not is_online():
        return
    origin = repo.remote(name="origin")
    for item in queue:
        repo.index.add(item["files"])
        repo.index.commit(item["message"])
        origin.push()
        console.print(f"[cyan]{item['timestamp']} - Pushed queued commit:[/cyan] {item['message']}")
    save_queue([])

def list_unstaged_files(repo):
    return [item.a_path for item in repo.index.diff(None)]

def show_diff(repo, files):
    for file in files:
        diff = repo.git.diff(file)
        if diff:
            syntax = Syntax(diff, "diff", theme="monokai", line_numbers=True)
            console.print(syntax)
        else:
            console.print(f"[yellow]{file} has no changes[/yellow]")

def commit_and_push(repo, commit_msg, files):
    if is_online():
        repo.index.add(files)
        repo.index.commit(commit_msg)
        try:
            repo.remote(name='origin').push()
            console.print(f"[green]{datetime.now().strftime('%H:%M:%S')} - Committed & pushed:[/green] {commit_msg}")
        except:
            console.print("[yellow]Could not push to remote. Queuing commit.[/yellow]")
            queue_commit(commit_msg, files)
    else:
        queue_commit(commit_msg, files)

# ===== TODO/WIP Scanning =====
def scan_todos(path="."):
    todos = []
    for root, _, files in os.walk(path):
        for file in files:
            if file.endswith(('.py', '.js', '.java', '.txt')):
                try:
                    with open(os.path.join(root, file)) as f:
                        for i, line in enumerate(f):
                            if re.search(r'TODO|WIP', line, re.IGNORECASE):
                                todos.append(f"{file}:{i+1} - {line.strip()}")
                except:
                    continue
    return todos

# ===== Queue & Status Reporting =====
def show_queue():
    queue = load_queue()
    if queue:
        table = Table(title="Queued Commits (Offline)")
        table.add_column("Time")
        table.add_column("Message")
        table.add_column("Files")
        for item in queue:
            table.add_row(item["timestamp"], item["message"], ", ".join(item["files"]))
        console.print(table)
    else:
        console.print("[green]No queued commits[/green]")

def check_push_status(repo):
    origin = repo.remote(name="origin")
    try:
        repo.git.fetch()
    except:
        console.print("[red]Failed to fetch remote. Check network or remote URL[/red]")
        return
    unpushed = list(repo.iter_commits(f'{repo.active_branch}..origin/{repo.active_branch}'))
    queued = load_queue()
    staged = [item.a_path for item in repo.index.diff(None)]
    
    if not unpushed and not queued and not staged:
        console.print("[green]✅ All changes fully pushed to remote![/green]")
    else:
        if staged:
            console.print(f"[yellow]⚠ Staged but not committed: {staged}[/yellow]")
        if unpushed:
            console.print(f"[yellow]⚠ Commits not pushed: {[c.hexsha[:7] for c in unpushed]}[/yellow]")
        if queued:
            console.print(f"[yellow]⏳ Queued commits (offline): {[q['message'] for q in queued]}[/yellow]")

# ===== Main Flow =====
def main():
    console.print("[blue]--- Developer Assistant Bot ---[/blue]")
    if not check_work_time():
        console.print("[blue]Proceeding anyway...[/blue]")

    # Choose project
    project_folder = choose_project()
    if not project_folder:
        console.print("[red]No project selected. Exiting.[/red]")
        return

    repo = detect_repo(project_folder)
    if not repo:
        init = inquirer.confirm(
            message=f"No Git repo found in {project_folder}. Initialize Git here?",
            default=True
        ).execute()
        if init:
            repo = init_repo(project_folder)
        else:
            console.print("[red]Cannot proceed without a Git repo. Exiting.[/red]")
            return

    # Push queued commits if online
    push_queue(repo)

    # Handle unstaged files
    unstaged = list_unstaged_files(repo)
    if unstaged:
        choices = inquirer.checkbox(
            message="Select files to stage:",
            choices=unstaged
        ).execute()
        if choices:
            show_diff(repo, choices)
            commit_msg = inquirer.text(message="Enter commit message:").execute()
            commit_and_push(repo, commit_msg, choices)

    # Show queued commits & TODOs
    show_queue()
    todos = scan_todos(project_folder)
    if todos:
        console.print("[red]⚠ Unfinished tasks detected:[/red]")
        for t in todos:
            console.print(f"[yellow]{t}[/yellow]")
    else:
        console.print("[green]No TODOs/WIPs found[/green]")

    # Final status
    check_push_status(repo)
    console.print(f"[blue]{datetime.now().strftime('%H:%M:%S')} - Project inspection completed[/blue]")

# ===== Run Bot =====
if __name__ == "__main__":
    main()
