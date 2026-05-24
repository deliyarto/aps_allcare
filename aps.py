import streamlit as st
import pandas as pd
import datetime
import plotly.express as px
import os  # Library tambahan untuk mengecek status file

# ==========================================
# CONFIGURASI UTAMA (SESUAIKAN DI SINI)
# ==========================================
STATUS_AMAN = ["Pembayaran Berhasil", "Ditolak", "Klaim Selesai"] 

# ==========================================
# KONFIGURASI HALAMAN
# ==========================================
st.set_page_config(page_title="Dashboard Klaim Yakes Pertamina", page_icon="🏥", layout="wide")

# ==========================================
# 0. SISTEM LOGIN
# ==========================================
def check_login(username, password):
    """Verifikasi username & password terhadap daftar di st.secrets."""
    users = st.secrets.get("users", {})
    return users.get(username) == password

def show_login_page():
    """Tampilkan halaman login."""
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown("## 🏥 Dashboard Klaim Yakes Pertamina")
        st.markdown("Silakan login untuk melanjutkan.")
        st.divider()
        username = st.text_input("Username", placeholder="Masukkan username")
        password = st.text_input("Password", type="password", placeholder="Masukkan password")
        if st.button("Login", use_container_width=True, type="primary"):
            if check_login(username, password):
                st.session_state["logged_in"] = True
                st.session_state["username"] = username
                st.rerun()
            else:
                st.error("Username atau password salah.")

# Cek status login
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

if not st.session_state["logged_in"]:
    show_login_page()
    st.stop()

# ==========================================
# KONTEN UTAMA (hanya tampil setelah login)
# ==========================================
st.title("🏥 Dashboard Monitoring & Pengingat Klaim RS")
st.markdown("Aplikasi Manajemen Operasional Tagihan Unit/RS kepada Yakes Pertamina.")

# ==========================================
# 1. LOAD DATA & PRE-PROCESSING (DENGAN AUTO-REFRESH)
# ==========================================
# ttl=1800 berarti cache otomatis kadaluarsa setiap 30 menit
@st.cache_data(ttl=1800)
def load_data(file_mtime):
    # Parameter file_mtime memastikan fungsi ini berjalan ulang JIKA file csv di-replace
    df = pd.read_csv("data/aps.csv", sep=";", encoding="utf-8-sig")
    
    df = df.rename(columns={'Total Bayar': 'Total Tagihan'})
    df['Tanggal Ajuan'] = pd.to_datetime(df['Tanggal Ajuan'])
    today = pd.to_datetime(datetime.date.today())
    
    def hitung_umur(row):
        if row['Status Klaim'] not in STATUS_AMAN:
            delta = (today - row['Tanggal Ajuan']).days
            return max(delta, 0)
        return None
    
    df['Umur Hari'] = df.apply(hitung_umur, axis=1)
    
    def bucket_umur(umur):
        if pd.isna(umur): return "Aman / Final"
        if umur <= 30: return "0-30 Hari"
        elif umur <= 60: return "31-60 Hari"
        elif umur <= 90: return "61-90 Hari"
        else: return "> 90 Hari"
        
    df['Kelompok Umur'] = df['Umur Hari'].apply(bucket_umur)
    df['Tahun'] = df['Tanggal Ajuan'].dt.year
    df['Bulan'] = df['Tanggal Ajuan'].dt.month
    df['ISO_Year'] = df['Tanggal Ajuan'].dt.isocalendar().year
    df['ISO_Week'] = df['Tanggal Ajuan'].dt.isocalendar().week
    
    return df

# Helper function format Rupiah
def format_rupiah(angka):
    return f"Rp {angka:,.0f}".replace(",", ".")

def format_rupiah_desimal(x):
    if pd.isna(x): return "Rp 0,00"
    formatted = f"Rp {x:,.2f}"
    return formatted.replace(',', 'X').replace('.', ',').replace('X', '.')

