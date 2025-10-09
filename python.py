# =================================================================================
#               ỨNG DỤNG PHÂN TÍCH BÁO CÁO TÀI CHÍNH VỚI GEMINI AI
# =================================================================================
# Tác giả: Gemini (Được huấn luyện bởi một lập trình viên Streamlit nhiều năm kinh nghiệm)
# Mô tả: Ứng dụng này cho phép người dùng tải lên file Báo cáo tài chính (Excel),
# tự động tính toán các chỉ số quan trọng và sử dụng Google Gemini để đưa ra
# những phân tích, nhận định chuyên sâu về tình hình tài chính của doanh nghiệp.
# =================================================================================

import streamlit as st
import pandas as pd
import plotly.express as px
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions

# --- Cấu hình trang và Tiêu đề ---
st.set_page_config(
    page_title="Trợ lý Phân tích BCTC",
    layout="wide",
    page_icon="💼"
)

st.title("💼 Trợ lý Phân tích Báo cáo Tài chính (BCTC)")
st.caption("Tải lên file BCTC dạng Excel để bắt đầu phân tích tự động với sự hỗ trợ từ AI.")

# =================================================================================
# 1️⃣ CÁC HÀM XỬ LÝ DỮ LIỆU
# =================================================================================

@st.cache_data(show_spinner="Đang xử lý dữ liệu từ file Excel...")
def process_financial_data(df):
    """
    Hàm này thực hiện các công việc sau:
    1. Chuẩn hóa dữ liệu: Đảm bảo các cột số là kiểu numeric.
    2. Tính toán Tăng trưởng: So sánh số liệu 'Năm sau' so với 'Năm trước'.
    3. Tính toán Tỷ trọng: Phân tích cơ cấu tài sản và nguồn vốn.
    """
    # Đổi tên cột để thống nhất
    df.columns = ['Chỉ tiêu', 'Năm trước', 'Năm sau']

    # Chuyển các cột số liệu sang dạng số, nếu lỗi thì thay bằng 0
    numeric_cols = ['Năm trước', 'Năm sau']
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # --- Tính toán Tốc độ tăng trưởng ---
    # Dùng replace(0, 1e-9) để tránh lỗi chia cho 0
    df['Tăng trưởng (%)'] = (
        (df['Năm sau'] - df['Năm trước']) / df['Năm trước'].replace(0, 1e-9)
    ) * 100

    # --- Tính toán Tỷ trọng ---
    # Tìm giá trị 'Tổng tài sản' và 'Tổng nguồn vốn' để làm mẫu số
    # Dùng regex để bắt được các trường hợp 'TỔNG CỘNG TÀI SẢN' hoặc 'TỔNG TÀI SẢN'
    tong_tai_san_row = df[df['Chỉ tiêu'].str.contains('TỔNG CỘNG TÀI SẢN|TỔNG TÀI SẢN', case=False, na=False, regex=True)]
    tong_nguon_von_row = df[df['Chỉ tiêu'].str.contains('TỔNG CỘNG NGUỒN VỐN|TỔNG NGUỒN VỐN', case=False, na=False, regex=True)]

    if tong_tai_san_row.empty or tong_nguon_von_row.empty:
        st.error("Lỗi: Không tìm thấy dòng 'Tổng cộng tài sản' hoặc 'Tổng cộng nguồn vốn' trong file. Vui lòng kiểm tra lại cấu trúc file Excel.")
        return None

    # Lấy giá trị tổng tài sản (nếu không có thì dùng 1e-9 để tránh lỗi)
    tong_tai_san_truoc = tong_tai_san_row['Năm trước'].iloc[0] or 1e-9
    tong_tai_san_sau = tong_tai_san_row['Năm sau'].iloc[0] or 1e-9

    # Lấy giá trị tổng nguồn vốn
    tong_nguon_von_truoc = tong_nguon_von_row['Năm trước'].iloc[0] or 1e-9
    tong_nguon_von_sau = tong_nguon_von_row['Năm sau'].iloc[0] or 1e-9

    # Tính tỷ trọng cho từng chỉ tiêu
    df['Tỷ trọng Năm trước (%)'] = 100 * df['Năm trước'] / tong_tai_san_truoc
    df['Tỷ trọng Năm sau (%)'] = 100 * df['Năm sau'] / tong_tai_san_sau

    return df

