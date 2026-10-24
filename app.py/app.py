"""Compatibilidad con el comando histórico: python app.py/app.py."""

from pathlib import Path
import runpy


if __name__ == "__main__":
    pipeline = Path(__file__).resolve().parents[1] / "pipeline_meteorologico.py"
    runpy.run_path(str(pipeline), run_name="__main__")
