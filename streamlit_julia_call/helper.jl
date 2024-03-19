module StreamlitHelper

function eval_for_session(sessionid::String, str::String)
    ast = Meta.parse("begin\n$(str)\nend")
    Main.eval(ast)
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