def format_short_idr(x):
    if pd.isna(x): return "0"
    if x >= 1e9: return f"{x/1e9:.1f} M"
    elif x >= 1e6: return f"{x/1e6:.1f} Jt"
    else: return f"{x:,.0f}"

# EKSEKUSI PEMBACAAN FILE DENGAN DETEKSI PERUBAHAN
file_path = "data/aps.csv"
try:
    # Mengambil waktu kapan file csv terakhir kali di-replace/di-save
    current_mtime = os.path.getmtime(file_path)
    df_raw = load_data(current_mtime)
except FileNotFoundError:
    st.error("File CSV tidak ditemukan! Pastikan file 'aps.csv' berada di dalam folder 'data/'.")
    st.stop()

# ==========================================
# 2. LOGIKA FILTERING (SIDEBAR)
# ==========================================
st.sidebar.markdown(f"👤 Login sebagai: **{st.session_state['username']}**")
if st.sidebar.button("Logout", use_container_width=True):
    st.session_state["logged_in"] = False
    st.session_state["username"] = ""
    st.rerun()
st.sidebar.divider()
st.sidebar.header("⚙️ Filter Utama (AND)")

list_unit = ["Semua Unit"] + list(df_raw['unit'].dropna().unique())
filter_unit = st.sidebar.selectbox("Pilih Unit / Rumah Sakit:", list_unit)

list_periode = ["Semua Waktu", "Tahun Ini", "Bulan Ini", "Bulan Lalu", "Pekan Ini", "Pekan Lalu", "Pilih Tanggal (Kustom)"]
filter_periode = st.sidebar.selectbox("Pilih Periode Ajuan:", list_periode)

rentang_tanggal = None
if filter_periode == "Pilih Tanggal (Kustom)":
    today_date = datetime.date.today()
    default_start = today_date - datetime.timedelta(days=30)
    rentang_tanggal = st.sidebar.date_input("Pilih Rentang Tanggal:", value=(default_start, today_date), max_value=today_date)

list_status = list(df_raw['Status Klaim'].dropna().unique())
filter_status = st.sidebar.multiselect("Pilih Status Klaim:", options=list_status, default=list_status)

# Tombol Sinkronisasi Manual
st.sidebar.markdown("---")
if st.sidebar.button("🔄 Segarkan Data Sekarang", use_container_width=True):
    st.cache_data.clear() # Membersihkan cache secara paksa
    st.rerun()            # Memuat ulang halaman saat itu juga

# -- PROSES PENYARINGAN DATA --
df_filtered = df_raw.copy()

if filter_unit != "Semua Unit":
    df_filtered = df_filtered[df_filtered['unit'] == filter_unit]

today_date = datetime.date.today()
curr_year = today_date.year
curr_month = today_date.month
curr_iso_year, curr_iso_week, _ = today_date.isocalendar()

if filter_periode == "Tahun Ini":
    df_filtered = df_filtered[df_filtered['Tahun'] == curr_year]
elif filter_periode == "Bulan Ini":
    df_filtered = df_filtered[(df_filtered['Tahun'] == curr_year) & (df_filtered['Bulan'] == curr_month)]
elif filter_periode == "Bulan Lalu":
    last_month = curr_month - 1 if curr_month > 1 else 12
    year_of_last_month = curr_year if curr_month > 1 else curr_year - 1
    df_filtered = df_filtered[(df_filtered['Tahun'] == year_of_last_month) & (df_filtered['Bulan'] == last_month)]
elif filter_periode == "Pekan Ini":
    df_filtered = df_filtered[(df_filtered['ISO_Year'] == curr_iso_year) & (df_filtered['ISO_Week'] == curr_iso_week)]
elif filter_periode == "Pekan Lalu":
    last_week = curr_iso_week - 1 if curr_iso_week > 1 else 52
    year_of_last_week = curr_iso_year if curr_iso_week > 1 else curr_iso_year - 1
    df_filtered = df_filtered[(df_filtered['ISO_Year'] == year_of_last_week) & (df_filtered['ISO_Week'] == last_week)]