@st.cache_data(show_spinner="Đang tính toán các chỉ số tài chính...")
def calculate_financial_ratios(df):
    """
    Tính toán các chỉ số tài chính quan trọng từ DataFrame đã được xử lý.
    Bao gồm: Chỉ số thanh toán hiện hành.
    """
    ratios = {
        'Thanh toán hiện hành Năm trước': 'N/A',
        'Thanh toán hiện hành Năm sau': 'N/A'
    }
    try:
        # Lấy dữ liệu các chỉ tiêu cần thiết
        tsnh_row = df[df['Chỉ tiêu'].str.contains('TÀI SẢN NGẮN HẠN', case=False, na=False)]
        no_nh_row = df[df['Chỉ tiêu'].str.contains('NỢ NGẮN HẠN', case=False, na=False)]

        if tsnh_row.empty or no_nh_row.empty:
            st.warning("⚠️ Cảnh báo: Thiếu chỉ tiêu 'Tài sản ngắn hạn' hoặc 'Nợ ngắn hạn' để tính toán đầy đủ các chỉ số.")
            return ratios

        # Lấy giá trị
        tsnh_truoc = tsnh_row['Năm trước'].iloc[0]
        tsnh_sau = tsnh_row['Năm sau'].iloc[0]
        no_nh_truoc = no_nh_row['Năm trước'].iloc[0]
        no_nh_sau = no_nh_row['Năm sau'].iloc[0]

        # Tính toán chỉ số (tránh chia cho 0)
        ratios['Thanh toán hiện hành Năm trước'] = tsnh_truoc / no_nh_truoc if no_nh_truoc != 0 else 0
        ratios['Thanh toán hiện hành Năm sau'] = tsnh_sau / no_nh_sau if no_nh_sau != 0 else 0

    except IndexError:
        st.warning("⚠️ Cảnh báo: Dữ liệu trong file Excel không đủ để tính các chỉ số tài chính.")
    except Exception as e:
        st.error(f"Lỗi không xác định khi tính toán chỉ số: {e}")

    return ratios

# =================================================================================
# 2️⃣ HÀM GỌI GEMINI API
# =================================================================================

def get_ai_analysis(data_df, ratios, api_key):
    """
    Gửi dữ liệu đã phân tích đến Gemini Pro và nhận lại nhận xét chuyên sâu.
    """
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash-latest")

        # Tạo prompt chi tiết để Gemini đưa ra câu trả lời chất lượng nhất
        prompt = f"""
        Với vai trò là một chuyên gia phân tích tài chính cấp cao, hãy dựa vào các dữ liệu sau đây để đưa ra một bản phân tích chi tiết về tình hình tài chính của doanh nghiệp.

        Bản phân tích cần có cấu trúc rõ ràng, chuyên nghiệp và dễ hiểu, bao gồm các phần sau:
        1.  **Đánh giá tổng quan:** Nhận xét chung về sức khỏe tài chính của doanh nghiệp trong kỳ phân tích.
        2.  **Phân tích về quy mô và tăng trưởng:** Dựa vào sự biến động của Tổng tài sản, Doanh thu, và Lợi nhuận.
        3.  **Phân tích về cơ cấu tài sản và nguồn vốn:** Nhận xét về sự thay đổi trong tỷ trọng các khoản mục chính (VD: tài sản ngắn hạn, nợ phải trả).
        4.  **Phân tích về khả năng thanh toán:** Dựa vào các chỉ số thanh toán đã được tính toán.
        5.  **Kết luận và đề xuất (nếu có):** Tóm tắt những điểm mạnh, điểm yếu và đưa ra một vài gợi ý.

        **DỮ LIỆU ĐẦU VÀO:**

        **1. Bảng phân tích tăng trưởng và tỷ trọng:**
        {data_df[['Chỉ tiêu', 'Năm trước', 'Năm sau', 'Tăng trưởng (%)', 'Tỷ trọng Năm sau (%)']].to_markdown(index=False)}

        **2. Các chỉ số tài chính quan trọng:**
        - Hệ số thanh toán hiện hành năm trước: {ratios['Thanh toán hiện hành Năm trước']:.2f}
        - Hệ số thanh toán hiện hành năm sau: {ratios['Thanh toán hiện hành Năm sau']:.2f}

        Hãy trình bày kết quả phân tích một cách mạch lạc, sử dụng các thuật ngữ tài chính chính xác.
        """

        response = model.generate_content(prompt)
        return response.text

    except google_exceptions.InvalidArgument as e:
        st.error("❌ Lỗi API Key: API Key của Sếp không hợp lệ hoặc đã hết hạn. Vui lòng kiểm tra lại trong phần Secrets của Streamlit.")
        return None
    except Exception as e:
        st.error(f"⚠️ Đã có lỗi xảy ra khi kết nối đến Gemini AI: {e}")
        return None

