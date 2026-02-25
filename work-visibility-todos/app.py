import streamlit as st
import pandas as pd

from auth import require_login, logout_button
from db import (
    init_db,
    get_users,
    list_tasks,
    create_task,
    update_task_meta,
    delete_task,
    # items
    list_items,
    add_item,
    update_item,
    toggle_item_done,
    delete_item,
    move_item,
    # logs
    add_task_log,
    get_task_logs,
)

st.set_page_config(page_title="Work Visibility - TODO", layout="wide")

STATUS = ["Todo", "In Progress", "Blocked", "Done"]
PRIORITY = ["Low", "Medium", "High"]

def _badge(status: str) -> str:
    return {
        "Todo": "🟦 Todo",
        "In Progress": "🟨 In Progress",
        "Blocked": "🟥 Blocked",
        "Done": "🟩 Done",
    }.get(status, status)

def main():
    init_db()
    user = require_login()
    users = get_users()
    usernames = [u["username"] for u in users]

    st.title("Work Visibility - TODO (Checklist)")
    st.caption("Create tasks, add checklist items, and track progress in one place.")

    top_l, top_r = st.columns([3, 1])
    with top_l:
        st.write(f"Signed in as **{user['username']}**")
    with top_r:
        logout_button()

    st.divider()

    # -----------------------------
    # Sidebar: filters + create task
    # -----------------------------
    st.sidebar.header("Filters")
    owner_filter = st.sidebar.multiselect("Owner", usernames, default=[user["username"]])
    status_filter = st.sidebar.multiselect("Status", STATUS, default=["Todo", "In Progress", "Blocked"])
    search = st.sidebar.text_input("Search tasks (title/desc/tags)")
    st.sidebar.divider()

    st.sidebar.header("Create a task")
    with st.sidebar.form("create_task_form", clear_on_submit=True):
        title = st.text_input("Title *")
        desc = st.text_area("Description")
        tags = st.text_input("Tags (comma-separated)")
        owner = st.selectbox("Owner", usernames, index=usernames.index(user["username"]))
        priority = st.selectbox("Priority", PRIORITY, index=1)
        status = st.selectbox("Status", STATUS, index=0)
        due_date = st.date_input("Due date", value=None)

        if st.form_submit_button("Create task"):
            if not title.strip():
                st.error("Title is required.")
            else:
                tid = create_task(
                    title=title.strip(),
                    description=desc.strip(),
                    tags=tags.strip(),
                    owner=owner,
                    priority=priority,
                    status=status,
                    due_date=str(due_date) if due_date else None,
                    created_by=user["username"],
                )
                add_task_log(tid, user["username"], f"Created task (status={status}, owner={owner})")
                st.success("Task created.")
                st.rerun()

    # -----------------------------
    # Task list
    # -----------------------------
    tasks = list_tasks(owners=owner_filter, statuses=status_filter, search=search.strip() or None)

    st.subheader("Tasks")
    if not tasks:
        st.info("No tasks match your filters.")
        return

    df = pd.DataFrame(tasks)
    df["status_badge"] = df["status"].apply(_badge)

    # Show progress per task
    progress = []
    for tid in df["id"].tolist():
        items = list_items(int(tid))
        if len(items) == 0:
            progress.append("—")
        else:
            done = sum(1 for it in items if it["is_done"])
            progress.append(f"{done}/{len(items)}")
    df["items_done"] = progress

    view = df[["id", "status_badge", "title", "owner", "priority", "due_date", "items_done", "tags", "updated_at"]].rename(
        columns={"status_badge": "status", "due_date": "due", "items_done": "items"}
    )
    st.dataframe(view, use_container_width=True, hide_index=True)

    st.divider()

    # -----------------------------
    # Select a task to manage
    # -----------------------------
    st.subheader("Manage a task")
    selected_id = st.selectbox("Select Task ID", options=df["id"].tolist())
    task = df[df["id"] == selected_id].iloc[0].to_dict()

    left, right = st.columns([2, 3], gap="large")

    # -----------------------------
    # Left: task meta edit
    # -----------------------------
    with left:
        st.markdown("#### Task details")
        with st.form("task_meta_form"):
            t_title = st.text_input("Title", value=task["title"])
            t_desc = st.text_area("Description", value=task.get("description") or "")
            t_tags = st.text_input("Tags", value=task.get("tags") or "")
            t_owner = st.selectbox("Owner", usernames, index=usernames.index(task["owner"]))
            t_priority = st.selectbox("Priority", PRIORITY, index=PRIORITY.index(task["priority"]))
            t_status = st.selectbox("Status", STATUS, index=STATUS.index(task["status"]))

            due_val = pd.to_datetime(task["due_date"]).date() if task["due_date"] else None
            t_due = st.date_input("Due date", value=due_val)

            note = st.text_area("Log note (optional)", placeholder="e.g., Waiting for data from X")

            c1, c2 = st.columns(2)
            save = c1.form_submit_button("Save task")
            delete = c2.form_submit_button("Delete task")

            if save:
                update_task_meta(
                    task_id=int(selected_id),
                    title=t_title.strip(),
                    description=t_desc.strip(),
                    tags=t_tags.strip(),
                    owner=t_owner,
                    priority=t_priority,
                    status=t_status,
                    due_date=str(t_due) if t_due else None,
                    updated_by=user["username"],
                )
                if note.strip():
                    add_task_log(int(selected_id), user["username"], note.strip())
                else:
                    add_task_log(int(selected_id), user["username"], "Updated task meta")
                st.success("Saved.")
                st.rerun()

            if delete:
                delete_task(int(selected_id))
                st.warning("Task deleted.")
                st.rerun()

    # -----------------------------
    # Right: checklist items
    # -----------------------------
    with right:
        st.markdown("#### Checklist items")
        items = list_items(int(selected_id))

        # Add item
        with st.form("add_item_form", clear_on_submit=True):
            new_text = st.text_input("New item")
            if st.form_submit_button("Add item"):
                if new_text.strip():
                    add_item(int(selected_id), new_text.strip(), created_by=user["username"])
                    add_task_log(int(selected_id), user["username"], f"Added item: {new_text.strip()}")
                    st.rerun()
                else:
                    st.error("Item text cannot be empty.")

        if not items:
            st.caption("No items yet. Add the first checklist item above.")
        else:
            # Render items with controls
            for it in items:
                row = st.columns([0.6, 6, 1, 1, 1])
                with row[0]:
                    checked = st.checkbox("done", value=bool(it["is_done"]), key=f"chk_{it['id']}", label_visibility="collapsed")
                    if checked != bool(it["is_done"]):
                        toggle_item_done(int(it["id"]), checked, updated_by=user["username"])
                        add_task_log(int(selected_id), user["username"], f"Toggled item {'done' if checked else 'not done'}: {it['text']}")
                        st.rerun()

                with row[1]:
                    edited = st.text_input("text", value=it["text"], key=f"txt_{it['id']}", label_visibility="collapsed")

                with row[2]:
                    if st.button("Save", key=f"save_{it['id']}"):
                        if edited.strip():
                            update_item(int(it["id"]), edited.strip(), updated_by=user["username"])
                            add_task_log(int(selected_id), user["username"], f"Edited item: {edited.strip()}")
                            st.rerun()
                        else:
                            st.error("Item text cannot be empty.")

                with row[3]:
                    if st.button("↑", key=f"up_{it['id']}"):
                        move_item(int(it["id"]), direction="up")
                        st.rerun()

                with row[4]:
                    if st.button("🗑", key=f"del_{it['id']}"):
                        delete_item(int(it["id"]))
                        add_task_log(int(selected_id), user["username"], f"Deleted item: {it['text']}")
                        st.rerun()

        st.divider()
        st.markdown("#### Task log")
        logs = get_task_logs(int(selected_id))
        if not logs:
            st.caption("No logs yet.")
        else:
            for lg in logs:
                st.markdown(f"- **{lg['created_at']}** — `{lg['actor']}`: {lg['message']}")

if __name__ == "__main__":
    main()
