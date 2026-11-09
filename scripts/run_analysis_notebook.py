"""Execute the report notebook using this Python interpreter, without solvers."""
import os
from pathlib import Path
import sys

import nbformat
from jupyter_client import KernelManager
from nbclient import NotebookClient

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / 'notebooks' / 'BMP_Experimental_Results.ipynb'


def main():
    # An in-memory kernel specification avoids global kernel registration and
    # ensures .venv packages are used when this script is invoked from .venv.
    os.environ['MPLBACKEND'] = 'module://matplotlib_inline.backend_inline'
    manager = KernelManager(kernel_name='python3')
    manager.kernel_spec.argv = [sys.executable, '-m', 'ipykernel_launcher', '-f', '{connection_file}']
    notebook = nbformat.read(PATH, as_version=4)
    client = NotebookClient(notebook, km=manager, timeout=180,
                            resources={'metadata': {'path': str(ROOT)}})
    try:
        client.execute()
        nbformat.validate(notebook)
        nbformat.write(notebook, PATH)
    finally:
        if manager.has_kernel:
            manager.shutdown_kernel(now=True)
    print(f'Executed: {PATH}')


if __name__ == '__main__':
    main()
