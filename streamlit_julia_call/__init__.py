from typing import Any, Optional

import base64
from io import BytesIO
import logging
import os
from result import Ok, Err, Result, is_ok, is_err
import signal
import streamlit
import sys
import threading

_LOGGER = logging.getLogger("julia_caller")
_LOGGER.addHandler(logging.StreamHandler(sys.stderr))
_LOGGER.setLevel(logging.DEBUG)

_JULIA_INSTANCE_KEY = "julia_instance"


def _get_streamlit_runtime() -> Optional[streamlit.runtime.Runtime]:
    return streamlit.runtime.get_instance()


def _run_on_runtime_eventloop(callback) -> Result[Any, Exception]:
    done_event = threading.Event()
    result = None
    exception = None

    def caller():
        nonlocal result
        try:
            result = callback()
        except Exception as exc:
            nonlocal exception
            exception = exc
        done_event.set()

    eventloop = _get_streamlit_runtime()._get_async_objs().eventloop
    eventloop.call_soon_threadsafe(caller)

    done_event.wait()

    if exception is None:
        return Ok(result)
    else:
        return Err(exception)


def _setup_signal_handlers():
    def sigint_handler(signum, frame):
        # Send SIGTERM to the process itself to fire the original SIGINT handler
        os.kill(os.getpid(), signal.SIGTERM)

    _LOGGER.info("Unblock SIGINT and register the handler.")
    signal.pthread_sigmask(signal.SIG_UNBLOCK, [signal.SIGINT])
    signal.signal(signal.SIGINT, sigint_handler)


def _get_julia_instance():
    runtime = _get_streamlit_runtime()
    return getattr(runtime, _JULIA_INSTANCE_KEY, None)


def _init_julia(ready_event, script_run_ctx):
    if "JULIA_NUM_THREADS" not in os.environ:
        os.environ["JULIA_NUM_THREADS"] = "auto"

    import julia.api

    _LOGGER.info("Start to initialize the julia instance.")
    julia = julia.api.Julia()

    _LOGGER.info("The julia instance has been created.")

    runtime = _get_streamlit_runtime()
    setattr(runtime, _JULIA_INSTANCE_KEY, julia)

    _LOGGER.info("The julia instance has been stored into the Runtime instance")

    from streamlit.runtime.scriptrunner import add_script_run_ctx
    add_script_run_ctx(ctx=script_run_ctx)

    _setup_signal_handlers()

    helper_jl_path = os.path.abspath(os.path.join(__file__, "..", "helper.jl"))
    julia.eval(f"""
    include("{helper_jl_path}")
    """)

    ready_event.set()
    _LOGGER.info("Julia is ready.")


def _start_julia():
    if _get_julia_instance() is None:
        julia_ready = threading.Event()
        script_run_context = streamlit.runtime.scriptrunner.get_script_run_ctx()
        _run_on_runtime_eventloop(lambda: _init_julia(julia_ready, script_run_context))
        julia_ready.wait()


def ensure_julia_instance():
    julia = _get_julia_instance()
    if julia is not None: return julia

    _start_julia()
    return _get_julia_instance()


def julia_call(target):
    def wrapper(*args, **kw):
        julia = ensure_julia_instance()
        result = _run_on_runtime_eventloop(lambda: target(julia, *args, **kw))
        if is_ok(result):
            return result.ok_value
        else:
            print(result.err_value)
            raise result.err_value

    return wrapper


@julia_call
def julia_eval(julia, src):
    return julia.eval(src)


@julia_call
def _display(julia, obj, mime=None):
    from julia import Base, Main
    if mime is None:
        return Main.StreamlitHelper.display_for_streamlit(obj)
    else:
        mime = Base.MIME(mime)
        return Main.StreamlitHelper.display_mime(mime, obj)


def render_svg(svg):
    b64 = base64.b64encode(svg.encode('utf-8')).decode("utf-8")
    html = r'<img src="data:image/svg+xml;base64,%s"/>' % b64
    streamlit.write(html, unsafe_allow_html=True)


def julia_display(src, *, mime=None):
    import streamlit.components.v1 as components

    if isinstance(src, str):
        obj = julia_eval(src)
    else:
        obj = src

    if mime is None:
        mime, mime_repr = _display(obj)
    else:
        _, mime_repr = _display(obj, mime)

    if src is not obj:
        del obj

    if mime == "text/plain":
        streamlit.write(mime_repr)
    elif mime == "text/markdown":
        streamlit.markdown(mime_repr)
    elif mime == "text/html":
        streamlit.markdown(mime_repr, unsafe_allow_html=True)
    elif mime == "image/png" or mime == "image/jpeg":
        streamlit.image(BytesIO(mime_repr))
    elif mime == "text/latex":
        streamlit.latex(mime_repr)
    elif mime == "image/svg+xml":
        render_svg(mime_repr)


__all__ = [
    "julia_call",
    "julia_eval",
    "julia_display"
]
