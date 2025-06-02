import streamlit as st
from pymongo import MongoClient
import pandas as pd
import time
from streamlit_option_menu import option_menu
from neo4j import GraphDatabase
import json

# Fungsi ambil data dari MongoDB
def getDataMongoDB(
    uri,
    db_name,
    collection_name,
    query_type="find",
    query=None,
    projection=None,
    return_dataframe=True,
    show_time=True,
    use_index=True):

    client = MongoClient(uri)
    db = client[db_name]
    
    # Pilih collection berdasarkan apakah menggunakan index atau tidak
    if use_index:
        collection = db["indexed"]  # Collection dengan index
        collection_label = "with index"
    else:
        collection = db[collection_name]  # Collection tanpa index
        collection_label = "without index"

    start = time.time()
    try:
        if query_type == "find":
            query = query or {}
            cursor = collection.find(query, projection)
            result = list(cursor)
        elif query_type == "aggregate":
            if not isinstance(query, list):
                raise ValueError("Aggregation query harus dalam bentuk list pipeline.")
            result = list(collection.aggregate(query))
        else:
            raise ValueError("query_type harus 'find' atau 'aggregate'")
    except Exception as e:
        st.error(f"Terjadi error saat query: {e}")
        result = []
    end = time.time()

    if show_time:
        if use_index:
            st.success(f"MongoDB query '{query_type}' executed {collection_label} in {end - start:.4f} seconds")
        else:
            st.warning(f"MongoDB query '{query_type}' executed {collection_label} in {end - start:.4f} seconds")

    client.close()

    if return_dataframe:
        return pd.DataFrame(result)
    else:
        return result
    
def getDataNeo4j(
    uri,
    username,
    password,
    query,
    parameters=None,
    return_dataframe=True,
    show_time=True,
    database="neo4j"):
    
    driver = GraphDatabase.driver(uri, auth=(username, password))
    
    start = time.time()
    result = []
    
    try:
        with driver.session(database=database) as session:
            # Execute query
            response = session.run(query, parameters or {})
            
            # Convert records to list of dictionaries
            result = []
            for record in response:
                # Convert record to dictionary
                record_dict = {}
                for key in record.keys():
                    value = record[key]
                    # Handle Neo4j node/relationship objects
                    if hasattr(value, '__dict__'):
                        if hasattr(value, 'items'):  # Node or Relationship
                            record_dict[key] = dict(value)
                        else:
                            record_dict[key] = str(value)
                    else:
                        record_dict[key] = value
                result.append(record_dict)
                
    except Exception as e:
        st.error(f"Terjadi error saat query Neo4j: {e}")
        result = []
    finally:
        driver.close()
    
    end = time.time()
    
    if show_time:
        st.success(f"Neo4j query executed in {end - start:.4f} seconds")
    
    if return_dataframe:
        return pd.DataFrame(result)
    else:
        return result


# Fungsi untuk page mongodb
def mongodb_page():
    st.subheader("📊 Akses Data dari MongoDB")
    
    # -------- Main Area Input --------
    col1, col2 = st.columns(2)
    with col1:
        query_type = st.selectbox("Pilih Jenis Query", ["find", "aggregate"])
    with col2:
        use_index = st.selectbox("Optimasi", ["With Index", "Without Index"])

    st.write("#### Daftar Kolom")
    try:
        client = MongoClient("mongodb://localhost:27017/")
        db = client["SalonDB"]
        collection = db["transactionlog"]
        sample_doc = collection.find_one()
        if sample_doc:
            st.write(", ".join(f"{key}" for key in sample_doc.keys()))
        else:
            st.warning("Koleksi tidak memiliki dokumen.")
        client.close()
    except Exception as e:
        st.error(f"Tidak dapat terhubung ke MongoDB: {e}")

    query_input = st.text_area(
        "Masukkan Query",
        height=200,
        placeholder='Contoh: {"name": "Michael Smith"} atau [{"$match": {"name": "Michael Smith"}}]'
    )

    run_query = st.button("Jalankan Query")

    # -------- Main Area Output --------
    if run_query:
        try:
            query = eval(query_input)

            df = getDataMongoDB(
                uri="mongodb://localhost:27017/",
                db_name="SalonDB",
                collection_name="transactionlog",
                query_type=query_type,
                query=query,
                projection={"_id": 0} if query_type == "find" else None,
                use_index=(use_index == "With Index")
            )
            st.write("### Hasil Query")
            if df.empty:
                st.warning("Tidak ada data ditemukan.")
            else:
                st.dataframe(df)

        except Exception as e:
            st.error(f"Terjadi kesalahan saat memproses query: {e}")    

