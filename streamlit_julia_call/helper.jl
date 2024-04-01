module StreamlitHelper

import PyCall
import PyCall: PyPtr, PyNULL, PyMethodDef, METH_O, @pysym, @pycheckn, pyincref_, pynothing, ispynull

# The mapping from a sessionid to the corresponding weakref of Python module
const session_weakmodule_cache = Dict{String,PyPtr}()

# The mapping from a weakref of Python module to the corresponding Julia module
const julia_script_module_cache = Dict{PyPtr,Module}()

# weakref_callback Python method
const script_module_weakref_callback_obj = PyNULL()

# Python expects the PyMethodDef structure to be a constant, so we put it in a
# global to prevent GC.
const script_module_weakref_callback_method = Ref{PyMethodDef}()

function script_module_removal_callback(callback::PyPtr, weakref::PyPtr)
    delete!(script_module_cache, weakref)
    ccall((@pysym :Py_DecRef), Cvoid, (PyPtr,), weakref)
    return pyincref_(pynothing[])
end

function ispythonmodule(pyobj::PyPtr)
    true  # FIXME
end

function get_script_module(sessionid::String, py_script_module::PyPtr)
    if !ispythonmodule(py_script_module)
        throw(ArgumentError("get_script_module: a Python module is required"))
    end

    if ispynull(script_module_weakref_callback_obj)
        cf = @cfunction(script_module_removal_callback, PyPtr, (PyPtr, PyPtr))
        script_module_weakref_callback_method[] = PyMethodDef("weakref_callback", cf, METH_O)
        copy!(script_module_weakref_callback_obj,
              PyObject(@pycheckn ccall((@pysym :PyCFunction_NewEx), PyPtr,
                                       (Ref{PyMethodDef}, Ptr{Cvoid}, Ptr{Cvoid}),
                                       script_module_weakref_callback_method, C_NULL, C_NULL)))
    end

    if haskey(session_weakmodule_cache, sessionid)
        weakmod = session_weakmodule_cache[sessionid]
        pymod = @pycheckn ccal((@pysym :PyWeakRef_GetObject), PyPtr, (PyPtr,), weakmod)

        if py_script_module !== pymod
            # On the case that the new python module is attached to the given session,
            # we need to replace the script running module in Julia side
            delete!(script_module_cache, weakmod)
            delete!(session_weakmodule_cache, sessionid)
            return get_script_module(sessionid, py_script_module)
        end
    end

    if !haskey(session_weakmodule_cache, sessionid)
        weakmod = @pycheckn ccall((@pysym :PyWeakRef_New), PyPtr, (PyPtr, PyPtr),
                                  py_script_module, script_module_weakref_callback_obj)
        session_weakmodule_cache[sessionid] = weakmod
    end

    if haskey(script_module_cache, weakmod)
        script_module_cache[weakmod]
    else
        script_module_cache[weakmod] = Module()
    end
end

function eval_for_session(sessionid::String, py_script_module::PyPtr, str::String)
    mod = get_script_module(sessionid, py_script_module)
    @info "eval_for_session" mod py_script_module sessionid
    ast = Meta.parse("begin\n$(str)\nend")
    mod.eval(ast)
end

_showable(a::AbstractVector{<:MIME}, x) = any(m -> showable(m, x), a)
_showable(m, x) = showable(m, x)

struct StreamlitDisplay <: AbstractDisplay end

streamlit_mime_types = Vector{Union{MIME, AbstractVector{MIME}}}([
    MIME("image/svg+xml"),
    [
        MIME("image/png"),
        MIME("image/jpeg")
    ],
    [
        MIME("text/markdown"),
        MIME("text/html"),
    ],
    MIME("text/latex"),
    MIME("text/plain"),
])

israwtext(::MIME, x::AbstractString) = true
israwtext(::MIME"text/plain", x::AbstractString) = false
israwtext(::MIME, x) = false

function display_mime(mime_array::Vector{MIME}, x)
    for m in mime_array
        if _showable(m, x)
            return display_mime(m, x)
        end
    end
    error("No displayable MIME types in mime array.")
end

function display_mime(m::MIME, x)
    buf = IOBuffer()
    sm = string(m)
    if istextmime(m)
        if israwtext(m, x)
            res = String(x)
        else
            show(buf, m, x)
            res = take!(buf)
        end
        return (sm, String(res))
    else
        if isa(x, Vector{UInt8})
            write(buf, x)
        else
            show(buf, m, x)
        end
        return (sm, take!(buf))
    end
end

function display_for_streamlit(x)
    for m in streamlit_mime_types
        try
            if _showable(m, x)
                return display_mime(m, x)
            end
        catch
            if m == MIME("text/plain")
                rethrow()
            end
        end
    end
    return nothing
end

end  # module StreamlitHelper