elif filter_periode == "Pilih Tanggal (Kustom)":
    if rentang_tanggal and len(rentang_tanggal) == 2:
        df_filtered = df_filtered[(df_filtered['Tanggal Ajuan'] >= pd.to_datetime(rentang_tanggal[0])) & (df_filtered['Tanggal Ajuan'] <= pd.to_datetime(rentang_tanggal[1]))]
    elif rentang_tanggal and len(rentang_tanggal) == 1:
        df_filtered = df_filtered[df_filtered['Tanggal Ajuan'] == pd.to_datetime(rentang_tanggal[0])]

if len(filter_status) > 0:
    df_filtered = df_filtered[df_filtered['Status Klaim'].isin(filter_status)]
else:
    df_filtered = df_filtered.iloc[0:0] 

df_macet = df_filtered[~df_filtered['Status Klaim'].isin(STATUS_AMAN)].copy()

if not df_macet.empty:
    df_macet['Umur Hari'] = pd.to_numeric(df_macet['Umur Hari'], errors='coerce').fillna(0).astype(int)

# ==========================================
# 3. STRUKTUR TAMPILAN MENGGUNAKAN TAB
# ==========================================
tab1, tab2 = st.tabs(["📊 Analisis & Tren Global", "🚨 Actionable Dashboard (Prioritas Tindakan)"])

