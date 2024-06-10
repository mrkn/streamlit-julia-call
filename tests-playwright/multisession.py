import streamlit as st
from streamlit_julia_call import julia_eval, julia_display
import time

# st.write("x = 0")

julia_eval("""
x = 0
""")

st.write(julia_eval("x += 1"))

time.sleep(2)

st.write(julia_eval("x += 1"))
