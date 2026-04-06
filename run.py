import socket
import subprocess
import sys
import os

# ---------- ANSI COLORS ----------
RESET = "\033[0m"
BOLD = "\033[1m"

RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"

# ---------- CONFIG ----------
PORTS = [
    (5173, "Frontend (Vite)"),
    (8000, "Django"),
    (8080, "WebSocket"),
]


# ---------- UTILITIES ----------
def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def get_pid_using_port(port):
    try:
        output = subprocess.check_output(
            f'netstat -ano | findstr :{port}', shell=True, text=True
        )
        lines = output.strip().split("\n")
        if lines:
            return lines[0].split()[-1]
    except subprocess.CalledProcessError:
        pass
    return None


def show_process(pid):
    try:
        subprocess.run(f'tasklist /FI "PID eq {pid}"', shell=True)
    except:
        pass


# ---------- MAIN LOGIC ----------
def check_ports():
    print(f"{BOLD}{CYAN}Checking required ports...{RESET}\n")

    for port, name in PORTS:
        if is_port_in_use(port):
            pid = get_pid_using_port(port)

            print(f"{RED}[FAIL]{RESET} Port {BOLD}{port}{RESET} ({name}) is in use")

            if pid:
                print(f"{YELLOW}PID:{RESET} {pid}")
                print(f"{CYAN}Process details:{RESET}")
                show_process(pid)

                print(f"\n{YELLOW}Action required:{RESET}")
                print(f"  taskkill /PID {pid} /F")
            else:
                print(f"{YELLOW}Warning:{RESET} Unable to determine PID")

            print(f"\n{BOLD}Close the other processes to continue...")
            sys.exit(1)

        print(f"{GREEN}[OK]{RESET}   Port {BOLD}{port}{RESET} ({name}) is available")


def start_services():
    print(f"\n{BOLD}{CYAN}Starting services...{RESET}\n")

    base = os.getcwd()

    wt_command = (
        f'wt -p "Command Prompt" -d "{base}\\frontend" cmd /k "npm run dev" ; '
        f'split-pane -V -p "Command Prompt" -d "{base}\\backend" cmd /k "call .venv\\Scripts\\activate && python manage.py runserver" ; '
        f'move-focus left ; '
        f'split-pane -H -p "Command Prompt" -d "{base}\\backend" cmd /k "call .venv\\Scripts\\activate && celery -A api worker --loglevel=info -P solo" ; '
        f'move-focus right ; '
        f'split-pane -H -p "Command Prompt" -d "{base}\\websocket" cmd /k "go run ." ; '
        f'split-pane -V -p "Command Prompt" -d "{base}\\finetunning" cmd /k "call .venv\\Scripts\\activate && python -m celery -A worker worker -Q inference --loglevel=info --concurrency=1 -P solo"'
    )

    subprocess.run(wt_command, shell=True)


# ---------- ENTRY ----------
if __name__ == "__main__":
    check_ports()
    start_services()