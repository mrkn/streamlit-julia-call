module StreamlitHelper

import PyCall
import PyCall: PyObject, PyPtr, PyNULL, PyMethodDef, METH_O, @pysym, @pycheckn, pyincref_, pynothing, ispynull

const _lock = ReentrantLock()

# The mapping from a weakref of Python module to the corresponding session ID
const weakmodule_session_cache = Dict{PyPtr,String}()

# The mapping from a session ID to the corresponding weakref of Python module
const session_weakmodule_cache = Dict{String,PyPtr}()

# The mapping from a session ID to the corresponding Julia module
const script_module_cache = Dict{String,Module}()

# weakref_callback Python method
const script_module_weakref_callback_obj = PyNULL()

# Python expects the PyMethodDef structure to be a constant, so we put it in a
# global to prevent GC.
const script_module_weakref_callback_method = Ref{PyMethodDef}()

function script_module_removal_callback(callback::PyPtr, weakref::PyPtr)
    lock(_lock) do
        delete!(weakmodule_session_cache, weakref)
        ccall((@pysym :Py_DecRef), Cvoid, (PyPtr,), weakref)
    end
    println("script_module_removal_callback: weakref=$(weakref)")
    return pyincref_(pynothing[])
end

function ispythonmodule(pyobj::PyPtr)
    true  # FIXME
end

function get_script_module(sessionid::String, py_script_module::PyPtr)
    @info "get_script_module" sessionid py_script_module

    if !ispythonmodule(py_script_module)
        throw(ArgumentError("get_script_module: a Python module is required"))
    end

    if ispynull(script_module_weakref_callback_obj)
        @info "get_script_module: Initialize script_module_weakref_callback_obj"
        cf = @cfunction(script_module_removal_callback, PyPtr, (PyPtr, PyPtr))
        script_module_weakref_callback_method[] = PyMethodDef("weakref_callback", cf, METH_O)
        copy!(script_module_weakref_callback_obj,
              PyObject(@pycheckn ccall((@pysym :PyCFunction_NewEx), PyPtr,
                                       (Ref{PyMethodDef}, Ptr{Cvoid}, Ptr{Cvoid}),
                                       script_module_weakref_callback_method, C_NULL, C_NULL)))
    end

    lock(_lock) do
        if haskey(session_weakmodule_cache, sessionid)
            @info "get_script_module: session_weakmodule_cache has a value to the given sessionid"

            weakmod = session_weakmodule_cache[sessionid]
            @info "get_script_module" weakmod

            pymod = if !haskey(weakmodule_session_cache, weakmod)
                @info "get_script_module: The weakmod corersponding to the given sessionid is invalid"
                nothing
            else
                @pycheckn ccall((@pysym :PyWeakref_GetObject), PyPtr, (PyPtr,), weakmod)
            end

            @info "get_script_module" pymod

            if py_script_module !== pymod
                # On the case that the new python module is attached to the given session,
                # we need to replace the script running module in Julia side
                pymod !== nothing && @info "get_script_module: python module was replaced"

                delete!(session_weakmodule_cache, sessionid)
                delete!(weakmodule_session_cache, weakmod)
                delete!(script_module_cache, sessionid)
                return get_script_module(sessionid, py_script_module)
            end
        end

        if !haskey(session_weakmodule_cache, sessionid)
            @info "get_script_module: session_weakmodule_cache does not have a value to the given sessionid"
            weakmod = @pycheckn ccall((@pysym :PyWeakref_NewRef), PyPtr, (PyPtr, PyPtr),
                                      py_script_module, script_module_weakref_callback_obj)
            @info "get_script_module: register a weakmod to the sessionid" sessionid weakmod
            session_weakmodule_cache[sessionid] = weakmod
            weakmodule_session_cache[weakmod] = sessionid
        end

        @info "get_script_module" weakmod get(script_module_cache, sessionid, nothing)

        if haskey(script_module_cache, sessionid)
            @info "get_script_module: script_module already exists"
            script_module_cache[sessionid]
        else
            @info "get_script_module: script_module is newly created"
            script_module_cache[sessionid] = Module()
        end
    end
end

function eval_for_session(sessionid, py_script_module, str)
    @info "eval_for_session" sessionid typeof(sessionid) py_script_module typeof(py_script_module) typeof(str)
    mod = get_script_module(sessionid, PyPtr(py_script_module))
    @info "eval_for_session: script_module is obtained" mod
    ast = Meta.parse("begin\n$(str)\nend")
    @info "eeval_for_session" ast
    Core.eval(mod, ast)
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