# ------------------------------------------
# TAB 1: ANALISIS & TREN GLOBAL (5 CHARTS)
# ------------------------------------------
with tab1:
    st.markdown("### 📈 Ringkasan Eksekutif & Tren Finansial")
    
    col1, col2, col3, col4 = st.columns(4)
    total_claims = len(df_filtered)
    total_tagihan = df_filtered['Total Tagihan'].sum()
    total_layak_bayar = df_filtered['Nilai Layak Bayar'].sum()
    total_patients = df_filtered['Rawat Inap'].sum() + df_filtered['Rawat Jalan'].sum()

    col1.metric("Total Claims", f"{total_claims:,}")
    col2.metric("Total Tagihan", format_rupiah(total_tagihan))
    col3.metric("Nilai Layak Bayar", format_rupiah(total_layak_bayar))
    col4.metric("Total Patients", f"{total_patients:,.0f}")

    st.markdown("---")
    c1, c2 = st.columns(2)
    
    with c1:
        st.subheader("1. Sebaran Status Klaim (Breakdown)")
        if not df_filtered.empty:
            df_status = df_filtered.groupby('Status Klaim').size().reset_index(name='Jumlah')
            fig1 = px.pie(df_status, values='Jumlah', names='Status Klaim', hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
            fig1.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig1, use_container_width=True)
        else:
            st.info("Data tidak tersedia.")

    with c2:
        st.subheader("2. Monitoring Umur Tagihan (Aging)")
        df_chart2 = df_filtered[df_filtered['Status Klaim'] != "Pembayaran Berhasil"]
        if not df_chart2.empty:
            df_aging_grouped = df_chart2.groupby('Kelompok Umur')['Total Tagihan'].sum().reset_index()
            urutan = ["0-30 Hari", "31-60 Hari", "61-90 Hari", "> 90 Hari"]
            df_aging_grouped['Kelompok Umur'] = pd.Categorical(df_aging_grouped['Kelompok Umur'], categories=urutan, ordered=True)
            df_aging_grouped = df_aging_grouped.sort_values('Kelompok Umur')
                
            fig2 = px.bar(df_aging_grouped, x='Kelompok Umur', y='Total Tagihan', text=df_aging_grouped['Total Tagihan'].apply(format_short_idr), color_discrete_sequence=['#4A90E2'])
            fig2.update_traces(textposition='outside')
            fig2.update_layout(yaxis_title="Total Tagihan (IDR)", xaxis_title="Kelompok Umur Tagihan")
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("Semua tagihan lunas / Pembayaran Berhasil.")

    c3, c4 = st.columns(2)
    
    with c3:
        st.subheader("3. Tipe Pasien (Rawat Inap vs Rawat Jalan)")
        if not df_filtered.empty:
            df_patients = df_filtered.groupby('Status Klaim')[['Rawat Inap', 'Rawat Jalan']].sum().reset_index()
            fig3 = px.bar(df_patients, x='Status Klaim', y=['Rawat Inap', 'Rawat Jalan'], barmode='stack', labels={'value': 'Jumlah Pasien', 'variable': 'Tipe Perawatan'}, color_discrete_sequence=['#2ECC71', '#3498DB'])
            st.plotly_chart(fig3, use_container_width=True)
        else:
            st.info("Data tidak tersedia.")

    with c4:
        st.subheader("4. Tren Finansial Kronologis")
        if not df_filtered.empty:
            df_trend = df_filtered.groupby('Tanggal Ajuan')[['Total Tagihan', 'Nilai Layak Bayar']].sum().reset_index()
            df_trend = df_trend.sort_values('Tanggal Ajuan')
            fig4 = px.line(df_trend, x='Tanggal Ajuan', y=['Total Tagihan', 'Nilai Layak Bayar'], labels={'value': 'Nominal (IDR)', 'variable': 'Kategori'}, color_discrete_map={'Total Tagihan': '#E74C3C', 'Nilai Layak Bayar': '#2ECC71'})
            fig4.update_layout(hovermode="x unified")
            st.plotly_chart(fig4, use_container_width=True)
        else:
            st.info("Data tidak tersedia.")

    st.markdown("---")
    st.subheader("5. Performa Komparasi Nilai Tagihan Antar Unit & Status")
    if not df_filtered.empty:
        df_unit_perf = df_filtered.groupby(['unit', 'Status Klaim'])['Total Tagihan'].sum().reset_index()
        fig5 = px.bar(
            df_unit_perf, y='unit', x='Total Tagihan', color='Status Klaim',
            orientation='h', barmode='stack', labels={'Total Tagihan': 'Total Tagihan (IDR)', 'unit': 'Unit / Rumah Sakit'},
            color_discrete_sequence=px.colors.qualitative.Safe
        )
        fig5.update_layout(yaxis={'categoryorder': 'total ascending'}, hovermode="y unified", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        st.plotly_chart(fig5, use_container_width=True)
    else:
        st.info("Data tidak tersedia.")

# ------------------------------------------
# TAB 2: ACTIONABLE DASHBOARD (PRIORITAS TINDAKAN)
# ------------------------------------------
with tab2:
    st.markdown("### 🚨 Kendali Tagihan Macet & Prioritas Tindakan Follow-Up")
    
    m1, m2, m3, m4 = st.columns(4)
    total_nominal_macet = df_macet['Total Tagihan'].sum()
    total_berkas_macet = len(df_macet)
    klaim_tertua = df_macet['Umur Hari'].max() if not df_macet.empty else 0

    if not df_macet.empty:
        rs_kritis_series = df_macet.groupby('unit')['Total Tagihan'].sum()
        rs_paling_kritis = rs_kritis_series.idxmax()
        nominal_kritis = rs_kritis_series.max()
        rs_kritis_label = f"{rs_paling_kritis} ({format_short_idr(nominal_kritis)})"
    else:
        rs_kritis_label = "Tidak Ada"

    m1.metric("Total Tagihan Macet", format_rupiah(total_nominal_macet), delta="Perlu Ditagih", delta_color="inverse")
    m2.metric("Jumlah Berkas Macet", f"{total_berkas_macet} Berkas")
    m3.metric("Klaim Tertua (Outstanding)", f"{klaim_tertua:.0f} Hari" if klaim_tertua > 0 else "0 Hari")
    m4.metric("Unit Paling Kritis", rs_kritis_label)

    st.markdown("---")

    if df_macet.empty:
        st.success("🎉 Bersih! Tidak ditemukan adanya penumpukan tagihan macet pada filter periode/unit ini.")
    else:
        col_kiri, col_kanan = st.columns([3, 2])
        
        with col_kiri:
            st.subheader("📋 Leaderboard Prioritas Hubungi RS")
            df_leaderboard = df_macet.groupby('unit').agg(
                Berkas_Macet=('No', 'count'),
                Total_Mendekam=('Total Tagihan', 'sum'),
                Hari_Tertua=('Umur Hari', 'max')
            ).reset_index()
            df_leaderboard = df_leaderboard.sort_values(by='Total_Mendekam', ascending=False)
            
            df_display = df_leaderboard.copy()
            df_display['Total_Mendekam'] = df_display['Total_Mendekam'].apply(format_rupiah_desimal)
            df_display['Hari_Tertua'] = df_display['Hari_Tertua'].apply(lambda x: f"{x:.0f} Hari")
            df_display.columns = ['Nama Unit / RS', 'Jumlah Berkas Macet', 'Total Tagihan Macet', 'Klaim Tertua']
            st.dataframe(df_display, use_container_width=True, hide_index=True)
            
        with col_kanan:
            st.subheader("🔍 Detail Hambatan Per Status")
            df_posisi = df_macet.groupby(['unit', 'Status Klaim'])['Total Tagihan'].sum().reset_index()
            fig_posisi = px.bar(
                df_posisi, y='unit', x='Total Tagihan', color='Status Klaim',
                orientation='h', barmode='stack', labels={'Total Tagihan': 'Total Tagihan Macet', 'unit': 'Unit/RS'},
                color_discrete_sequence=px.colors.qualitative.Bold
            )
            fig_posisi.update_layout(yaxis={'categoryorder': 'total ascending'}, showlegend=True, margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig_posisi, use_container_width=True)

        st.markdown("---")
        st.subheader("🗺️ Heatmap Pola Umur Kemacetan Antar Unit")
        
        df_matrix = df_macet.pivot_table(index='unit', columns='Kelompok Umur', values='Total Tagihan', aggfunc='sum', fill_value=0).reset_index()
        kolom_umur = ["0-30 Hari", "31-60 Hari", "61-90 Hari", "> 90 Hari"]
        for col in kolom_umur:
            if col not in df_matrix.columns:
                df_matrix[col] = 0
                
        df_matrix = df_matrix[['unit'] + kolom_umur]
        df_matrix = df_matrix.sort_values(by='> 90 Hari', ascending=False)
        
        df_matrix_styled = df_matrix.style.background_gradient(cmap='Reds', subset=kolom_umur).format(format_rupiah_desimal, subset=kolom_umur)
        st.dataframe(df_matrix_styled, use_container_width=True, hide_index=True)

        st.markdown("---")
        st.subheader("📥 Fitur Ekspor Data Lampiran Teguran")
        
        selected_rs = st.selectbox("Pilih Unit untuk Mengunduh Detail Berkas Macet:", list(df_macet['unit'].unique()))
        df_download = df_macet[df_macet['unit'] == selected_rs][
            ['Batch Number', 'Nomor Invoice', 'Tanggal Ajuan', 'Umur Hari', 'Kelompok Umur', 'Total Tagihan', 'Status Klaim', 'Catatan']
        ].sort_values(by='Umur Hari', ascending=False)
        
        df_download_display = df_download.style.format({
            'Total Tagihan': format_rupiah_desimal,
            'Umur Hari': '{:,.0f}',
            'Tanggal Ajuan': lambda t: t.strftime('%Y-%m-%d') if pd.notna(t) else ""
        })
        st.dataframe(df_download_display, use_container_width=True, hide_index=True)
        
        csv_data = df_download.to_csv(index=False).encode('utf-8')
        st.download_button(
            label=f"⬇️ Download Daftar Berkas Macet {selected_rs} (CSV)",
            data=csv_data,
            file_name=f"Berkas_Macet_{selected_rs.replace(' ', '_')}.csv",
            mime='text/csv'
        )