# =================================================================================
# 3️⃣ GIAO DIỆN CHÍNH CỦA ỨNG DỤNG
# =================================================================================

# --- Khu vực tải file lên ---
with st.sidebar:
    st.header("⚙️ Bảng điều khiển")
    uploaded_file = st.file_uploader(
        "Tải file Excel BCTC của Sếp tại đây",
        type=['xlsx', 'xls']
    )
    st.info(
        """
        **Lưu ý:** File Excel cần có 3 cột với thứ tự:
        1.  **Chỉ tiêu**
        2.  **Năm trước**
        3.  **Năm sau**
        """
    )

# --- Xử lý và hiển thị kết quả ---
if uploaded_file:
    try:
        df_raw = pd.read_excel(uploaded_file)
        df_processed = process_financial_data(df_raw.copy())

        # Chỉ tiếp tục nếu process_financial_data không trả về None (tức là không có lỗi)
        if df_processed is not None:
            # --- Hiển thị bảng dữ liệu đã xử lý ---
            st.subheader("Bảng 1: Phân tích Tăng trưởng & Tỷ trọng")
            st.dataframe(
                df_processed.style.format({
                    'Năm trước': '{:,.0f}',
                    'Năm sau': '{:,.0f}',
                    'Tăng trưởng (%)': '{:.2f}%',
                    'Tỷ trọng Năm trước (%)': '{:.2f}%',
                    'Tỷ trọng Năm sau (%)': '{:.2f}%'
                }),
                use_container_width=True,
                height=500
            )

            # Tính toán các chỉ số
            ratios = calculate_financial_ratios(df_processed)

            # --- Khu vực phân tích của AI ---
            st.divider()
            st.subheader("🤖 Phân tích Chuyên sâu từ Trợ lý AI")

            # Lấy API key từ secrets của Streamlit
            # Sếp cần phải setup secret này trên Streamlit Cloud
            api_key = st.secrets.get("GEMINI_API_KEY")

            if not api_key:
                st.error("Sếp ơi, chưa có 'GEMINI_API_KEY' trong phần Secrets của Streamlit. Em không thể kết nối với AI được.")
            else:
                if st.button("Yêu cầu AI phân tích ngay!", type="primary"):
                    with st.spinner("⏳ Em đang phân tích dữ liệu, Sếp chờ chút nhé..."):
                        ai_result = get_ai_analysis(df_processed, ratios, api_key)

                        if ai_result:
                            # --- Dashboard trực quan ---
                            st.subheader("Bảng 2: Dashboard các chỉ số chính")
                            col1, col2, col3 = st.columns(3)
                            
                            # Dùng try-except để tránh lỗi nếu không tìm thấy chỉ tiêu
                            try:
                                tts_sau = df_processed[df_processed['Chỉ tiêu'].str.contains('TỔNG CỘNG TÀI SẢN|TỔNG TÀI SẢN', case=False, na=False, regex=True)]['Năm sau'].iloc[0]
                                dt_sau = df_processed[df_processed['Chỉ tiêu'].str.contains('Doanh thu bán hàng', case=False, na=False)]['Năm sau'].iloc[0]
                                ln_sau = df_processed[df_processed['Chỉ tiêu'].str.contains('Lợi nhuận sau thuế', case=False, na=False)]['Năm sau'].iloc[0]

                                col1.metric("Tổng tài sản (Năm sau)", f"{tts_sau:,.0f} VNĐ")
                                col2.metric("Doanh thu (Năm sau)", f"{dt_sau:,.0f} VNĐ")
                                col3.metric("Lợi nhuận sau thuế (Năm sau)", f"{ln_sau:,.0f} VNĐ")
                            except (IndexError, KeyError):
                                st.warning("Không thể hiển thị đầy đủ dashboard do thiếu một số chỉ tiêu quan trọng.")


                            col1, col2, col3 = st.columns(3)
                            col1.metric("Tăng trưởng DT TB (%)", f"{df_processed[df_processed['Chỉ tiêu'].str.contains('Doanh thu', case=False, na=False)]['Tăng trưởng (%)'].mean():.2f}%")
                            col2.metric("Tỷ trọng TSNH (%)", f"{df_processed[df_processed['Chỉ tiêu'].str.contains('TÀI SẢN NGẮN HẠN', case=False, na=False)]['Tỷ trọng Năm sau (%)'].iloc[0]:.2f}%")
                            col3.metric("Hệ số thanh toán HH", f"{ratios.get('Thanh toán hiện hành Năm sau', 0):.2f}")


                            # --- Hiển thị kết quả AI ---
                            st.subheader("Nhận định từ Trợ lý AI")
                            st.markdown(ai_result)

                            # --- Hiển thị biểu đồ ---
                            st.divider()
                            st.subheader("Bảng 3: Trực quan hóa dữ liệu")
                            
                            tab1, tab2, tab3 = st.tabs(["Cơ cấu tài sản", "Tăng trưởng", "So sánh giá trị"])
                            
                            with tab1:
                                st.markdown("##### Cơ cấu tài sản năm sau")
                                # Lọc ra các chỉ tiêu chính để vẽ biểu đồ cho gọn
                                pie_data = df_processed[df_processed['Chỉ tiêu'].isin(['Tiền và các khoản tương đương tiền', 'Hàng tồn kho', 'Các khoản phải thu ngắn hạn', 'Tài sản cố định'])]
                                if not pie_data.empty:
                                    fig = px.pie(pie_data, values='Năm sau', names='Chỉ tiêu', title='Tỷ trọng các khoản mục chính trong tài sản')
                                    st.plotly_chart(fig, use_container_width=True)
                                else:
                                    st.info("Không đủ dữ liệu chi tiết để vẽ biểu đồ cơ cấu.")

                            with tab2:
                                st.markdown("##### Tốc độ tăng trưởng các chỉ tiêu chính")
                                growth_data = df_processed[df_processed['Tăng trưởng (%)'].abs() > 0].set_index('Chỉ tiêu')
                                st.bar_chart(growth_data['Tăng trưởng (%)'])

                            with tab3:
                                st.markdown("##### So sánh giá trị Năm trước - Năm sau")
                                comparison_data = df_processed[df_processed['Chỉ tiêu'].isin(['TỔNG CỘNG TÀI SẢN', 'NỢ PHẢI TRẢ', 'VỐN CHỦ SỞ HỮU', 'Doanh thu bán hàng và cung cấp dịch vụ', 'Lợi nhuận sau thuế thu nhập doanh nghiệp'])].set_index('Chỉ tiêu')
                                st.bar_chart(comparison_data[['Năm trước', 'Năm sau']])


    except ValueError as ve:
        st.error(f"❌ Lỗi cấu trúc dữ liệu: {ve}. Sếp vui lòng kiểm tra lại file Excel.")
    except Exception as e:
        st.error(f"⚠️ Có lỗi không mong muốn xảy ra: {e}. Sếp thử kiểm tra lại định dạng file nhé.")

else:
    st.info("👋 Chào Sếp! Vui lòng tải lên file Excel từ thanh bên để em bắt đầu phân tích.")
