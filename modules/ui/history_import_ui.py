"""History Import UI.

UI for importing historical training files from 'treningi_csv' folder.
"""
import html
import streamlit as st
from pathlib import Path

from modules.history_import import (
    import_training_folder, 
    get_available_files, 
    TRAINING_FOLDER
)
from modules.db import SessionStore


def render_history_import_tab(cp: float = 280):
    """Render the history import UI tab.
    
    Args:
        cp: Critical Power for TSS calculations
    """
    st.header("📂 Import Historycznych Treningów")
    
    store = SessionStore()
    current_count = store.get_session_count()
    
    st.info(f"""
    **Folder źródłowy:** `{TRAINING_FOLDER}`
    
    **Aktualne sesje w bazie:** {current_count}
    """)
    
    # Check available files
    available = get_available_files()
    
    if not available:
        st.warning("Brak plików CSV w folderze 'treningi_csv'.")
        return
    
    # Display available files
    st.subheader(f"📋 Dostępne pliki ({len(available)})")
    
    with st.expander("Pokaż listę plików", expanded=False):
        for f in available[:20]:  # Show first 20
            size_kb = f['size'] / 1024
            st.markdown(f"- `{f['date']}` - {f['name']} ({size_kb:.0f} KB)")
        
        if len(available) > 20:
            st.caption(f"...i {len(available) - 20} więcej")
    
    # Import settings
    st.divider()
    st.subheader("⚙️ Ustawienia importu")
    
    col1, col2 = st.columns(2)
    
    with col1:
        cp_import = st.number_input(
            "CP/FTP dla obliczeń TSS [W]",
            min_value=100,
            max_value=500,
            value=int(cp),
            help="Moc krytyczna używana do obliczania TSS historycznych treningów"
        )
    
    with col2:
        st.metric("Pliki do importu", len(available))
    
    # Import button
    st.divider()
    
    if st.button("🚀 Importuj wszystkie pliki", type="primary", use_container_width=True):
        with st.spinner("Importowanie..."):
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            def progress_callback(current, total, message):
                progress_bar.progress(current / total)
                status_text.text(f"[{current}/{total}] {message}")
            
            success, fail, messages = import_training_folder(
                cp=cp_import,
                progress_callback=progress_callback
            )
            
            progress_bar.empty()
            status_text.empty()
            
            # Show results
            if success > 0:
                st.success(f"✅ Zaimportowano **{success}** treningów!")
            
            if fail > 0:
                st.warning(f"⚠️ Nieudane: **{fail}** plików")
            
            # Show details with XSS protection
            with st.expander("Szczegóły importu"):
                for msg in messages:
                    escaped_msg = html.escape(msg)
                    if msg.startswith("✅"):
                        st.markdown(f"<span style='color: green'>{escaped_msg}</span>", unsafe_allow_html=True)
                    else:
                        st.markdown(f"<span style='color: red'>{escaped_msg}</span>", unsafe_allow_html=True)

            # Refresh count
            new_count = store.get_session_count()
            st.info(f"**Sesje w bazie po imporcie:** {new_count}")
    
    # Manual file selection
    st.divider()
    st.subheader("📁 Import wybranych plików")
    
    selected = st.multiselect(
        "Wybierz pliki do importu",
        options=[f['name'] for f in available],
        default=[]
    )
    
    if selected and st.button("Importuj wybrane"):
        from modules.history_import import import_single_file
        
        with st.spinner("Importowanie wybranych..."):
            for filename in selected:
                # Path traversal protection: validate the resolved path is within TRAINING_FOLDER
                filepath = TRAINING_FOLDER / filename
                try:
                    resolved_path = filepath.resolve()
                    training_folder_resolved = TRAINING_FOLDER.resolve()
                    
                    # Python 3.9+: use is_relative_to, fallback to string comparison
                    if hasattr(resolved_path, 'is_relative_to'):
                        if not resolved_path.is_relative_to(training_folder_resolved):
                            st.error(f"❌ Nieprawidłowa ścieżka pliku: {html.escape(filename)}")
                            continue
                    else:
                        # Fallback for older Python versions
                        if not str(resolved_path).startswith(str(training_folder_resolved)):
                            st.error(f"❌ Nieprawidłowa ścieżka pliku: {html.escape(filename)}")
                            continue
                    
                    if not resolved_path.exists():
                        st.error(f"❌ Plik nie istnieje: {html.escape(filename)}")
                        continue
                    
                    success, msg = import_single_file(resolved_path, cp_import)
                    # XSS protection for message display
                    escaped_msg = html.escape(msg)
                    if success:
                        st.success(escaped_msg)
                    else:
                        st.error(escaped_msg)
                        
                except Exception as e:
                    st.error(f"❌ Błąd przetwarzania pliku {html.escape(filename)}: {html.escape(str(e))}")