def neo4j_page():
    neo4j_uri = "bolt://localhost:7687"
    neo4j_user = "neo4j"
    neo4j_password = "salon1234"
    
    # Query section
    st.write("#### Cypher Query")
    
    cypher_query = st.text_area(
        "Masukkan Cypher Query",
        height=200,
        value="""   MATCH (c:Cabang {id_salon: 1})-[:HAS_EMPLOYEE]->(e:Employee)
        RETURN e.id_employee AS employee_id, e.name AS EmployeeName"""
    )

    parameters_input = st.text_area(
        "Parameters (JSON format, opsional)",
        height=68,
        placeholder='{"limit": 10, "id_salon": 1}'
    )
    
    # Options
    col1, col2 = st.columns(2)
    with col1:
        show_time = st.checkbox("Tampilkan waktu eksekusi", value=True)
    with col2:
        return_dataframe = st.checkbox("Return sebagai DataFrame", value=True)
    
    # Execute query button
    if st.button("🚀 Jalankan Cypher Query", type="primary"):
        if not cypher_query.strip():
            st.error("Query tidak boleh kosong!")
            return
            
        try:
            # Parse parameters if provided
            parameters = None
            if parameters_input.strip():
                try:
                    parameters = json.loads(parameters_input)
                except json.JSONDecodeError as e:
                    st.error(f"Format JSON parameters tidak valid: {e}")
                    return
            
            # Execute query using the Neo4j function
            with st.spinner("Menjalankan query Neo4j..."):
                result = getDataNeo4j(
                    uri=neo4j_uri,
                    username=neo4j_user,
                    password=neo4j_password,
                    query=cypher_query,
                    parameters=parameters,
                    return_dataframe=return_dataframe,
                    show_time=show_time
                )
            
            # Display results
            if return_dataframe:
                if not result.empty:
                    st.write(f"**Hasil Query:** {len(result)} record(s)")
                    st.dataframe(result, use_container_width=True)
                    
                    # Show summary statistics for numeric columns
                    numeric_cols = result.select_dtypes(include=['number']).columns
                    if len(numeric_cols) > 0:
                        st.write("**Statistik Numerik:**")
                        st.dataframe(result[numeric_cols].describe())
                else:
                    st.info("Query berhasil dijalankan tapi tidak ada data yang ditampilkan.")
            else:
                if result:
                    st.write(f"**Hasil Query:** {len(result)} record(s)")
                    st.json(result)
                else:
                    st.info("Query berhasil dijalankan tapi tidak ada data yang ditampilkan.")
                    
        except Exception as e:
            st.error(f"Error saat menjalankan query: {str(e)}")


def combine_page():
    st.header("🤝 Query Gabungan (MongoDB & Neo4j)")
    query_template = st.selectbox("Pilih Template Query", ("Template 1", "Template 2", "Custom Query"))

    if query_template == "Custom Query":
        col1, col2 = st.columns(2)
        with col1:
            query_type = st.selectbox("Pilih Jenis Query", ["find", "aggregate"])
        with col2:
            use_index = st.selectbox("Optimasi", ["With Index", "Without Index"])

        qmongo = st.text_area(
            "Masukkan Custom Query MongoDB",
            height=100,
            placeholder='Contoh: {"name": "Michael Smith"} atau [{"$match": {"name": "Michael Smith"}}]'
        )

        qneo = st.text_area("Masukkan Custom Query Neo4j", "", height=100)
        joincol = st.text_area("Masukkan Kolom Join", "", height=100)


    if st.button("Show Result"):
        if(query_template=="Custom Query"):
            try:
                qmongo = eval(qmongo)

                mongo_df = getDataMongoDB(
                    uri="mongodb://localhost:27017/",
                    db_name="SalonDB",
                    collection_name="transactionlog",
                    query_type=query_type,
                    query=qmongo,
                    projection={"_id": 0} if query_type == "find" else None,
                    use_index=(use_index == "With Index")
                )
                if mongo_df.empty:
                    st.warning("Tidak ada data ditemukan.")
                else:
                    st.dataframe(mongo_df)

                neo_df = getDataNeo4j(
                    uri="bolt://localhost:7687",
                    username="neo4j",
                    password="salon1234",
                    query=qneo,
                    parameters=None,
                    return_dataframe=True,
                    show_time=True
                )
                if neo_df.empty:
                    st.warning("Tidak ada data ditemukan.")
                else:
                    st.dataframe(neo_df)
                
                joined_df = mongo_df.join(neo_df.set_index(joincol), on=joincol)
                st.dataframe(joined_df)

            except Exception as e:
                st.error(f"Terjadi kesalahan saat memproses query: {e}") 

            

