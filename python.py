# ==========================================================
# App Phân Tích Báo Cáo Tài Chính với Gemini AI
# Tác giả: ChatGPT (Streamlit Deploy Expert)
# ==========================================================

import streamlit as st
import pandas as pd
import plotly.express as px
import google.generativeai as genai
from google.api_core import exceptions as gex

# --- Cấu hình Trang ---
st.set_page_config(
    page_title="App Phân Tích Báo Cáo Tài Chính",
    layout="wide",
    page_icon="📊"
)

st.title("📈 Ứng dụng Phân Tích Báo Cáo Tài Chính")

# ==========================================================
# 1️⃣ HÀM XỬ LÝ DỮ LIỆU
# ==========================================================

@st.cache_data
def process_financial_data(df):
    """Tính toán tốc độ tăng trưởng và tỷ trọng."""
    numeric_cols = ['Năm trước', 'Năm sau']
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # 1. Tốc độ tăng trưởng
    df['Tốc độ tăng trưởng (%)'] = (
        (df['Năm sau'] - df['Năm trước']) / df['Năm trước'].replace(0, 1e-9)
    ) * 100

    # 2. Tỷ trọng
    tong_tai_san_row = df[df['Chỉ tiêu'].str.contains('TỔNG CỘNG TÀI SẢN', case=False, na=False)]
    if tong_tai_san_row.empty:
        raise ValueError("Không tìm thấy chỉ tiêu 'TỔNG CỘNG TÀI SẢN'.")

    tong_tai_san_N_1 = tong_tai_san_row['Năm trước'].iloc[0] or 1e-9
    tong_tai_san_N = tong_tai_san_row['Năm sau'].iloc[0] or 1e-9

    df['Tỷ trọng Năm trước (%)'] = (df['Năm trước'] / tong_tai_san_N_1) * 100
    df['Tỷ trọng Năm sau (%)'] = (df['Năm sau'] / tong_tai_san_N) * 100
    return df


# ==========================================================
# 2️⃣ HÀM GỌI GEMINI API
# ==========================================================
def get_ai_analysis(data_for_ai, api_key):
    """Gửi dữ liệu đến Gemini và nhận phản hồi."""
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")

        prompt = f"""
        Bạn là chuyên gia phân tích tài chính. Hãy viết nhận xét 3–4 đoạn
        về tình hình tài chính của doanh nghiệp dựa trên dữ liệu sau:
        {data_for_ai}
        """

        response = model.generate_content(prompt)
        return response.text

    except gex.InvalidArgument:
        return "❌ Lỗi: Key không hợp lệ hoặc hết hạn."
    except Exception as e:
        return f"⚠️ Lỗi khi gọi Gemini API: {e}"


# ==========================================================
# 3️⃣ TẢI FILE EXCEL & XỬ LÝ
# ==========================================================
uploaded_file = st.file_uploader(
    "1️⃣ Tải file Excel Báo cáo Tài chính (Chỉ tiêu | Năm trước | Năm sau)",
    type=['xlsx', 'xls']
)

