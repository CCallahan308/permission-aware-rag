"""Community Cloud entrypoint with a separate, minimal requirements file."""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from streamlit_app import main

if __name__ == "__main__":
    main()
