from typing import Any

import base64
import click
from io import BytesIO
import os
from result import Ok, Err, Result, is_ok, is_err
import signal
import streamlit
import sys
import threading

_LOGGER= streamlit.logger.get_logger("streamlit-julia-call")

_JULIA_INSTANCE_KEY = "__streamlit_julia_call__julia_instance__"


def _get_streamlit_runtime():
    import streamlit.runtime as runtime
    return runtime.get_instance()


def _get_julia_instance():
    import streamlit.runtime as runtime
    return getattr(_get_streamlit_runtime(), _JULIA_INSTANCE_KEY, None)


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

    loop = _get_streamlit_runtime()._get_async_objs().eventloop
    loop.call_soon_threadsafe(caller)

    done_event.wait()

    if exception is None:
        return Ok(result)
    else:
        return Err(exception)


def _sigint_handler(signum, frame):
    _LOGGER.debug("SIGINT has been triggered.  Send SIGTERM the process itself.")
    # Send SIGTERM to the process itself to fire Streamlit's original SIGINT handler
    os.kill(os.getpid(), signal.SIGTERM)


def _setup_signal_handlers():
    _LOGGER.debug("Register the SIGINT handler")
    signal.pthread_sigmask(signal.SIG_UNBLOCK, [signal.SIGINT])
    signal.signal(signal.SIGINT, _sigint_handler)


def _init_julia(ready_event, script_run_ctx):
    if "JULIA_NUM_THREADS" not in os.environ:
        os.environ["JULIA_NUM_THREADS"] = "auto"

    _LOGGER.debug("Start to instantiate the Julia instance.")

    import julia.api
    julia = julia.api.Julia()

    _LOGGER.debug("The julia instance has been craeted.")

    setattr(_get_streamlit_runtime(), _JULIA_INSTANCE_KEY, julia)

    _LOGGER.debug("The julia instance has been stored into Streamlit's Runtime instance")

    from streamlit.runtime.scriptrunner import add_script_run_ctx
    add_script_run_ctx(ctx=script_run_ctx)

    _setup_signal_handlers()

    _helper_jl_path = os.path.abspath(os.path.join(__file__, "..", "helper.jl"))
    _LOGGER.debug(f"Start to load {_helper_jl_path}")

    julia.eval(f"""include("{_helper_jl_path}")""")

    _LOGGER.debug(f"{_helper_jl_path} is loaded")

    ready_event.set()
    _LOGGER.debug("Julia is ready.")

    return


def _start_julia():
    if _get_julia_instance() is None:
        julia_ready = threading.Event()
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        script_run_ctx = get_script_run_ctx()
        _run_on_runtime_eventloop(lambda: _init_julia(julia_ready, script_run_ctx))
        julia_ready.wait()


def julia_call(target):
    def wrapper(*args, **kw):
        _start_julia()
        julia = _get_julia_instance()
        result = _run_on_runtime_eventloop(lambda: target(julia, *args, **kw))
        _LOGGER.debug(f"result = {result}")
        if is_ok(result):
            return result.ok_value
        else:
            raise result.err_value
    return wrapper


@julia_call
def julia_eval(julia, src: str):
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
    b64 = base64.b64encode(svg.encode("utf-8")).decode("utf-8")
    html = r'<img src="data:image/svg+xml;base64,%s"/>' % b64
    streamlit.write(html, unsafe_allow_html=True)


def julia_display(src, *, mime=None):
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
        streamlit.write(mime_repr, unsafe_allow_html=True)
    elif mime == "image/png" or mime == "image/jpeg":
        streamlit.image(BytesIO(mime_repr))
    elif mime == "image/svg+xml":
        render_svg(mime_repr)
    elif mime == "text/latex":
        streamlit.latex(mime_repr)
    else:
        _LOGGER.warning(f"Unable to display an unsupported mime type data: {mime}")


__all__ = [
    "julia_call",
    "julia_eval",
    "julia_display"
]
