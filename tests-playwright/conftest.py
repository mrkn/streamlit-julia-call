from typing import Generator
from types import ModuleType

import os
from random import randint
import shlex
import socket
import subprocess
from tempfile import TemporaryFile
import time

import pytest
from pytest import FixtureRequest
import requests
from playwright.sync_api import Page


class AsyncSubprocess:
    """A context manager. Wraps subprocess. Popen to capture output safely."""

    def __init__(self, args, cwd=None, env=None):
        self.args = args
        self.cwd = cwd
        self.env = env or {}
        self._proc = None
        self._stdout_file = None

    def terminate(self):
        """Terminate the process and return its stdout/stderr in a string."""
        if self._proc is not None:
            self._proc.terminate()
            self._proc.wait()
            self._proc = None

        # Read the stdout file and close it
        stdout = None
        if self._stdout_file is not None:
            self._stdout_file.seek(0)
            stdout = self._stdout_file.read()
            self._stdout_file.close()
            self._stdout_file = None

        return stdout

    def __enter__(self):
        self.start()
        return self

    def start(self):
        # Start the process and capture its stdout/stderr output to a temp
        # file. We do this instead of using subprocess.PIPE (which causes the
        # Popen object to capture the output to its own internal buffer),
        # becaue large amount of output can cause it to deadlock.
        self._stdout_file = TemporaryFile("w+")
        print(f"Running: {shlex.join(self.args)}")
        self._proc = subprocess.Popen(
            self.args,
            cwd=self.cwd,
            stdout=self._stdout_file,
            stderr=subprocess.STDOUT,
            text=True,
            env={**os.environ.copy(), **self.env}
        )

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._proc is not None:
            self._proc.terminate()
            self._proc = None
        if self._stdout_file is not None:
            self._stdout_file.close()
            self._stdout_file = None



def resolve_test_to_script(test_module: ModuleType) -> str:
    """Resolve the test module to the corresponding test script filename."""
    assert test_module.__file__ is not None
    return test_module.__file__.replace("_test.py", ".py")


def hash_to_range(text: str, min: int = 10000, max: int = 65535) -> int:
    sha256_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return min + (int(sha256_hash, 16) % (max - min + 1))


def is_port_available(port: int, host: str) -> bool:
    """Check if a port is available on the given host."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        return sock.connect_ex((host, port)) != 0


def find_available_port(min_port: int = 10000, max_port: int = 65535, max_tries: int = 50, host: str = "localhost") -> int:
    """Find an available port on the given host."""
    for _ in range(max_tries):
        selected_port = randint(min_port, max_port)
        if is_port_available(selected_port, host):
            return selected_port
    raise RuntimeError("Unable to find an available port")


def is_app_server_running(port: int, host: str = "localhost") -> bool:
    """Check if the app server is running."""
    try:
        return requests.get(f"http://{host}:{port}/_stcore/health", timeout=1).text == "ok"
    except Exception:
        return False


def wait_for_app_server_to_start(port: int, timeout: int = 5) -> bool:
    """Wait for the app server to start."""
    print(f"Waiting for app to start... {port}")
    start_time = time.time()
    while not is_app_server_running(port):
        time.sleep(3)
        if time.time() - start_time > 60 * timeout:
            return False
    return True


def wait_for_app_run(page: Page, wait_delay: int = 100):
    """Wait for the given page to finish running."""
    page.wait_for_selector(
        "[data-testid='stStatusWidget']", timeout=20000, state="detached"
    )
    if wait_delay > 0:
        # Give the app a little more time to render everything
        page.wait_for_timeout(wait_delay)


def wait_for_app_loaded(page: Page, embedded: bool = False):
    """Wait for the app to fully loaded."""
    # Wait for the app view container to appear:
    page.wait_for_selector(
        "[data-testid='stAppViewContainer']", timeout=30000, state="attached"
    )

    # Wait for the main menu to appear:
    if not embedded:
        page.wait_for_selector(
            "[data-testid='stMainMenu']", timeout=20000, state="attached"
        )

    wait_for_app_run(page)


@pytest.fixture(scope="module")
def app_port() -> int:
    """Fixture that returns an available port on localhost."""
    # Find a random available port
    return find_available_port()


@pytest.fixture(scope="module", autouse=True)
def app_server(app_port: int, request: FixtureRequest) -> Generator[AsyncSubprocess, None, None]:
    """Fixture that starts and stops the Streamlit app server."""
    streamlit_proc = AsyncSubprocess(
        [
            "poetry",
            "run",
            "streamlit",
            "run",
            resolve_test_to_script(request.module),
            "--server.headless",
            "true",
            "--global.developmentMode",
            "false",
            "--server.port",
            str(app_port),
            "--browser.gatherUsageStats",
            "false"
        ],
        cwd="."
    )
    streamlit_proc.start()
    if not wait_for_app_server_to_start(app_port):
        streamlit_stdout = streamlit_proc.terminate()
        print(streamlit_stdout)
        raise RuntimeError("Unable to start Streamlit app")
    yield streamlit_proc
    streamlit_stdout = streamlit_proc.terminate()
    print(streamlit_stdout)


@pytest.fixture(scope="function")
def app(page: Page, app_port: int) -> Page:
    """Fixture that opens the app."""
    page.goto(f"http://localhost:{app_port}/")
    wait_for_app_loaded(page)
    return page