# ================= Streamlit App =================
# Set page config harus di awal
st.set_page_config(layout="wide", page_title="Query Database Salon",
                   initial_sidebar_state="expanded")

# --- CSS Kustom ---
st.markdown("""
<style>
    /* Mengatur jarak dari atas untuk seluruh konten utama aplikasi */
    .block-container {
        padding-top: 2rem; /* Menambahkan padding atas 2cm */
        padding-bottom: 1rem;
        padding-left: 1rem;
        padding-right: 1rem;
    }

    /* Mengatur posisi horizontal menu topbar */
    div[data-testid="stVerticalBlock"] > div:first-child .st-emotion-cache-1pxe4x7 { /* Class untuk option_menu container */
        flex-direction: row !important;
        justify-content: center !important;
        width: 100%;
        margin-top: -20px; /* Menarik menu ke atas sedikit */
    }

    /* Menyesuaikan padding konten utama Streamlit */
    .css-1av0mt5 { /* Streamlit main content padding */
        padding-top: 0rem;
    }

    /* Styling tambahan untuk topbar container itu sendiri */
    .st-emotion-cache-z5fcl4 { /* Ini bisa berbeda. Periksa di browser Anda */
        background-color: #f0f2f6;
        padding: 0.5rem 1rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 2rem;
        border-radius: 10px;
    }

    /* Styling item individu di topbar menu */
    div[data-testid="stVerticalBlock"] > div:first-child .st-emotion-cache-1pxe4x7 .st-emotion-cache-1y4qm01 { /* Class untuk item menu individu */
        margin-left: 0.5rem;
        margin-right: 0.5rem;
        padding: 0.5rem 1rem;
    }

    div[data-testid="stVerticalBlock"] > div:first-child .st-emotion-cache-1y4qm01 > div > p {
        font-size: 16px !important;
    }

    /* Override gaya default Streamlit untuk judul */
    h1 {
        color: #2e8b57;
        text-align: center;
        font-size: 3em;
        margin-bottom: 1rem;
        text-shadow: 1px 1px 2px rgba(0,0,0,0.1);
    }

    /* Gaya untuk subheader */
    h2 {
        color: #4CAF50;
        border-bottom: 2px solid #4CAF50;
        padding-bottom: 5px;
        margin-top: 2rem;
    }

    /* Gaya untuk tombol */
    .stButton > button {
        background-color: #4CAF50;
        color: white;
        border-radius: 8px;
        padding: 10px 20px;
        font-size: 16px;
        border: none;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.2);
        transition: all 0.3s ease-in-out;
    }
    .stButton > button:hover {
        background-color: #45a049;
        transform: translateY(-2px);
        box-shadow: 4px 4px 10px rgba(0,0,0,0.3);
    }

    /* Gaya untuk input text area, text input, selectbox */
    .stTextArea > label, .stTextInput > label, .stSelectbox > label {
        font-weight: bold;
        color: #333;
    }

    /* Gaya untuk expander */
    .streamlit-expanderHeader {
        background-color: #e6ffe6;
        color: #2e8b57;
        font-weight: bold;
        border-radius: 5px;
        padding: 10px;
        border: 1px solid #c8e6c9;
    }

    /* Gaya untuk tabel/data frame */
    .dataframe {
        border: 1px solid #ddd;
        border-collapse: collapse;
        width: 100%;
        margin-top: 1rem;
        box-shadow: 0 0 10px rgba(0,0,0,0.1);
    }
    .dataframe th {
        background-color: #4CAF50;
        color: white;
        padding: 8px;
        text-align: left;
    }
    .dataframe td {
        padding: 8px;
        border: 1px solid #ddd;
    }
    .dataframe tr:nth-child(even) {
        background-color: #f2f2f2;
    }

    /* Sidebar Styling */
    [data-testid="stSidebar"] {
        background-color: #B2D8CE !important;
        padding-top: 2rem;
    }
    /* Menyejajarkan judul sidebar dengan ikon */
    [data-testid="stSidebar"] h1 {
        display: flex;
        align-items: center; /* Menyejajarkan item secara vertikal di tengah */
        gap: 8px; /* Memberi sedikit jarak antara ikon dan teks */
        font-size: 1.5em; /* Ukuran font tetap sama */
        color: #2e8b57 !important; /* Warna teks judul sidebar */
        margin-bottom: 1rem; /* Jaga margin bawah */
    }
    /* Mengubah warna teks markdown di sidebar agar kontras */
    [data-testid="stSidebar"] p {
        color: #333 !important;
    }
    /* Untuk teks developer yang bold */
    [data-testid="stSidebar"] b {
        color: #004d40 !important;
    }
    /* Untuk teks email (jika dirender sebagai anchor/link) */
    [data-testid="stSidebar"] a {
        color: #00796B !important;
    }

</style>
""", unsafe_allow_html=True)

