@echo off

wt -p "Command Prompt" -d "%~dp0frontend" cmd /k "npm run dev" ; ^
split-pane -V -p "Command Prompt" -d "%~dp0backend" cmd /k "call .venv\Scripts\activate && python manage.py runserver" ; ^
move-focus left ; ^
split-pane -H -p "Command Prompt" -d "%~dp0backend" cmd /k "call .venv\Scripts\activate && celery -A api worker --loglevel=info -P solo" ; ^
move-focus right ; ^
split-pane -H -p "Command Prompt" -d "%~dp0websocket" cmd /k "go run ."