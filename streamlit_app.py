import streamlit as st
import sqlite3
import os
import uuid
from PIL import Image, ImageFilter

# 配置
UPLOAD_FOLDER = "uploads"
DB_PATH = "postcards.db"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# 初始化数据库
def init_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
    c.execute('''
    CREATE TABLE IF NOT EXISTS postcards (
        id TEXT PRIMARY KEY,
        front_path TEXT,
        back_path TEXT,
        series TEXT DEFAULT '未分类',
        send_place TEXT DEFAULT '未知',
        send_time TEXT DEFAULT '未知',
        receive_place TEXT DEFAULT '未知',
        receive_time TEXT DEFAULT '未知',
        rating INTEGER DEFAULT 0
    )
    ''')
    conn.commit()
    return conn

conn = init_db()

# Pillow 实现图片模糊（替代 OpenCV，遮挡地址）
def blur_image(input_path, output_path):
    try:
        img = Image.open(input_path)
        w, h = img.size
        # 截取右下角区域做模糊（地址区）
        box = (int(w*0.5), int(h*0.6), w, h)
        region = img.crop(box)
        region = region.filter(ImageFilter.GaussianBlur(radius=15))
        img.paste(region, box)
        img.save(output_path)
        return True
    except Exception as e:
        st.warning(f"图片处理失败: {e}")
        return False

# 保存上传文件
def save_file(uploaded_file, save_path):
    with open(save_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

# 页面布局
st.set_page_config(page_title="极限明信片管理", layout="wide")
st.title("📮 极限明信片管理系统")

# 上传区域
st.subheader("上传新明信片")
col_up1, col_up2 = st.columns(2)
front_file = col_up1.file_uploader("正面照片", type=["jpg","jpeg","png"])
back_file = col_up2.file_uploader("背面照片（自动模糊地址）", type=["jpg","jpeg","png"])

if st.button("✅ 提交保存"):
    if not front_file:
        st.error("请选择正面照片！")
    else:
        card_id = str(uuid.uuid4())
        # 保存正面
        front_name = f"{card_id}_front.jpg"
        front_path = os.path.join(UPLOAD_FOLDER, front_name)
        save_file(front_file, front_path)

        # 处理并保存背面
        back_path = None
        if back_file:
            back_raw_name = f"{card_id}_raw.jpg"
            back_raw_path = os.path.join(UPLOAD_FOLDER, back_raw_name)
            save_file(back_file, back_raw_path)

            back_name = f"{card_id}_back.jpg"
            back_path = os.path.join(UPLOAD_FOLDER, back_name)
            blur_image(back_raw_path, back_path)
            os.remove(back_raw_path)

        # 写入数据库
        c = conn.cursor()
        c.execute(
            "INSERT INTO postcards (id, front_path, back_path) VALUES (?,?,?)",
            (card_id, front_path, back_path)
        )
        conn.commit()
        st.success("🎉 明信片上传成功！")
        st.rerun()

# 展示&管理区域
st.divider()
st.subheader("明信片列表")
c = conn.cursor()
c.execute("SELECT * FROM postcards ORDER BY rowid DESC")
cards = c.fetchall()

if not cards:
    st.info("暂无已上传明信片")
else:
    for item in cards:
        card_id, front_path, back_path, series, send_place, send_time, rec_place, rec_time, rating = item
        with st.container(border=True):
            col1, col2, col3 = st.columns([1,1,4])
            with col1:
                if os.path.exists(front_path):
                    st.image(front_path, use_column_width=True)
            with col2:
                if back_path and os.path.exists(back_path):
                    st.image(back_path, use_column_width=True)
                else:
                    st.write("无背面")
            with col3:
                st.write(f"ID: {card_id}")
                st.write(f"系列: {series} | 评级: {rating}/5")
                st.write(f"寄出: {send_place} {send_time} | 收件: {rec_place} {rec_time}")
                if st.button("🗑️ 删除", key=f"del_{card_id}"):
                    # 删除本地文件
                    if os.path.exists(front_path):
                        os.remove(front_path)
                    if back_path and os.path.exists(back_path):
                        os.remove(back_path)
                    # 删除数据库记录
                    c.execute("DELETE FROM postcards WHERE id=?", (card_id,))
                    conn.commit()
                    st.success("已删除")
                    st.rerun()