# --- Judul Aplikasi ---
st.title("🚀 Query Database Salon")

# --- Topbar Navigation ---
with st.container():
    selected = option_menu(
        menu_title=None,
        options=["MongoDB", "Neo4j", "Combine"],
        icons=["database", "diagram-3", "layers"],
        menu_icon="server",
        default_index=0,
        orientation="horizontal",
        styles={
            "container": {"padding": "0!important", "background-color": "#f0f2f6", "border-radius": "10px", "box-shadow": "0 2px 10px rgba(0,0,0,0.1)", "margin-bottom": "20px"},
            "icon": {"color": "#00796B", "font-size": "18px"},
            "nav-link": {"font-size": "16px", "text-align": "center", "margin":"0px", "--hover-color": "#e0f2f1", "padding": "10px 20px", "border-radius": "8px"},
            "nav-link-selected": {"background-color": "#004d40", "color": "white"},
        }
    )

# --- Sidebar Navigation ---
with st.sidebar:
    st.markdown("---")
    # Bagian ini yang diubah untuk penyejajaran
    st.title("📌 Panduan")

    if selected == "MongoDB":
        st.markdown("""
        **MongoDB Query:**
        1. Pilih jenis query: `find` atau `aggregate`
        2. Pilih optimasi: `With Index` atau `Without Index`
        3. Masukkan query dalam format Python dict atau list
        4. Klik tombol **Jalankan Query**
        5. Bandingkan performa kedua skenario
        """)
    elif selected == "Neo4j":
        st.markdown("""
        **Neo4j Query:**
        1. Pilih skenario optimasi
        2. Masukkan Cypher query (atau gunakan template)
        3. Tambahkan parameters jika diperlukan
        4. Klik tombol **Jalankan Cypher Query**
        5. Lihat perbedaan performa
        """)
    else:  # Combine
        st.markdown("""
        **Combine Data:**
        1. Pilih skenario optimasi
        2. Pilih template query atau buat custom
        3. Klik tombol **Jalankan Query Gabungan**
        4. Lihat hasil gabungan dari kedua database
        5. Bandingkan performa kedua skenario
        """)

    st.markdown("---")
    # Bagian ini yang diubah untuk penyejajaran
    st.title("👨‍💻 Developer")
    st.markdown("""
    <b>Afeef Radithya Rashid</b><br>
    📧 Afeef123@gmail.com<br><br>
    <b>Daffa Aqil Shadiq</b><br>
    📧 dfshadiq9@gmail.com
    """, unsafe_allow_html=True)


# --- Main Content Berdasarkan Selection ---
if selected == "MongoDB":
    mongodb_page()
elif selected == "Neo4j":
    neo4j_page()
elif selected == "Combine":
    combine_page()