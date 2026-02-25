import streamlit as st
import pandas as pd

from auth import require_login, logout_button
from db import echo ( 
    init_db,echo     get_users,echo     list_tasks,echo     create_task,echo     update_task_meta,echo     delete_task,echo     # items
    list_items,echo     add_item,echo     update_item,echo     toggle_item_done,echo     delete_item,echo     move_item,echo     # logs
    add_task_log,echo     get_task_logs,echo )

st.set_page_config(page_title="Work Visibility - TODO", layout="wide"