if uploaded_file:
    try:
        df_raw = pd.read_excel(uploaded_file)
        df_raw.columns = ['Chỉ tiêu', 'Năm trước', 'Năm sau']
        df_processed = process_financial_data(df_raw.copy())

        # Hiển thị bảng
        st.subheader("📊 2️⃣ Bảng Tốc độ tăng trưởng & Tỷ trọng cơ cấu")
        st.dataframe(
            df_processed.style.format({
                'Năm trước': '{:,.0f}',
                'Năm sau': '{:,.0f}',
                'Tốc độ tăng trưởng (%)': '{:.2f}%',
                'Tỷ trọng Năm trước (%)': '{:.2f}%',
                'Tỷ trọng Năm sau (%)': '{:.2f}%'
            }),
            use_container_width=True
        )

        # ======================================================
        # 4️⃣ TÍNH TOÁN CÁC CHỈ SỐ CƠ BẢN
        # ======================================================
        try:
            tsnh_n = df_processed[df_processed['Chỉ tiêu'].str.contains('TÀI SẢN NGẮN HẠN', case=False, na=False)]['Năm sau'].iloc[0]
            tsnh_n_1 = df_processed[df_processed['Chỉ tiêu'].str.contains('TÀI SẢN NGẮN HẠN', case=False, na=False)]['Năm trước'].iloc[0]
            no_ngan_han_N = df_processed[df_processed['Chỉ tiêu'].str.contains('NỢ NGẮN HẠN', case=False, na=False)]['Năm sau'].iloc[0]
            no_ngan_han_N_1 = df_processed[df_processed['Chỉ tiêu'].str.contains('NỢ NGẮN HẠN', case=False, na=False)]['Năm trước'].iloc[0]

            thanh_toan_hien_hanh_N = tsnh_n / (no_ngan_han_N or 1e-9)
            thanh_toan_hien_hanh_N_1 = tsnh_n_1 / (no_ngan_han_N_1 or 1e-9)
        except IndexError:
            st.warning("⚠️ Thiếu chỉ tiêu 'TÀI SẢN NGẮN HẠN' hoặc 'NỢ NGẮN HẠN' để tính chỉ số.")
            thanh_toan_hien_hanh_N = "N/A"
            thanh_toan_hien_hanh_N_1 = "N/A"

        # ======================================================
        # 5️⃣ NHẬN XÉT AI + DASHBOARD
        # ======================================================
        st.subheader("5️⃣ Nhận xét Tình hình Tài chính (AI & Dashboard)")

        data_for_ai = pd.DataFrame({
            'Chỉ tiêu': [
                'Toàn bộ bảng dữ liệu',
                'Tăng trưởng Tài sản ngắn hạn (%)',
                'Thanh toán hiện hành (N-1)',
                'Thanh toán hiện hành (N)'
            ],
            'Giá trị': [
                df_processed.to_markdown(index=False),
                f"{df_processed[df_processed['Chỉ tiêu'].str.contains('TÀI SẢN NGẮN HẠN', case=False, na=False)]['Tốc độ tăng trưởng (%)'].iloc[0]:.2f}%",
                f"{thanh_toan_hien_hanh_N_1}",
                f"{thanh_toan_hien_hanh_N}"
            ]
        }).to_markdown(index=False)

        # ======================================================
        # NÚT PHÂN TÍCH AI
        # ======================================================
        if st.button("🤖 Yêu cầu AI Phân tích"):
            api_key = st.secrets.get("GEMINI_API_KEY")

            if api_key:
                with st.spinner("⏳ Đang gửi dữ liệu cho Gemini..."):
                    ai_result = get_ai_analysis(data_for_ai, api_key)

                    # ---------------- DASHBOARD KPI ----------------
                    st.markdown("## 🧭 Dashboard Tổng hợp Chỉ số Tài chính")
                    st.divider()

                    tong_tai_san = df_processed[df_processed['Chỉ tiêu'].str.contains('TỔNG CỘNG TÀI SẢN', case=False, na=False)]
                    tai_san_ngan_han = df_processed[df_processed['Chỉ tiêu'].str.contains('TÀI SẢN NGẮN HẠN', case=False, na=False)]
                    no_ngan_han = df_processed[df_processed['Chỉ tiêu'].str.contains('NỢ NGẮN HẠN', case=False, na=False)]

                    kpi_data = {
                        "Tổng tài sản (Năm sau)": f"{tong_tai_san['Năm sau'].iloc[0]:,.0f}" if not tong_tai_san.empty else "N/A",
                        "Tài sản ngắn hạn (Năm sau)": f"{tai_san_ngan_han['Năm sau'].iloc[0]:,.0f}" if not tai_san_ngan_han.empty else "N/A",
                        "Nợ ngắn hạn (Năm sau)": f"{no_ngan_han['Năm sau'].iloc[0]:,.0f}" if not no_ngan_han.empty else "N/A",
                        "Tốc độ tăng trưởng TB (%)": f"{df_processed['Tốc độ tăng trưởng (%)'].mean():.2f}%",
                        "Tỷ trọng TS ngắn hạn (%)": f"{tai_san_ngan_han['Tỷ trọng Năm sau (%)'].iloc[0]:.2f}%" if not tai_san_ngan_han.empty else "N/A",
                        "Hệ số thanh toán hiện hành": f"{thanh_toan_hien_hanh_N:.2f}" if isinstance(thanh_toan_hien_hanh_N, (int, float)) else "N/A"
                    }

                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Tổng tài sản (Năm sau)", kpi_data["Tổng tài sản (Năm sau)"])
                        st.metric("Tốc độ tăng trưởng TB (%)", kpi_data["Tốc độ tăng trưởng TB (%)"])
                    with col2:
                        st.metric("Tài sản ngắn hạn (Năm sau)", kpi_data["Tài sản ngắn hạn (Năm sau)"])
                        st.metric("Tỷ trọng TS ngắn hạn (%)", kpi_data["Tỷ trọng TS ngắn hạn (%)"])
                    with col3:
                        st.metric("Nợ ngắn hạn (Năm sau)", kpi_data["Nợ ngắn hạn (Năm sau)"])
                        st.metric("Hệ số thanh toán hiện hành", kpi_data["Hệ số thanh toán hiện hành"])

                    # ---------------- BIỂU ĐỒ ----------------
                    st.divider()
                    st.markdown("## 📊 Biểu đồ Phân tích Chi tiết")

                    st.subheader("🔹 So sánh giá trị Năm trước - Năm sau")
                    chart_data = df_processed[['Chỉ tiêu', 'Năm trước', 'Năm sau']].set_index('Chỉ tiêu')
                    st.bar_chart(chart_data, use_container_width=True)

                    st.subheader("🔹 Cơ cấu Tài sản Năm sau (Tỷ trọng %)")
                    pie_data = df_processed[['Chỉ tiêu', 'Tỷ trọng Năm sau (%)']]
                    pie_data = pie_data[~pie_data['Chỉ tiêu'].str.contains('TỔNG CỘNG', case=False, na=False)]
                    fig = px.pie(pie_data, values='Tỷ trọng Năm sau (%)', names='Chỉ tiêu', title='Cơ cấu Tài sản Năm sau (%)')
                    st.plotly_chart(fig, use_container_width=True)

                    st.subheader("🔹 Tốc độ Tăng trưởng (%)")
                    growth_chart = df_processed[['Chỉ tiêu', 'Tốc độ tăng trưởng (%)']].set_index('Chỉ tiêu')
                    st.line_chart(growth_chart, use_container_width=True)

                    # ---------------- NHẬN XÉT AI ----------------
                    st.divider()
                    st.markdown("## 🤖 Nhận xét Phân tích từ Gemini AI")
                    st.info(ai_result)
            else:
                st.error("🚫 Lỗi: Chưa có GEMINI_API_KEY trong Streamlit Secrets.")

    except ValueError as ve:
        st.error(f"❌ Lỗi cấu trúc dữ liệu: {ve}")
    except Exception as e:
        st.error(f"⚠️ Có lỗi xảy ra khi xử lý file: {e}")

else:
    st.info("📂 Vui lòng tải lên file Excel để bắt đầu phân tích.")
