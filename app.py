import streamlit as st

from lecture_rag import store
from lecture_rag.pipeline import answer, build_index
from lecture_rag.utils import youtube_id

st.set_page_config(page_title="Lecture RAG", page_icon="🎓")
st.title("🎓 Lecture Q&A with timestamps")

with st.sidebar:
    st.header("Add a lecture")
    source = st.text_input("YouTube/NPTEL URL or local file path")
    model = st.selectbox("Whisper model", ["tiny", "base", "small", "medium"], index=2)
    if st.button("Index lecture") and source:
        with st.status("Indexing...", expanded=True) as status:
            vid = build_index(source.strip(), model, log=st.write)
            status.update(label="Done", state="complete")
        st.session_state["video_id"] = vid

videos = store.list_videos()
if not videos:
    st.info("Index a lecture from the sidebar to begin.")
    st.stop()

ids = list(videos)
default = ids.index(st.session_state["video_id"]) if st.session_state.get("video_id") in ids else 0
vid = st.selectbox("Lecture", ids, index=default, format_func=lambda i: videos[i])
meta, _, _ = store.load(vid)

if youtube_id(meta["source"]):
    st.video(meta["source"], start_time=st.session_state.get("start", 0))

q = st.text_input("Ask a question about this lecture")
if q:
    with st.spinner("Searching..."):
        r = answer(vid, q)
    st.markdown(r["answer"])
    st.success(f"Explained at **{r['timestamp']}**  ·  [open in YouTube]({r['url']})")
    if st.button(f"▶ Jump player to {r['timestamp']}"):
        st.session_state["start"] = r["seconds"]
        st.rerun()
    with st.expander("Retrieved sections"):
        for s in r["sources"]:
            st.markdown(f"**{s['time']}** (score {s['score']})\n\n{s['text']}")
