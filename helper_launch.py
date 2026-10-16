"""Build the native helper launch command without changing its runtime or config."""
from pathlib import Path


def service_arguments(app, interpreter, runtime, config):
    values = [str(value) for value in (app, interpreter, runtime, config)]
    if any(not Path(value).is_absolute() or "\0" in value for value in values):
        raise ValueError("Absolute helper paths required")
    app, interpreter, runtime, config = map(Path, values)
    return [str(app / "Contents/MacOS/RepoHub"), "--helper", str(interpreter),
            str(runtime / "repohub.py"), "--config", str(config)]
