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
    database="neo4j",
    optimized=True):
    
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
        optimization_label = "optimized" if optimized else "non-optimized"
        if optimized:
            st.success(f"Neo4j query executed ({optimization_label}) in {end - start:.4f} seconds")
        else:
            st.warning(f"Neo4j query executed ({optimization_label}) in {end - start:.4f} seconds")
    
    if return_dataframe:
        return pd.DataFrame(result)
    else:
        return result

# Fungsi untuk page MongoDB
def mongodb_page():
    st.subheader("📊 Akses Data dari MongoDB - Salon Database")
    
    # -------- Main Area Input --------
    col1, col2 = st.columns(2)
    with col1:
        query_type = st.selectbox("Pilih Jenis Query", ["find", "aggregate"])
    with col2:
        use_index = st.selectbox("Optimasi", ["With Index", "Without Index"])

    st.write("#### Daftar Kolom Transaction Data")
    try:
        client = MongoClient("mongodb://localhost:27017/")
        db = client["SalonDB"]
        collection = db["transactionlog"]
        sample_doc = collection.find_one()
        if sample_doc:
            # Tampilkan struktur data salon
            st.write("**Kolom utama:** `_id`, `id_transaction`, `id_franchise`, `id_employee`, `product`, `transaction_date`, `order_quantity`, `nama_daerah`, `kota`, `kecamatan`, `kode_pos`, `id_salon`")
            st.write("**Kolom product:** `id_product`, `name`")
            st.write("Contoh struktur dokumen:")
            st.json(sample_doc, expanded=False)
        else:
            st.warning("Koleksi tidak memiliki dokumen.")
        client.close()
    except Exception as e:
        st.error(f"Tidak dapat terhubung ke MongoDB: {e}")

    # Query examples untuk salon data
    st.write("#### Contoh Query untuk Salon Data")
    query_examples = {
        "Find by Salon ID": '{"id_salon": 1}',
        "Find by Kota": '{"kota": "Jakarta"}',
        "Aggregate Sales by Salon": '[{"$group": {"_id": "$id_salon", "total_transactions": {"$sum": 1}, "total_quantity": {"$sum": "$order_quantity"}}}]',
        "Aggregate Sales by Product": '[{"$group": {"_id": "$product.name", "total_sales": {"$sum": "$order_quantity"}}}, {"$sort": {"total_sales": -1}}]'
    }
    
    selected_example = st.selectbox("Pilih Contoh Query", list(query_examples.keys()))
    
    query_input = st.text_area(
        "Masukkan Query",
        height=200,
        value=query_examples[selected_example],
        placeholder='Contoh: {"id_salon": 1} atau [{"$match": {"kota": "Jakarta"}}]'
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
                st.write(f"**Total records:** {len(df)}")

        except Exception as e:
            st.error(f"Terjadi kesalahan saat memproses query: {e}")

# Fungsi untuk page Neo4j
def neo4j_page():
    st.subheader("🔗 Akses Data dari Neo4j - Salon Graph Database")
    
    neo4j_uri = "bolt://localhost:7687"
    neo4j_user = "neo4j"
    neo4j_password = "salon1234"
    
    # Optimization option
    st.write("#### Optimasi Query")
    optimization_option = st.selectbox(
        "Pilih Skenario",
        ["Optimized (dengan index & optimasi)", "Non-optimized (tanpa index & optimasi)"]
    )
    optimized = "Optimized" in optimization_option
    
    # Query section
    st.write("#### Node Structure")
    st.info("""
    **Nodes dalam Graph Database:**
    - **Employee**: id, name, id_salon, work_start_hour, work_end_hour
    - **Daerah**: id_salon, nama_daerah, kecamatan, kota, kode_pos  
    - **Product**: id, name, category, price
    - **Franchise**: id_salon, salon_name, year_established
    """)
    
    # Predefined query examples based on optimization
    query_examples = {
        "Get All Employees": "MATCH (e:Employee) RETURN e.id, e.name, e.id_salon, e.work_start_hour, e.work_end_hour LIMIT 20",
        "Get Salon Locations": "MATCH (d:Daerah) RETURN d.id_salon, d.nama_daerah, d.kecamatan, d.kota, d.kode_pos LIMIT 20",
        "Get Products by Category": "MATCH (p:Product) RETURN p.id, p.name, p.category, p.price ORDER BY p.category LIMIT 20",
        "Get Franchises": "MATCH (f:Franchise) RETURN f.id_salon, f.salon_name, f.year_established ORDER BY f.year_established LIMIT 20",
        "Employee-Salon Relationship": "MATCH (e:Employee)-[:WORKS_AT]->(f:Franchise) RETURN e.name, f.salon_name LIMIT 20",
        "Salon-Location Relationship": "MATCH (f:Franchise)-[:LOCATED_IN]->(d:Daerah) RETURN f.salon_name, d.kota, d.kecamatan LIMIT 20"
    }
    
    if optimized:
        default_query = query_examples["Employee-Salon Relationship"]
    else:
        default_query = query_examples["Get All Employees"]
    
    st.write("#### Contoh Query Cypher")
    selected_example = st.selectbox("Pilih Contoh Query", list(query_examples.keys()))
    
    cypher_query = st.text_area(
        "Masukkan Cypher Query",
        height=200,
        value=query_examples[selected_example]
    )

    parameters_input = st.text_area(
        "Parameters (JSON format, opsional)",
        height=68,
        placeholder='{"salon_id": 1, "limit": 10}'
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
                    show_time=show_time,
                    optimized=optimized
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
    
    # Database info section
    st.write("---")
    st.write("#### ℹ️ Informasi Database")
    
    if st.button("📊 Cek Koneksi & Info Database"):
        try:
            with st.spinner("Mengecek koneksi ke Neo4j..."):
                # Test connection with simple query
                info_result = getDataNeo4j(
                    uri=neo4j_uri,
                    username=neo4j_user,
                    password=neo4j_password,
                    query="CALL db.labels() YIELD label RETURN label ORDER BY label",
                    show_time=False,
                    optimized=True
                )
                
                if not info_result.empty:
                    st.success("✅ Koneksi ke Neo4j berhasil!")
                    
                    col1, col2 = st.columns(2)
                    
                    # Show available labels
                    with col1:
                        st.write("**Labels yang tersedia:**")
                        labels = info_result['label'].tolist()
                        for label in labels:
                            st.write(f"• {label}")
                    
                    # Get relationship types
                    with col2:
                        rel_result = getDataNeo4j(
                            uri=neo4j_uri,
                            username=neo4j_user,
                            password=neo4j_password,
                            query="CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType ORDER BY relationshipType",
                            show_time=False,
                            optimized=True
                        )
                        
                        if not rel_result.empty:
                            st.write("**Relationship Types:**")
                            rel_types = rel_result['relationshipType'].tolist()
                            for rel_type in rel_types:
                                st.write(f"• {rel_type}")
                else:
                    st.warning("Koneksi berhasil tapi tidak ada labels yang ditemukan.")
                    
        except Exception as e:
            st.error(f"❌ Gagal terhubung ke Neo4j: {str(e)}")
            st.write("Pastikan:")
            st.write("• Neo4j server sudah berjalan")
            st.write("• URI, username, dan password benar")
            st.write("• Port tidak diblokir firewall")

# Fungsi untuk page Combine
def combine_page():
    st.subheader("🔄 Kombinasi Data MongoDB & Neo4j - Salon Analysis")
    
    # Scenario selection
    st.write("#### Pilih Skenario Optimasi")
    scenario = st.selectbox(
        "Skenario",
        ["Scenario 1: Tanpa Indexing & Optimasi", "Scenario 2: Dengan Indexing & Optimasi"]
    )
    
    use_optimization = "Scenario 2" in scenario
    
    # Predefined combined query examples
    st.write("#### Query Gabungan Tersedia")
    query_options = [
        "Analisis Transaksi per Salon", 
        "Analisis Produk & Layanan per Salon",
        "Analisis Karyawan & Performa Salon",
        "Custom Query"
    ]
    
    selected_query = st.selectbox("Pilih Query Template", query_options)
    
    if selected_query == "Analisis Transaksi per Salon":
        st.write("##### Query: Analisis total transaksi dan quantity per salon")
        
        mongo_query = [
            {
                '$group': {
                    '_id': '$id_salon', 
                    'total_transactions': {'$sum': 1},
                    'total_quantity': {'$sum': '$order_quantity'},
                    'avg_quantity': {'$avg': '$order_quantity'},
                    'transaction_dates': {'$addToSet': '$transaction_date'}
                }
            }, {
                '$project': {
                    'total_transactions': 1,
                    'total_quantity': 1,
                    'avg_quantity': {'$round': ['$avg_quantity', 2]},
                    'unique_days': {'$size': '$transaction_dates'}
                }
            }, {
                '$sort': {'total_transactions': -1}
            }
        ]
        
        if use_optimization:
            neo4j_query = """
            MATCH (f:Franchise)-[:LOCATED_IN]->(d:Daerah)
            WHERE f.id_salon IN $salon_ids
            RETURN f.id_salon, f.salon_name, f.year_established, 
                   d.nama_daerah, d.kota, d.kecamatan, d.kode_pos
            ORDER BY f.id_salon
            """
        else:
            neo4j_query = """
            MATCH (f:Franchise)-[:LOCATED_IN]->(d:Daerah)
            RETURN f.id_salon, f.salon_name, f.year_established, 
                   d.nama_daerah, d.kota, d.kecamatan, d.kode_pos
            ORDER BY f.id_salon
            """
    
    elif selected_query == "Analisis Produk & Layanan per Salon":
        st.write("##### Query: Analisis produk yang dijual per salon dengan detail harga")
        
        mongo_query = [
            {
                '$group': {
                    '_id': {
                        'id_salon': '$id_salon',
                        'product_name': '$product.name'
                    },
                    'total_quantity': {'$sum': '$order_quantity'},
                    'transaction_count': {'$sum': 1}
                }
            }, {
                '$project': {
                    '_id': 0,
                    'id_salon': '$_id.id_salon',
                    'product_name': '$_id.product_name',
                    'total_quantity': 1,
                    'transaction_count': 1,
                    'avg_quantity_per_transaction': {
                        '$divide': ['$total_quantity', '$transaction_count']
                    }
                }
            }, {
                '$sort': {
                    'id_salon': 1,
                    'total_quantity': -1
                }
            }
        ]
        
        if use_optimization:
            neo4j_query = """
            MATCH (f:Franchise)-[:OFFERS]->(p:Product)
            WHERE f.id_salon IN $salon_ids
            RETURN f.id_salon, f.salon_name, p.id as product_id, 
                   p.name as product_name, p.category, p.price
            ORDER BY f.id_salon, p.category
            """
        else:
            neo4j_query = """
            MATCH (f:Franchise)-[:OFFERS]->(p:Product)
            RETURN f.id_salon, f.salon_name, p.id as product_id, 
                   p.name as product_name, p.category, p.price
            ORDER BY f.id_salon
            """
    
    elif selected_query == "Analisis Karyawan & Performa Salon":
        st.write("##### Query: Analisis transaksi per karyawan dan informasi salon")
        
        mongo_query = [
            {
                '$group': {
                    '_id': {
                        'id_salon': '$id_salon',
                        'id_employee': '$id_employee'
                    },
                    'employee_transactions': {'$sum': 1},
                    'employee_total_quantity': {'$sum': '$order_quantity'}
                }
            }, {
                '$group': {
                    '_id': '$_id.id_salon',
                    'total_employees': {'$sum': 1},
                    'total_transactions': {'$sum': '$employee_transactions'},
                    'total_quantity': {'$sum': '$employee_total_quantity'},
                    'employees': {
                        '$push': {
                            'id_employee': '$_id.id_employee',
                            'transactions': '$employee_transactions',
                            'quantity': '$employee_total_quantity'
                        }
                    }
                }
            }, {
                '$project': {
                    'total_employees': 1,
                    'total_transactions': 1,
                    'total_quantity': 1,
                    'avg_transactions_per_employee': {
                        '$divide': ['$total_transactions', '$total_employees']
                    },
                    'top_employee': {
                        '$arrayElemAt': [
                            {'$sortArray': {'input': '$employees', 'sortBy': {'transactions': -1}}},
                            0
                        ]
                    }
                }
            }, {
                '$sort': {'total_transactions': -1}
            }
        ]
        
        if use_optimization:
            neo4j_query = """
            MATCH (f:Franchise)<-[:WORKS_AT]-(e:Employee)
            WHERE f.id_salon IN $salon_ids
            RETURN f.id_salon, f.salon_name, f.year_established,
                   e.id as employee_id, e.name as employee_name, 
                   e.work_start_hour, e.work_end_hour
            ORDER BY f.id_salon, e.name
            """
        else:
            neo4j_query = """
            MATCH (f:Franchise)<-[:WORKS_AT]-(e:Employee)
            RETURN f.id_salon, f.salon_name, f.year_established,
                   e.id as employee_id, e.name as employee_name, 
                   e.work_start_hour, e.work_end_hour
            ORDER BY f.id_salon
            """

    else:  # Custom Query
        st.write("##### Custom Query")
        col1, col2 = st.columns(2)
        with col1:
            st.write("**MongoDB Query (Aggregation Pipeline)**")
            mongo_query_input = st.text_area("MongoDB Query", height=150, 
                placeholder='[{"$match": {"id_salon": 1}}, {"$group": {"_id": "$product.name", "count": {"$sum": 1}}}]')
        with col2:
            st.write("**Neo4j Query (Cypher)**")
            neo4j_query_input = st.text_area("Neo4j Query", height=150,
                placeholder='MATCH (f:Franchise) RETURN f.id_salon, f.salon_name LIMIT 10')
    
    # Execute combined query
    if st.button("🚀 Jalankan Query Gabungan", type="primary"):
        if selected_query == "Custom Query":
            try:
                mongo_query = eval(mongo_query_input) if mongo_query_input.strip() else []
                neo4j_query = neo4j_query_input.strip()
            except:
                st.error("Format query tidak valid!")
                return
        
        if not mongo_query or not neo4j_query:
            st.error("Kedua query harus diisi!")
            return
        
        try:
            col1, col2 = st.columns(2)
            
            # Execute MongoDB query
            with col1:
                st.write("### 📊 Hasil MongoDB")
                with st.spinner("Menjalankan query MongoDB..."):
                    mongo_result = getDataMongoDB(
                        uri="mongodb://localhost:27017/",
                        db_name="SalonDB",
                        collection_name="transactionlog",
                        query_type="aggregate",
                        query=mongo_query,
                        use_index=use_optimization
                    )
                
                if not mongo_result.empty:
                    st.dataframe(mongo_result, use_container_width=True)
                    
                    # Extract salon IDs for Neo4j query
                    if selected_query == "Analisis Transaksi per Salon":
                        salon_ids = mongo_result['_id'].tolist()
                        neo4j_params = {"salon_ids": salon_ids}
                    elif selected_query == "Analisis Produk & Layanan per Salon":
                        salon_ids = mongo_result['id_salon'].unique().tolist()
                        neo4j_params = {"salon_ids": salon_ids}
                    elif selected_query == "Analisis Karyawan & Performa Salon":
                        salon_ids = mongo_result['_id'].tolist()
                        neo4j_params = {"salon_ids": salon_ids}
                    else:
                        neo4j_params = {}
                else:
                    st.warning("Tidak ada data dari MongoDB")
                    neo4j_params = {}
            
            # Execute Neo4j query
            with col2:
                st.write("### 🔗 Hasil Neo4j")
                if neo4j_params or selected_query == "Custom Query":
                    with st.spinner("Menjalankan query Neo4j..."):
                        neo4j_result = getDataNeo4j(
                            uri="bolt://localhost:7687",
                            username="neo4j",
                            password="salon1234",
                            query=neo4j_query,
                            parameters=neo4j_params,
                            optimized=use_optimization
                        )
                    
                    if not neo4j_result.empty:
                        st.dataframe(neo4j_result, use_container_width=True)
                    else:
                        st.warning("Tidak ada data dari Neo4j")
                else:
                    st.warning("Tidak dapat menjalankan Neo4j query - tidak ada parameter")
                    neo4j_result = pd.DataFrame()
            
            # Combine results if both have data
            if not mongo_result.empty and not neo4j_result.empty:
                st.write("---")
                st.write("### 🔄 Hasil Gabungan")
                
                if selected_query == "Analisis Transaksi per Salon":
                    try:
                        combined = pd.merge(
                            mongo_result, 
                            neo4j_result, 
                            left_on='_id', 
                            right_on='id_salon', 
                            how='left'
                        )
                        
                        st.write("#### Analisis Transaksi per Salon dengan Lokasi")
                        if not combined.empty:
                            st.dataframe(combined, use_container_width=True)
                            
                            # Show summary
                            st.write("**Ringkasan:**")
                            st.write(f"- Jumlah salon: {len(combined)}")
                            st.write(f"- Total transaksi semua salon: {combined['total_transactions'].sum()}")
                            st.write(f"- Rata-rata transaksi per salon: {combined['total_transactions'].mean():.2f}")
                            st.write(f"- Total quantity terjual: {combined['total_quantity'].sum()}")
                            
                            # Show top cities
                            if 'kota' in combined.columns:
                                city_summary = combined.groupby('kota')['total_transactions'].sum().sort_values(ascending=False)
                                st.write("**Transaksi per Kota:**")
                                for city, transactions in city_summary.head().items():
                                    st.write(f"- {city}: {transactions} transaksi")
                        else:
                            st.warning("Tidak ada data yang dapat digabungkan.")
                    except Exception as e:
                        st.error(f"Error saat menggabungkan data salon: {str(e)}")
                
                elif selected_query == "Analisis Produk & Layanan per Salon":
                    try:
                        combined = pd.merge(
                            mongo_result, 
                            neo4j_result, 
                            left_on=['id_salon', 'product_name'], 
                            right_on=['id_salon', 'product_name'], 
                            how='inner'
                        )
                        
                        if not combined.empty:
                            # Calculate total revenue per product
                            combined['total_revenue'] = combined['total_quantity'] * combined['price']
                            
                            st.write("#### Analisis Produk & Layanan per Salon dengan Revenue")
                            st.dataframe(combined, use_container_width=True)
                            
                            # Show comprehensive summary
                            st.write("**Ringkasan Detail:**")
                            st.write(f"- Jumlah produk/layanan: {len(combined)}")
                            st.write(f"- Jumlah salon: {combined['id_salon'].nunique()}")
                            st.write(f"- Total quantity terjual: {combined['total_quantity'].sum():,}")
                            st.write(f"- Total revenue: Rp {combined['total_revenue'].sum():,.2f}")
                            
                            # Show top products by revenue
                            product_revenue = combined.groupby('product_name')['total_revenue'].sum().sort_values(ascending=False)
                            st.write("**Top 5 Produk/Layanan Berdasarkan Revenue:**")
                            for product, revenue in product_revenue.head().items():
                                st.write(f"- {product}: Rp {revenue:,.2f}")
                            
                            # Show category analysis
                            if 'category' in combined.columns:
                                category_analysis = combined.groupby('category').agg({
                                    'total_quantity': 'sum',
                                    'total_revenue': 'sum',
                                    'id_product': 'nunique'
                                }).round(2)
                                st.write("**Analisis per Kategori:**")
                                st.dataframe(category_analysis, use_container_width=True)
                            
                            # Show franchise performance
                            franchise_performance = combined.groupby(['id_franchise', 'franchise_name', 'year']).agg({
                                'total_quantity': 'sum',
                                'total_revenue': 'sum',
                                'id_product': 'nunique'
                            }).round(2)
                            franchise_performance.columns = ['Total Quantity', 'Total Revenue', 'Unique Products']
                            st.write("**Performa per Franchise:**")
                            st.dataframe(franchise_performance, use_container_width=True)
                            
                        else:
                            st.warning("Tidak ada data yang dapat digabungkan.")
                    except Exception as e:
                        st.error(f"Error saat menggabungkan data minuman: {str(e)}")
                        import traceback
                        st.write("**Full error traceback:**")
                        st.code(traceback.format_exc())
                
                else:  # Custom query
                    st.write("#### Hasil Custom Query")
                    st.write("**Data MongoDB:**")
                    st.dataframe(mongo_result)
                    st.write("**Data Neo4j:**")
                    st.dataframe(neo4j_result)
                    st.info("Untuk custom query, silakan lakukan analisis manual pada kedua hasil di atas.")
            else:
                if mongo_result.empty:
                    st.warning("Tidak ada data dari MongoDB untuk digabungkan")
                if neo4j_result.empty:
                    st.warning("Tidak ada data dari Neo4j untuk digabungkan")
                    
        except Exception as e:
            st.error(f"Error saat menjalankan query gabungan: {str(e)}")
            import traceback
            st.write("**Full error traceback:**")
            st.code(traceback.format_exc())
    
        # Performance comparison
        st.write("---")
        st.write("#### 📈 Perbandingan Performa")

        st.info("Menjalankan perbandingan performa untuk kedua skenario...")
        
        # Sample query for comparison
        sample_mongo_query = [
            {
                '$unwind': '$product'
            }, {
                '$group': {
                    '_id': '$id_franchise', 
                    'total_sales': {
                        '$sum': '$product.quantity'
                    }, 
                    'transaction_ids': {
                        '$addToSet': '$id_transaction'
                    }
                }
            }, {
                '$project': {
                    'total_sales': 1, 
                    'transaction_count': {
                        '$size': '$transaction_ids'
                    }, 
                    'avg_sales': {
                        '$divide': [
                            '$total_sales', {
                                '$size': '$transaction_ids'
                            }
                        ]
                    }
                }
            }, {
                '$sort': {
                    '_id': 1
                }
            }
        ]
        
        sample_neo4j_query = """MATCH (f:Franchise)-[:IS_LOCATED]->(d:Daerah)
            RETURN f.id_cafe as id_cafe, f.name, f.year, d.kota, d.kecamatan, d.nama_daerah"""
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**Scenario 1: Tanpa Optimasi**")
            start_time = time.time()
            
            # MongoDB without optimization
            mongo_result_1 = getDataMongoDB(
                uri="mongodb://localhost:27017/",
                db_name="SalonDB", 
                collection_name="transactionlog",
                query_type="aggregate",
                query=sample_mongo_query,
                use_index=False,
                show_time=False
            )
            
            # Neo4j without optimization
            neo4j_result_1 = getDataNeo4j(
                uri="bolt://localhost:7687",
                username="neo4j",
                password="salon1234",
                query=sample_neo4j_query,
                optimized=False,
                show_time=False
            )
            
            total_time_1 = time.time() - start_time
            st.warning(f"Total waktu: {total_time_1:.4f} seconds")
        
        with col2:
            st.write("**Scenario 2: Dengan Optimasi**")
            start_time = time.time()
            
            # MongoDB with optimization
            mongo_result_2 = getDataMongoDB(
                uri="mongodb://localhost:27017/",
                db_name="SalonDB",
                collection_name="transactionlog", 
                query_type="aggregate",
                query=sample_mongo_query,
                use_index=True,
                show_time=False
            )
            
            # Neo4j with optimization
            neo4j_result_2 = getDataNeo4j(
                uri="bolt://localhost:7687",
                username="neo4j", 
                password="salon1234",
                query=sample_neo4j_query + " // with optimization",
                optimized=True,
                show_time=False
            )
            
            total_time_2 = time.time() - start_time
            st.success(f"Total waktu: {total_time_2:.4f} seconds")
        
        # Show improvement
        if total_time_1 > 0:
            improvement = ((total_time_1 - total_time_2) / total_time_1) * 100
            st.write(f"### 🎯 Peningkatan Performa: {improvement:.1f}%")
            
            if improvement > 0:
                st.success(f"Scenario 2 lebih cepat {improvement:.1f}% dari Scenario 1")
            else:
                st.warning("Tidak ada peningkatan performa yang signifikan")









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
    
    # Optimization option
    st.write("#### Optimasi Query")
    optimization_option = st.selectbox(
        "Pilih Skenario",
        ["Optimized (dengan index & optimasi)", "Non-optimized (tanpa index & optimasi)"]
    )
    optimized = "Optimized" in optimization_option
    
    # Query section
    st.write("#### Cypher Query")
    
    # Predefined query examples based on optimization
    if optimized:
        default_query = """   MATCH (c:Cabang {id_salon: 1})-[:HAS_EMPLOYEE]->(e:Employee)
    RETURN e.id_employee AS employee_id, e.name AS EmployeeName"""
    else:
        default_query = """MATCH (f:Franchise)-[:HAS_EMPLOYEE]->(e:Employee)
    RETURN e.name, e.id_employee, f.name as franchise_name, f.id_cafe
    LIMIT 20"""
    
    cypher_query = st.text_area(
        "Masukkan Cypher Query",
        height=200,
        value=default_query
    )

    parameters_input = st.text_area(
        "Parameters (JSON format, opsional)",
        height=68,
        placeholder='{"limit": 10, "cafe_id": 1}'
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
                    show_time=show_time,
                    optimized=optimized
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
    
    # Database info section
    st.write("---")
    st.write("#### ℹ️ Informasi Database")
    
    if st.button("📊 Cek Koneksi & Info Database"):
        try:
            with st.spinner("Mengecek koneksi ke Neo4j..."):
                # Test connection with simple query
                info_result = getDataNeo4j(
                    uri=neo4j_uri,
                    username=neo4j_user,
                    password=neo4j_password,
                    query="CALL db.labels() YIELD label RETURN label ORDER BY label",
                    show_time=False,
                    optimized=True
                )
                
                if not info_result.empty:
                    st.success("✅ Koneksi ke Neo4j berhasil!")
                    
                    col1, col2 = st.columns(2)
                    
                    # Show available labels
                    with col1:
                        st.write("**Labels yang tersedia:**")
                        labels = info_result['label'].tolist()
                        for label in labels:
                            st.write(f"• {label}")
                    
                    # Get relationship types
                    with col2:
                        rel_result = getDataNeo4j(
                            uri=neo4j_uri,
                            username=neo4j_user,
                            password=neo4j_password,
                            query="CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType ORDER BY relationshipType",
                            show_time=False,
                            optimized=True
                        )
                        
                        if not rel_result.empty:
                            st.write("**Relationship Types:**")
                            rel_types = rel_result['relationshipType'].tolist()
                            for rel_type in rel_types:
                                st.write(f"• {rel_type}")
                else:
                    st.warning("Koneksi berhasil tapi tidak ada labels yang ditemukan.")
                    
        except Exception as e:
            st.error(f"❌ Gagal terhubung ke Neo4j: {str(e)}")
            st.write("Pastikan:")
            st.write("• Neo4j server sudah berjalan")
            st.write("• URI, username, dan password benar")
            st.write("• Port tidak diblokir firewall")


def combine_page():
    st.header("🤝 Query Gabungan (MongoDB & Neo4j)")
    st.write("Di sini Anda akan menempatkan logika dan UI untuk query gabungan.")
    st.info("Pilih template query atau buat custom query gabungan.")
    # Contoh elemen UI
    optimization = st.selectbox("Pilih Skenario Optimasi", ("Scenario 1 (Tanpa Index)", "Scenario 2 (Dengan Index)"))
    query_template = st.selectbox("Pilih Template Query", ("Pegawai Terbaik Ramadhan", "Penjualan per Franchise", "Custom Query"))

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
                    show_time=True,
                    optimized=False
                )
                if neo_df.empty:
                    st.warning("Tidak ada data ditemukan.")
                else:
                    st.dataframe(neo_df)
                
                joined_df = mongo_df.join(neo_df.set_index(joincol), on=joincol)
                st.dataframe(joined_df)

            except Exception as e:
                st.error(f"Terjadi kesalahan saat memproses query: {e}") 

            


# --- Main Content Berdasarkan Selection ---
if selected == "MongoDB":
    mongodb_page()
elif selected == "Neo4j":
    neo4j_page()
elif selected == "Combine":
    combine_page()