import streamlit as st
from streamlit_julia_call import julia_eval, julia_display

st.markdown("""
```julia
using CairoMakie, CSV, DataFrames
```
""")

julia_eval("""
using CairoMakie, CSV, DataFrames
""")

st.markdown("""
```julia
f = Figure()
ax = Axis(f[1, 1])
x = range(0, 10, length=100)
y = cos.(x)
lines!(ax, x, y)
f
```
""")

julia_display("""
f = Figure()
ax = Axis(f[1, 1])
x = range(0, 10, length=100)
y = cos.(x)
lines!(ax, x, y)
f
""")

# julia_display("""CSV.read("housing.csv", DataFrame)""")
